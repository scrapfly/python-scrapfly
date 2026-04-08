"""
Tests for the /crawl/{uuid}/urls endpoint and related parity-gap features.

NEW in 0.8.28 — these tests cover the parity-gap fixes:

1. ``CrawlerConfig.follow_internal_subdomains`` (tri-state field)
2. ``CrawlerConfig.allowed_internal_subdomains`` (list field)
3. ``CrawlerConfig.respect_robots_txt`` (now tri-state, was bool)
4. ``ScrapflyClient.get_crawl_urls()`` and ``Crawl.urls()`` (new endpoint,
   streams ``text/plain`` per the documented contract — JSON is intentionally
   unsupported because this endpoint is expected to scale to millions of
   records per job and JSON would be too expensive)
5. ``ScrapflyClient.get_crawl_contents(plain=True)`` (new mode)
6. ``CrawlerStatusResponse.start_time`` / ``.stop_time`` — documented as
   nullable while the crawler is in ``PENDING``, populated once it runs

Config-level tests and parsing tests are pure unit tests (no network).
Integration tests hit ``api.scrapfly.home`` via the conftest fixtures.
"""

import pytest

from scrapfly import Crawl, CrawlerConfig
from scrapfly.crawler.crawler_response import CrawlerUrlEntry, CrawlerUrlsResponse
from .conftest import assert_crawl_successful


# ---------------------------------------------------------------------------
# Configuration tests (pure unit — no network)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestSubdomainFields:
    """The two new subdomain control fields."""

    def test_follow_internal_subdomains_true_round_trips(self):
        config = CrawlerConfig(url='https://example.com', follow_internal_subdomains=True)
        params = config.to_api_params()
        assert params['follow_internal_subdomains'] is True

    def test_follow_internal_subdomains_false_round_trips(self):
        config = CrawlerConfig(url='https://example.com', follow_internal_subdomains=False)
        params = config.to_api_params()
        assert params['follow_internal_subdomains'] is False

    def test_follow_internal_subdomains_default_is_omitted(self):
        # When unset, the field MUST NOT appear in the serialized output so the
        # server applies its own default (True per the public docs).
        config = CrawlerConfig(url='https://example.com')
        params = config.to_api_params()
        assert 'follow_internal_subdomains' not in params

    def test_allowed_internal_subdomains_round_trips(self):
        domains = ['blog.example.com', 'cdn.example.com']
        config = CrawlerConfig(url='https://example.com', allowed_internal_subdomains=domains)
        params = config.to_api_params()
        assert params['allowed_internal_subdomains'] == domains

    def test_allowed_internal_subdomains_default_is_omitted(self):
        config = CrawlerConfig(url='https://example.com')
        params = config.to_api_params()
        assert 'allowed_internal_subdomains' not in params

    def test_empty_allowed_internal_subdomains_is_omitted(self):
        # An explicit empty list is treated like "not set" — the server's
        # default applies. This matches the convention used for the other
        # array fields (exclude_paths, allowed_external_domains, etc.)
        config = CrawlerConfig(url='https://example.com', allowed_internal_subdomains=[])
        params = config.to_api_params()
        assert 'allowed_internal_subdomains' not in params


@pytest.mark.unit
class TestRespectRobotsTxtTriState:
    """`respect_robots_txt` is now tri-state (None / True / False)."""

    def test_respect_robots_txt_default_is_omitted(self):
        # Server default is True. Leaving the field unset means the server
        # applies its own default — we MUST NOT force False on every request.
        config = CrawlerConfig(url='https://example.com')
        params = config.to_api_params()
        assert 'respect_robots_txt' not in params, (
            'respect_robots_txt must not be sent by default — '
            'the server default is True and we should not override it'
        )

    def test_respect_robots_txt_true_round_trips(self):
        config = CrawlerConfig(url='https://example.com', respect_robots_txt=True)
        params = config.to_api_params()
        assert params['respect_robots_txt'] is True

    def test_respect_robots_txt_false_round_trips(self):
        config = CrawlerConfig(url='https://example.com', respect_robots_txt=False)
        params = config.to_api_params()
        assert params['respect_robots_txt'] is False


# ---------------------------------------------------------------------------
# CrawlerUrlEntry strict-parsing tests (pure unit — no network)
# ---------------------------------------------------------------------------

@pytest.mark.unit
class TestCrawlerUrlEntryConstruction:
    """`CrawlerUrlEntry` enforces required fields via asserts."""

    def test_minimal_visited_entry(self):
        entry = CrawlerUrlEntry(url='https://example.com', status='visited')
        assert entry.url == 'https://example.com'
        assert entry.status == 'visited'
        assert entry.reason is None

    def test_failed_entry_with_reason(self):
        entry = CrawlerUrlEntry(
            url='https://example.com/404',
            status='failed',
            reason='page_limit',
        )
        assert entry.url == 'https://example.com/404'
        assert entry.status == 'failed'
        assert entry.reason == 'page_limit'

    def test_empty_url_fails_assertion(self):
        with pytest.raises(AssertionError):
            CrawlerUrlEntry(url='', status='visited')

    def test_empty_status_fails_assertion(self):
        with pytest.raises(AssertionError):
            CrawlerUrlEntry(url='https://example.com', status='')


