"""Offline serialization tests for session_sticky_proxy.

session_sticky_proxy=false must reach the wire as an explicit param.
Omitting it lets the API default to sticky=true (the default when a
session is present), so the user could never disable proxy stickiness —
the bug behind the ipify "same IP across requests" report.

Left unset, the param stays off the wire and out of the "ignored" warning:
only a value the caller passed is sent, or warned about without a session.
"""

import logging

import pytest

from scrapfly import ScrapeConfig


def _sticky_warnings(caplog) -> list:
    return [r for r in caplog.records if r.levelno == logging.WARNING and 'session_sticky_proxy' in r.getMessage()]


def test_sticky_false_is_sent():
    cfg = ScrapeConfig(url="https://example.com", session="s1", session_sticky_proxy=False)
    assert cfg.to_api_params(key="x")["session_sticky_proxy"] == "false"


def test_sticky_true_is_sent():
    cfg = ScrapeConfig(url="https://example.com", session="s1", session_sticky_proxy=True)
    assert cfg.to_api_params(key="x")["session_sticky_proxy"] == "true"


def test_sticky_default_is_left_to_api():
    cfg = ScrapeConfig(url="https://example.com", session="s1")
    assert "session_sticky_proxy" not in cfg.to_api_params(key="x")


def test_sticky_omitted_without_session():
    cfg = ScrapeConfig(url="https://example.com", session_sticky_proxy=True)
    assert "session_sticky_proxy" not in cfg.to_api_params(key="x")


def test_no_warning_without_session_by_default(caplog):
    caplog.set_level(logging.WARNING)
    ScrapeConfig(url="https://example.com").to_api_params(key="x")
    assert _sticky_warnings(caplog) == []


@pytest.mark.parametrize("sticky", [True, False])
def test_warning_when_set_without_session(caplog, sticky):
    caplog.set_level(logging.WARNING)
    ScrapeConfig(url="https://example.com", session_sticky_proxy=sticky).to_api_params(key="x")
    assert len(_sticky_warnings(caplog)) == 1


@pytest.mark.parametrize("sticky", [None, True, False])
def test_dict_round_trip_keeps_sticky(sticky):
    cfg = ScrapeConfig(url="https://example.com", session="s1", session_sticky_proxy=sticky)
    restored = ScrapeConfig.from_dict(cfg.to_dict())
    assert restored.session_sticky_proxy is sticky
    assert restored.to_api_params(key="x") == cfg.to_api_params(key="x")
