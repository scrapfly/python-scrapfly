"""End-to-end integration tests for session_sticky_proxy semantics.

Current contract, verified against the API:

  - A reused session with session_sticky_proxy=true keeps one exit IP. That
    network-identity continuity is what a session exists to provide.
  - session_sticky_proxy=false on a reused session releases the provider's
    IP-binding token, so the exit IP is free to rotate. It is not required to
    change on any given pair of calls, so this asserts the call is accepted
    rather than asserting a different IP.
  - session_sticky_proxy=false with asp=true is rejected with 400. The anti-bot
    clearance is bound to the IP that solved the challenge, so the combination
    is contradictory and the API refuses it instead of silently overriding.

Deterministic serialization of the flag is covered offline by
test_scrape_config_sticky.py; these are the behavioral guard.

Run:
    SCRAPFLY_KEY=scp-live-... pytest tests/test_session_sticky_proxy.py -v -s
"""

import json
import os
import uuid

import pytest

# Drives the live API; skipped by tests/conftest.py without credentials.
# Session/proxy semantics end-to-end through the SDK: these drive real scrapes
# against a live Scrapfly environment.
pytestmark = [pytest.mark.integration, pytest.mark.e2e]


from scrapfly import ScrapeConfig, ScrapflyClient
from scrapfly.errors import ApiHttpClientError


API_KEY = os.environ.get("SCRAPFLY_KEY", "scp-live-YOUR_API_KEY_HERE")
API_HOST = os.environ.get("SCRAPFLY_API_HOST", "https://api.scrapfly.io")

IPIFY_URL = "https://api.ipify.org?format=json"
PROXY_POOL = os.environ.get("SCRAPFLY_TEST_POOL", "public_residential_pool")
COUNTRY = "us"


@pytest.fixture
def client() -> ScrapflyClient:
    return ScrapflyClient(key=API_KEY, host=API_HOST, verify=False)


@pytest.fixture
def session_name() -> str:
    return f"sticky-test-{uuid.uuid4().hex[:8]}"


def _scrape_country(client: ScrapflyClient, **overrides) -> str:
    """Country the request actually went out from, as reported by the API."""
    cfg = ScrapeConfig(
        url=IPIFY_URL,
        render_js=False,
        country=COUNTRY,
        proxy_pool=PROXY_POOL,
        **overrides,
    )
    result = client.scrape(cfg)

    return result.context['proxy']['country']


def _scrape_ip(client: ScrapflyClient, **overrides) -> str:
    cfg = ScrapeConfig(
        url=IPIFY_URL,
        render_js=False,
        country=COUNTRY,
        proxy_pool=PROXY_POOL,
        **overrides,
    )
    result = client.scrape(cfg)
    payload = json.loads(result.content)
    ip = payload.get("ip")
    assert ip, f"ipify returned no ip field: {result.content[:200]!r}"
    return ip


class TestSessionStickyProxy:
    def test_sticky_session_pins_ip(self, client: ScrapflyClient, session_name: str):
        """A reused session with sticky proxy keeps one exit IP."""
        first_ip = _scrape_ip(client, session=session_name, session_sticky_proxy=True, asp=False)
        second_ip = _scrape_ip(client, session=session_name, session_sticky_proxy=True, asp=False)

        assert first_ip == second_ip, (
            "A reused sticky session should keep one exit IP, but it changed "
            f"({first_ip} != {second_ip})."
        )

    def test_unpinned_session_still_honours_country(self, client: ScrapflyClient, session_name: str):
        """
        Releasing the IP-binding token also clears the geo attributes derived from
        the old IP (timezone, city, coordinates, ASN). Country targeting must
        survive that reset, on the first request and on the reused session.
        """
        for _ in range(2):
            country = _scrape_country(
                client, session=session_name, session_sticky_proxy=False, asp=False
            )
            assert country.lower() == COUNTRY, (
                f"country={COUNTRY} was requested but the exit proxy reported {country!r} "
                "after the sticky IP was released"
            )

    def test_non_sticky_with_asp_is_rejected(self, client: ScrapflyClient, session_name: str):
        """
        The clearance is bound to the IP that solved the challenge, so asp=true with
        session_sticky_proxy=false is contradictory and refused rather than silently
        overridden.
        """
        with pytest.raises(ApiHttpClientError) as raised:
            _scrape_ip(client, session=session_name, session_sticky_proxy=False, asp=True)

        assert 'incompatible with asp=true' in str(raised.value)