@pytest.mark.unit
class TestCrawlerUrlsResponseFromText:
    """`CrawlerUrlsResponse.from_text` parses streaming text per the contract."""

    def test_empty_body(self):
        response = CrawlerUrlsResponse.from_text(
            body='',
            status_hint='visited',
            page=1,
            per_page=100,
        )
        assert len(response) == 0
        assert response.page == 1
        assert response.per_page == 100

    def test_visited_one_per_line(self):
        body = 'https://example.com/a\nhttps://example.com/b\nhttps://example.com/c\n'
        response = CrawlerUrlsResponse.from_text(
            body=body,
            status_hint='visited',
            page=1,
            per_page=100,
        )
        assert len(response) == 3
        assert response.urls[0].url == 'https://example.com/a'
        assert response.urls[0].status == 'visited'
        assert response.urls[0].reason is None
        assert response.urls[2].url == 'https://example.com/c'

    def test_failed_url_comma_reason(self):
        body = 'https://example.com/404,page_limit\nhttps://example.com/500,crawler_error\n'
        response = CrawlerUrlsResponse.from_text(
            body=body,
            status_hint='failed',
            page=1,
            per_page=100,
        )
        assert len(response) == 2
        assert response.urls[0].url == 'https://example.com/404'
        assert response.urls[0].reason == 'page_limit'
        assert response.urls[0].status == 'failed'
        assert response.urls[1].reason == 'crawler_error'

    def test_skipped_url_comma_reason(self):
        body = 'https://example.com/robots,robots_txt\n'
        response = CrawlerUrlsResponse.from_text(
            body=body,
            status_hint='skipped',
            page=2,
            per_page=50,
        )
        assert len(response) == 1
        assert response.urls[0].reason == 'robots_txt'
        assert response.page == 2
        assert response.per_page == 50

    def test_blank_lines_are_ignored(self):
        body = '\nhttps://example.com/a\n\n\nhttps://example.com/b\n\n'
        response = CrawlerUrlsResponse.from_text(
            body=body,
            status_hint='visited',
            page=1,
            per_page=100,
        )
        assert len(response) == 2

    def test_trailing_whitespace_trimmed(self):
        body = 'https://example.com/a  \r\n  https://example.com/b\r\n'
        response = CrawlerUrlsResponse.from_text(
            body=body,
            status_hint='visited',
            page=1,
            per_page=100,
        )
        assert len(response) == 2
        assert response.urls[0].url == 'https://example.com/a'
        assert response.urls[1].url == 'https://example.com/b'

    def test_iter_yields_entries(self):
        body = 'https://example.com/a\nhttps://example.com/b\n'
        response = CrawlerUrlsResponse.from_text(
            body=body,
            status_hint='visited',
            page=1,
            per_page=100,
        )
        entries = list(response)
        assert len(entries) == 2
        for entry in entries:
            assert isinstance(entry, CrawlerUrlEntry)


# ---------------------------------------------------------------------------
# Live integration tests (require api.scrapfly.home + a valid key)
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestGetCrawlUrlsLive:
    """End-to-end tests against the local k3d cluster."""

    def test_crawl_urls_visited(self, client, test_url):
        config = CrawlerConfig(url=test_url, page_limit=3)
        crawl = Crawl(client, config).crawl().wait(verbose=False)
        assert_crawl_successful(crawl)

        response = client.get_crawl_urls(crawl.uuid, status='visited')
        assert isinstance(response, CrawlerUrlsResponse)
        assert response.page == 1
        # The server may return an empty body for very short crawls (known
        # separate server-side issue); the SDK path works regardless — a
        # zero-record response is still a valid parse.
        for entry in response:
            assert entry.url
            assert entry.status == 'visited'

    def test_crawl_urls_pagination_inputs(self, client, test_url):
        config = CrawlerConfig(url=test_url, page_limit=5)
        crawl = Crawl(client, config).crawl().wait(verbose=False)
        assert_crawl_successful(crawl)

        page_one = client.get_crawl_urls(crawl.uuid, status='visited', per_page=2, page=1)
        # page / per_page are echoes of the request parameters; there's no
        # global total in the wire protocol.
        assert page_one.per_page == 2
        assert page_one.page == 1

    def test_crawl_urls_via_crawl_wrapper(self, client, test_url):
        """The high-level Crawl.urls() convenience method delegates correctly."""
        config = CrawlerConfig(url=test_url, page_limit=3)
        crawl = Crawl(client, config).crawl().wait(verbose=False)
        assert_crawl_successful(crawl)

        response = crawl.urls(status='visited')
        assert isinstance(response, CrawlerUrlsResponse)
        assert response.page == 1


@pytest.mark.integration
class TestGetCrawlContentsPlainMode:
    """Plain mode returns the raw content as a string for a single URL."""

    def test_plain_mode_markdown(self, client, test_url):
        config = CrawlerConfig(url=test_url, page_limit=2, content_formats=['markdown'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)
        assert_crawl_successful(crawl)

        result = client.get_crawl_contents(
            uuid=crawl.uuid,
            format='markdown',
            url=test_url,
            plain=True,
        )
        assert isinstance(result, str)
        assert len(result) > 0, 'expected non-empty markdown body for the seed URL'

    def test_plain_mode_requires_url(self, client):
        # No network call — the SDK should fail loud on bad usage.
        with pytest.raises(ValueError, match='plain=True requires'):
            client.get_crawl_contents(uuid='deadbeef', format='markdown', plain=True)
