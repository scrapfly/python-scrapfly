from urllib.parse import parse_qs, urlsplit

from scrapfly import BrowserConfig


def test_joining_a_browser_sets_share_cdp():
    config = BrowserConfig(session="shared-shop", share_cdp=True)
    restored = BrowserConfig.from_dict(config.to_dict())

    query = parse_qs(urlsplit(restored.websocket_url("key")).query)
    assert query["session"] == ["shared-shop"]
    assert query["share_cdp"] == ["true"]
    assert "share_cdp" not in parse_qs(urlsplit(BrowserConfig(session="shared-shop").websocket_url("key")).query)
