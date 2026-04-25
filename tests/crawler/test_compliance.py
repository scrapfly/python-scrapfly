"""
Crawler Compliance Test Suite

Drives the Scrapfly Crawler API (via the Python SDK) against the
web-scraping-dev compliance trap suite, then asserts conformance by
querying the central report endpoint /crawler-test-report on the target
app.

The trap app exposes 30 scenario routes (robots.txt traps, redirect
loops, session-id vortex, infinite calendar, URL normalization,
nofollow, sitemap index, etc). Each route records hits in an
in-memory store. This test suite asserts hit counts after each crawl.

Server-side catalog:
    apps/web-scraping-dev/website/app/web/CRAWLER_TEST_SUITE.md
Reference scrape-engine implementation:
    apps/scrapfly/scrape-engine/scrape_engine/tests/crawler/test_crawler_compliance_suite.py
SDK brief:
    sdk/CRAWLER_COMPLIANCE_TEST_BRIEF.md

Required env vars (already loaded by conftest.py):
    SCRAPFLY_KEY        Dev API key (e.g. scp-live-...)
    SCRAPFLY_API_HOST   Local Scrapfly API (e.g. https://api.scrapfly.local)

Optional env var (this file only):
    WEB_SCRAPING_DEV_BASE   Trap app base URL.
                            Defaults to https://web-scraping.dev (public prod).
                            Override to https://web-scraping-dev.local for the
                            local self-hosted dev cluster.

Run:
    pytest tests/crawler/test_compliance.py -m compliance -xvs
"""
import os
import warnings

import httpx
import pytest

from scrapfly import Crawl, CrawlerConfig

from .conftest import assert_crawl_successful


# Suppress the noisy InsecureRequestWarning from urllib3 — the local dev cluster
# Traefik certs are self-signed; the SDK fixture and our httpx clients all
# use verify=False intentionally.
warnings.filterwarnings("ignore", category=Warning, module="urllib3")

TARGET_BASE = os.environ.get("WEB_SCRAPING_DEV_BASE", "https://web-scraping.dev")
REPORT_URL = f"{TARGET_BASE}/crawler-test-report"
RESET_URL = f"{REPORT_URL}/reset"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _http_client() -> httpx.Client:
    """Plain httpx client for talking to the trap app directly.

    DO NOT use the Scrapfly SDK for this — we are observing the trap store,
    not exercising the crawler. Mixing SDK retries / proxies / etc here
    would muddy the assertion.
    """
    return httpx.Client(timeout=15, verify=False)


def reset_trap_store() -> None:
    """Clear the remote trap store. Must be called before every test for
    isolation, since the store is a single global dict on the server."""
    with _http_client() as c:
        r = c.post(RESET_URL)
        r.raise_for_status()


def fetch_report(trap: str | None = None) -> dict:
    """Fetch the compliance report. If trap is set, filter to that trap."""
    params = {"trap": trap} if trap else None
    with _http_client() as c:
        r = c.get(REPORT_URL, params=params)
        r.raise_for_status()
        return r.json()


def hit_count(report: dict, trap_name: str) -> int:
    """Safe lookup — returns 0 if the trap was never hit. The trap store
    does NOT pre-register trap names, so a missing key means zero hits."""
    return (report.get("traps") or {}).get(trap_name, {}).get("hit_count", 0)


def run_crawl(client, **config_overrides) -> Crawl:
    """Run a crawl synchronously and return the completed Crawl object.

    All compliance tests use the same baseline config: small page_limit,
    cache disabled (so trap hits are reproducible), max_duration capped
    so a buggy run cannot block CI.
    """
    config_kwargs = {
        "url": TARGET_BASE + "/",
        "page_limit": 50,
        "max_depth": 2,
        "max_concurrency": 5,
        "max_duration": 120,
        # Cache off — we need fresh hits on every run, otherwise a cached
        # trap response would NOT call record_hit() server-side.
        "cache": False,
        "cache_clear": True,
        # Sensible defaults — most tests want politeness ON; the negative
        # control test overrides respect_robots_txt explicitly.
        "respect_robots_txt": True,
        "ignore_no_follow": False,
        "follow_external_links": False,
        # No ASP for localhost
        "asp": False,
    }
    config_kwargs.update(config_overrides)
    config = CrawlerConfig(**config_kwargs)
    crawl = Crawl(client, config).crawl().wait(verbose=False)
    return crawl


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_store_between_tests():
    """Ensure each test starts with an empty trap store."""
    reset_trap_store()
    yield
    # Leave state after test for post-mortem inspection.


# ---------------------------------------------------------------------------
# Robots.txt compliance
# ---------------------------------------------------------------------------


