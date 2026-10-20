"""Offline tests for the proxy pools.

`basic`, `unblocker`, `unblocker_ultra` and `auto` ride the existing
`proxy_pool` parameter. The API resolves each to a proxy network and the
Unblocker, so the SDK only has to carry the exact wire value; the pool names
written before them stay next to them, unchanged.
"""

import base64
import warnings

import pytest

from scrapfly import BrowserConfig, CrawlerConfig, ScrapeConfig, ScreenshotConfig

URL = "https://example.com"

POOLS = {
    "BASIC": "basic",
    "UNBLOCKER": "unblocker",
    "UNBLOCKER_ULTRA": "unblocker_ultra",
    "AUTO": "auto",
}

LEGACY_POOLS = {
    "PUBLIC_DATACENTER_POOL": "public_datacenter_pool",
    "PUBLIC_RESIDENTIAL_POOL": "public_residential_pool",
}

# The Tor pool is a current pool, not a name written before the proxy pools.
TOR_POOL = {"PUBLIC_TOR_POOL": "public_tor_pool"}


@pytest.mark.parametrize("name,value", {**POOLS, **TOR_POOL, **LEGACY_POOLS}.items())
def test_constant_carries_the_wire_value(name, value):
    assert getattr(ScrapeConfig, name) == value


@pytest.mark.parametrize("pool", POOLS.values())
def test_scrape_pool_is_sent_as_proxy_pool_without_asp(pool):
    params = ScrapeConfig(url=URL, proxy_pool=pool).to_api_params(key="x")
    assert params["proxy_pool"] == pool
    assert "asp" not in params


@pytest.mark.parametrize("pool", POOLS.values())
def test_crawler_pool_is_sent_as_proxy_pool_without_asp(pool):
    params = CrawlerConfig(url=URL, proxy_pool=pool).to_api_params()
    assert params["proxy_pool"] == pool
    assert "asp" not in params


def test_no_proxy_pool_is_sent_by_default():
    assert "proxy_pool" not in ScrapeConfig(url=URL).to_api_params(key="x")
    assert "proxy_pool" not in CrawlerConfig(url=URL).to_api_params()
    assert "proxy_pool" not in ScreenshotConfig(url=URL).to_api_params(key="x")


@pytest.mark.parametrize("pool", POOLS.values())
def test_pool_survives_the_dict_round_trip(pool):
    restored = ScrapeConfig.from_dict(ScrapeConfig(url=URL, proxy_pool=pool).to_dict())
    assert restored.proxy_pool == pool


def test_legacy_pool_with_unblocker_is_unchanged():
    params = ScrapeConfig(
        url=URL, proxy_pool=ScrapeConfig.PUBLIC_RESIDENTIAL_POOL, unblocker=True
    ).to_api_params(key="x")
    assert params["proxy_pool"] == "public_residential_pool"
    assert params["asp"] == "true"


def _exported(**overrides) -> str:
    """A log export as the engine writes it: the order the API sent."""
    msgpack = pytest.importorskip("msgpack")
    data = {
        "url": URL, "retry": True, "headers": {}, "session": None, "session_sticky_proxy": True,
        "cache": False, "cache_ttl": None, "cache_clear": False, "render_js": False, "method": "GET",
        "body": None, "ssl": False, "dns": False, "country": None, "debug": False,
        "correlation_id": None, "tags": [], "format": None, "js": None, "rendering_wait": None,
        "screenshots": None, "screenshot_flags": None, "proxy_pool": None, "auto_scroll": None,
        "cost_budget": None,
    }
    data.update(overrides)
    return base64.b64encode(msgpack.dumps(data)).decode("utf-8")


@pytest.mark.parametrize("unblocker_tier,pool,asp,expected", [
    ("none", "public_datacenter_pool", False, "basic"),
    ("normal", "public_residential_pool", True, "unblocker"),
    # `basic` on a project that forces the Unblocker: normal, still on datacenter.
    ("normal", "public_datacenter_pool", True, "basic"),
])
def test_replaying_an_export_sends_the_pool_word(unblocker_tier, pool, asp, expected):
    cfg = ScrapeConfig.from_exported_config(
        _exported(proxy_pool=pool, asp=asp, unblocker=asp, unblocker_tier=unblocker_tier)
    )
    params = cfg.to_api_params(key="x")
    assert params["proxy_pool"] == expected
    assert "asp" not in params


@pytest.mark.parametrize("unblocker_tier", ["ultra", None])
@pytest.mark.parametrize("pool,asp", [
    ("public_residential_pool", True),
    ("public_residential_pool", False),
    ("public_datacenter_pool", True),
    ("public_datacenter_pool", False),
])
def test_replaying_an_ultra_or_legacy_export_keeps_pool_and_asp(unblocker_tier, pool, asp):
    # ultra is `unblocker_ultra` or a request with asp=True: the pool and asp as exported
    # replay either one unchanged.
    overrides = {"proxy_pool": pool, "asp": asp, "unblocker": asp}
    if unblocker_tier is not None:
        overrides["unblocker_tier"] = unblocker_tier

    params = ScrapeConfig.from_exported_config(_exported(**overrides)).to_api_params(key="x")
    assert params["proxy_pool"] == pool
    assert params.get("asp") == ("true" if asp else None)


@pytest.mark.parametrize("pool", POOLS.values())
def test_screenshot_sends_the_pool(pool):
    params = ScreenshotConfig(url=URL, proxy_pool=pool).to_api_params(key="x")
    assert params["proxy_pool"] == pool


def test_screenshot_pool_survives_the_dict_round_trip():
    restored = ScreenshotConfig.from_dict(ScreenshotConfig(url=URL, proxy_pool="unblocker").to_dict())
    assert restored.proxy_pool == "unblocker"


@pytest.mark.parametrize("kwargs", [{"unblock": True}, {"unblock": False}, {"unblock_timeout": 30}])
def test_browser_unblock_params_are_deprecated(kwargs):
    with pytest.warns(DeprecationWarning, match="cloud_browser_unblock"):
        config = BrowserConfig(**kwargs)

    # Deprecated, not dropped: the WebSocket URL stays what it was.
    url = config.websocket_url(api_key="x")
    for name in kwargs:
        assert f"{name}=" in url


def test_browser_without_unblock_params_does_not_warn():
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        BrowserConfig(proxy_pool="residential")
