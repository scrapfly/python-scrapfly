"""Offline serialization tests for session_sticky_proxy.

session_sticky_proxy=false must reach the wire as an explicit param.
Omitting it lets the API default to sticky=true (the default when a
session is present), so the user could never disable proxy stickiness —
the bug behind the ipify "same IP across requests" report.
"""

from scrapfly import ScrapeConfig


def test_sticky_false_is_sent():
    cfg = ScrapeConfig(url="https://example.com", session="s1", session_sticky_proxy=False)
    assert cfg.to_api_params(key="x")["session_sticky_proxy"] == "false"


def test_sticky_true_is_sent():
    cfg = ScrapeConfig(url="https://example.com", session="s1", session_sticky_proxy=True)
    assert cfg.to_api_params(key="x")["session_sticky_proxy"] == "true"


def test_sticky_default_is_true():
    cfg = ScrapeConfig(url="https://example.com", session="s1")
    assert cfg.to_api_params(key="x")["session_sticky_proxy"] == "true"


def test_sticky_omitted_without_session():
    cfg = ScrapeConfig(url="https://example.com", session_sticky_proxy=True)
    assert "session_sticky_proxy" not in cfg.to_api_params(key="x")