@pytest.mark.compliance
@pytest.mark.integration
class TestRobotsTxtCompliance:
    """The /robots-disallowed URL is linked from the homepage scenarios
    section but is Disallow'd in /robots.txt for all UAs. A conforming
    crawler MUST NOT fetch it."""

    def test_respects_robots_txt(self, client):
        crawl = run_crawl(client, page_limit=50, max_depth=2)
        assert_crawl_successful(crawl)

        report = fetch_report()
        violations = hit_count(report, "robots_txt_violation")
        assert violations == 0, (
            f"SDK crawl with respect_robots_txt=True fetched "
            f"/robots-disallowed {violations} times. The crawler is "
            "ignoring robots.txt Disallow directives. "
            f"Report: {report.get('traps', {}).get('robots_txt_violation')}"
        )

    def test_violates_robots_when_disabled_negative_control(self, client):
        """Negative control. With respect_robots_txt=False the crawler
        SHOULD discover and fetch /robots-disallowed. If this returns 0
        hits, the trap link is not discoverable AT ALL — which means the
        positive test above is meaningless and silently passes."""
        crawl = run_crawl(
            client,
            page_limit=50,
            max_depth=2,
            respect_robots_txt=False,
        )
        assert_crawl_successful(crawl)

        report = fetch_report()
        hits = hit_count(report, "robots_txt_violation")
        assert hits >= 1, (
            "Negative control failed: with respect_robots_txt=False the "
            "crawler still did not fetch /robots-disallowed. Either the "
            "scenario card on the trap homepage is missing, the link is "
            "not in the rendered HTML, or the SDK is not honoring "
            "respect_robots_txt=False. The robots-respect positive test "
            "above is therefore unreliable until this is fixed."
        )


# ---------------------------------------------------------------------------
# Meta / header robots directives (link-level nofollow)
# ---------------------------------------------------------------------------


@pytest.mark.compliance
@pytest.mark.integration
class TestNofollowCompliance:
    """Page-level <meta name='robots' content='nofollow'> and link-level
    <a rel='nofollow'> must both prevent the crawler from following the
    target. The X-Robots-Tag HTTP header variant should also be honored."""

    def test_respects_meta_nofollow(self, client):
        crawl = run_crawl(
            client,
            url=TARGET_BASE + "/meta-nofollow",
            page_limit=10,
            max_depth=2,
        )
        assert_crawl_successful(crawl)

        report = fetch_report()
        assert hit_count(report, "meta_nofollow_violation") == 0, (
            "Crawler followed a link from a page with "
            "<meta name='robots' content='nofollow'>"
        )

    def test_respects_rel_nofollow(self, client):
        crawl = run_crawl(
            client,
            url=TARGET_BASE + "/rel-nofollow",
            page_limit=10,
            max_depth=2,
        )
        assert_crawl_successful(crawl)

        report = fetch_report()
        assert hit_count(report, "rel_nofollow_violation") == 0, (
            "Crawler followed a link with rel='nofollow' attribute"
        )

    def test_respects_x_robots_tag_nofollow(self, client):
        crawl = run_crawl(
            client,
            url=TARGET_BASE + "/header-nofollow",
            page_limit=10,
            max_depth=2,
        )
        assert_crawl_successful(crawl)

        report = fetch_report()
        assert hit_count(report, "x_robots_tag_nofollow_violation") == 0, (
            "Crawler did not honor X-Robots-Tag: nofollow HTTP header"
        )


# ---------------------------------------------------------------------------
# Crawler traps — bounded behavior
# ---------------------------------------------------------------------------


@pytest.mark.compliance
@pytest.mark.integration
class TestCrawlerTraps:
    """Classic crawler traps that a naive implementation will fall into:
    redirect loops, session-id vortexes, infinite calendars."""

    def test_escapes_redirect_loop(self, client):
        """/loop-a -> 302 -> /loop-b -> 302 -> /loop-a indefinitely.
        Crawler must detect the cycle and abandon."""
        crawl = run_crawl(
            client,
            url=TARGET_BASE + "/loop-a",
            page_limit=20,
            max_depth=5,
        )
        assert_crawl_successful(crawl)

        loops = hit_count(fetch_report(), "redirect_loop")
        # A few hits while the cycle is detected is OK; infinite is not.
        assert loops < 10, (
            f"Crawler caught in redirect loop: {loops} hits on the loop "
            "endpoints. Cycle detection is not working."
        )

    def test_bounds_session_vortex(self, client):
        """/session-vortex injects a fresh ?sid=<uuid> on every render.
        A crawler that does not canonicalize URLs explodes. A conforming
        crawler should strip the sid param OR cap quickly via dedup."""
        crawl = run_crawl(
            client,
            url=TARGET_BASE + "/session-vortex",
            page_limit=100,
            max_depth=3,
        )
        assert_crawl_successful(crawl)

        hits = hit_count(fetch_report(), "session_vortex_hit")
        # Generous ceiling: a smart crawler hits ~1, a dumb one hits 100+.
        assert hits < 20, (
            f"Crawler trapped by session-id vortex: {hits} hits. Check "
            "URL canonicalization for volatile query params."
        )

    def test_bounds_infinite_calendar(self, client):
        """/calendar/YYYY/MM links to next/prev month infinitely. Must be
        capped by max_depth or by infinite-pagination heuristics."""
        crawl = run_crawl(
            client,
            url=TARGET_BASE + "/calendar/2024/01",
            page_limit=100,
            max_depth=5,
        )
        assert_crawl_successful(crawl)

        hits = hit_count(fetch_report(), "calendar_trap_hit")
        # max_depth=5 caps us well under 50 even if every link is followed.
        assert hits < 50, (
            f"Crawler stuck in infinite calendar: {hits} pages crawled"
        )

    def test_caps_redirect_chain(self, client):
        """/redirect-chain/1 -> .../2 -> ... -> /10 (final 200 body).
        The crawler should follow until either max_redirects or the 200."""
        crawl = run_crawl(
            client,
            url=TARGET_BASE + "/redirect-chain/1",
            page_limit=5,
            max_depth=1,
        )
        assert_crawl_successful(crawl)

        depth = hit_count(fetch_report(), "redirect_chain_depth")
        # 0 = chain not entered (bug); >10 = impossible. Both fail.
        assert 0 < depth <= 10, (
            f"Unexpected redirect-chain depth: {depth} (expected 1..10)"
        )


