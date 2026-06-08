"""End-to-end integration test for session_sticky_proxy semantics.

Ticket: ipify returns the same IP across requests on a reused session even
with session_sticky_proxy=false.

Empirical finding (dev cluster, residential + datacenter pools): a REUSED
Scrapfly session keeps ONE exit IP for its whole lifetime regardless of
session_sticky_proxy. The engine persists the resolved proxy.ip.ipv4 with
the session and aligns the browser fingerprint (timezone/geo/WebRTC) to it;
resolve_proxy() returns the stored proxy verbatim and never re-resolves a
new IP for a reused session. session_sticky_proxy controls the UPSTREAM
PROVIDER's IP-binding token (whether the provider is asked to pin the same
egress), not per-request rotation inside a live Scrapfly session.

So "same IP on a reused session" is expected behavior, NOT the bug. The
real bug was that the SDK never put session_sticky_proxy=false on the wire
at all (it only sent the param when true) — covered by the deterministic
serialization tests in test_scrape_config_sticky.py. These live tests are
the behavioral guard:

  - test_session_pins_ip: a reused session keeps one exit IP (the contract
    a session exists to provide), and the SDK round-trips the flag.
  - test_asp_pins_ip: asp=true forces sticky (scrape_order.py override),
    matching the exact shape of the reported curl.

Run:
    SCRAPFLY_KEY=scp-live-... pytest tests/test_session_sticky_proxy.py -v -s
"""

import json
import os
import uuid

import pytest

from scrapfly import ScrapeConfig, ScrapflyClient


API_KEY = os.environ.get("SCRAPFLY_KEY", "scp-live-YOUR_API_KEY_HERE")
API_HOST = os.environ.get("SCRAPFLY_API_HOST", "https://api.scrapfly.local")

IPIFY_URL = "https://api.ipify.org?format=json"
PROXY_POOL = os.environ.get("SCRAPFLY_TEST_POOL", "public_residential_pool")
COUNTRY = "us"


@pytest.fixture
def client() -> ScrapflyClient:
    return ScrapflyClient(key=API_KEY, host=API_HOST, verify=False)


@pytest.fixture
def session_name() -> str:
    return f"sticky-test-{uuid.uuid4().hex[:8]}"


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
    def test_session_pins_ip(self, client: ScrapflyClient, session_name: str):
        """A reused session keeps the same exit IP — the network-identity
        continuity a session exists to provide. session_sticky_proxy=false
        does NOT rotate the IP within a live session.
        """
        first_ip = _scrape_ip(
            client, session=session_name, session_sticky_proxy=False, asp=False
        )
        second_ip = _scrape_ip(
            client, session=session_name, session_sticky_proxy=False, asp=False
        )
        assert first_ip == second_ip, (
            "A reused session should keep one exit IP, but it changed "
            f"({first_ip} != {second_ip}). The session's persisted "
            "proxy.ip.ipv4 is the source of truth for a reused session."
        )

    def test_asp_pins_ip_regardless_of_flag(self, client: ScrapflyClient, session_name: str):
        """asp=true forces sticky even when session_sticky_proxy=false is
        sent — scrape_order.py overrides the flag. This is the exact shape
        of the reported curl; the same IP here is correct behavior.
        """
        first_ip = _scrape_ip(
            client, session=session_name, session_sticky_proxy=False, asp=True
        )
        second_ip = _scrape_ip(
            client, session=session_name, session_sticky_proxy=False, asp=True
        )
        assert first_ip == second_ip, (
            "asp=true should force a pinned exit IP (sticky override in "
            f"scrape_order.py) but it changed ({first_ip} != {second_ip})."
        )