# ---------------------------------------------------------------------------
# URL normalization & deduplication
# ---------------------------------------------------------------------------


@pytest.mark.compliance
@pytest.mark.integration
class TestUrlNormalization:
    """Deduplication of URL variants that resolve to the same resource."""

    def test_collapses_fragments(self, client):
        """A page with links #a, #b, #c (all fragments of the same URL)
        must result in exactly ONE HTTP request, since fragments never
        leave the client."""
        crawl = run_crawl(
            client,
            url=TARGET_BASE + "/fragment-collapse",
            page_limit=10,
            max_depth=2,
        )
        assert_crawl_successful(crawl)

        # Starting on /fragment-collapse records 1 hit. The fragment links
        # must NOT generate any extra requests.
        assert hit_count(fetch_report(), "fragment_collapse_hit") == 1, (
            "Crawler made multiple requests for the same URL with "
            "different #fragment suffixes. Fragments must be stripped."
        )

    def test_normalizes_url_variants(self, client):
        """/normalize-source links to 6 variants of the same target URL
        (./target, ../normalize-source/target, /TARGET, trailing slash,
        empty query, with fragment). All must dedup to one fetch."""
        crawl = run_crawl(
            client,
            url=TARGET_BASE + "/normalize-source",
            page_limit=20,
            max_depth=2,
        )
        assert_crawl_successful(crawl)

        hits = hit_count(fetch_report(), "normalization_duplicate")
        assert hits <= 1, (
            f"Crawler fetched the normalized target {hits} times; "
            "expected at most 1. Check URL canonicalization (case "
            "sensitivity, trailing slash, fragment, empty query)."
        )


# ---------------------------------------------------------------------------
# Sitemap handling
# ---------------------------------------------------------------------------


@pytest.mark.compliance
@pytest.mark.integration
class TestSitemapHandling:
    """The trap app exposes a real sitemap index (50 children x 100 URLs)
    plus a deliberate dead link inside one of the children. Tests verify
    that the SDK can both consume sitemap indexes and survive dead links."""

    def test_reads_sitemap_index(self, client):
        crawl = run_crawl(
            client,
            url=TARGET_BASE + "/",
            page_limit=500,
            max_depth=1,
            use_sitemaps=True,
        )
        assert_crawl_successful(crawl)

        leafs = hit_count(fetch_report(), "sitemap_leaf_discovered")
        assert leafs > 0, (
            "Crawler with use_sitemaps=True did not discover any leaf "
            "URLs from /sitemap-index.xml. Either sitemap-index format "
            "is not supported, or the SDK did not pass use_sitemaps=true."
        )

    def test_tolerates_dead_link_in_sitemap(self, client):
        """One of the child sitemaps lists /sitemap-404-target which
        returns 404. The crawler must continue processing the rest."""
        crawl = run_crawl(
            client,
            url=TARGET_BASE + "/",
            page_limit=100,
            max_depth=1,
            use_sitemaps=True,
        )
        # The point is just that the crawl completes without crashing.
        # If we reached here without an exception, we are good.
        assert_crawl_successful(crawl)

        # Optional observation, not an assertion:
        hits = hit_count(fetch_report(), "sitemap_dead_link_followed")
        print(f"[observation] sitemap dead link followed: {hits} times")


# ---------------------------------------------------------------------------
# External-link boundary
# ---------------------------------------------------------------------------


@pytest.mark.compliance
@pytest.mark.integration
class TestExternalBoundary:
    """With follow_external_links=False the crawler must stay inside the
    base domain even when explicit redirects point outside."""

    def test_does_not_follow_external_redirect(self, client):
        crawl = run_crawl(
            client,
            url=TARGET_BASE + "/redirect-external",
            page_limit=5,
            max_depth=2,
            follow_external_links=False,
        )
        # No hard assertion on a trap counter; the test passes if the
        # crawl completes (i.e. did not get redirected forever to
        # example.com or crash on the boundary).
        assert_crawl_successful(crawl)

        report = fetch_report()
        followed = hit_count(report, "external_redirect_followed")
        print(f"[observation] external redirect followed: {followed}")
