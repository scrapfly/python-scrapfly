"""Offline tests for the `unblocker` input name and its `asp` alias.

`unblocker` is the customer-facing name for the anti-bot bypass. `asp` is the
deprecated alias and keeps working forever, so both names have to be accepted
on input while exactly one key, `asp`, keeps going out on the wire.

The wire key matters more than it looks: published SDK versions are immutable
and upgraded per installation, so a build that emitted `unblocker` against an
API deployment that had not learned it yet would silently drop a paid feature.
The scrape would succeed, be billed, and return a blocked page. Several tests
here exist only to pin that key down.
"""

import base64

import pytest

from scrapfly import CrawlerConfig, ScrapeConfig

URL = "https://example.com"


def _params(**kwargs):
    return ScrapeConfig(url=URL, **kwargs).to_api_params(key="x")


# --- ScrapeConfig: input names -------------------------------------------


def test_unblocker_only_enables_the_feature():
    cfg = ScrapeConfig(url=URL, unblocker=True)
    assert cfg.asp is True
    assert _params(unblocker=True)["asp"] == "true"


def test_asp_only_still_enables_the_feature():
    cfg = ScrapeConfig(url=URL, asp=True)
    assert cfg.asp is True
    assert _params(asp=True)["asp"] == "true"


def test_both_names_agreeing_on_true():
    assert _params(asp=True, unblocker=True)["asp"] == "true"


def test_both_names_agreeing_on_false_stays_off():
    assert "asp" not in _params(asp=False, unblocker=False)


def test_conflict_asp_false_wins_over_unblocker_true():
    """An explicitly supplied `asp` always wins. Never OR the two names."""
    cfg = ScrapeConfig(url=URL, asp=False, unblocker=True)
    assert cfg.asp is False
    assert "asp" not in cfg.to_api_params(key="x")


def test_conflict_asp_true_wins_over_unblocker_false():
    cfg = ScrapeConfig(url=URL, asp=True, unblocker=False)
    assert cfg.asp is True
    assert cfg.to_api_params(key="x")["asp"] == "true"


def test_neither_name_defaults_off():
    cfg = ScrapeConfig(url=URL)
    assert cfg.asp is False
    assert cfg.unblocker is False
    assert "asp" not in cfg.to_api_params(key="x")


def test_unblocker_false_alone_turns_it_off():
    """`unblocker=False` must be distinguishable from "not supplied"."""
    cfg = ScrapeConfig(url=URL, unblocker=False)
    assert cfg.asp is False
    assert "asp" not in cfg.to_api_params(key="x")


# --- ScrapeConfig: wire key ----------------------------------------------


def test_wire_key_is_asp_not_unblocker():
    params = _params(unblocker=True)
    assert params["asp"] == "true"
    assert "unblocker" not in params


# --- ScrapeConfig: the property ------------------------------------------


def test_unblocker_reflects_asp():
    cfg = ScrapeConfig(url=URL, asp=True)
    assert cfg.unblocker is True


def test_setting_unblocker_updates_asp_and_the_wire():
    cfg = ScrapeConfig(url=URL)
    cfg.unblocker = True
    assert cfg.asp is True
    assert cfg.to_api_params(key="x")["asp"] == "true"


def test_setting_asp_updates_unblocker():
    cfg = ScrapeConfig(url=URL)
    cfg.asp = True
    assert cfg.unblocker is True


def test_unblocker_stays_out_of_instance_dict():
    """api_response.py serializes `scrape_config.__dict__` for HEAD requests.

    A second stored attribute would put a duplicate anti-bot key in that blob;
    a property does not.
    """
    cfg = ScrapeConfig(url=URL, unblocker=True)
    assert "unblocker" not in cfg.__dict__
    assert cfg.__dict__["asp"] is True


# --- ScrapeConfig: serialization -----------------------------------------


def test_to_dict_exports_asp():
    assert ScrapeConfig(url=URL, unblocker=True).to_dict()["asp"] is True


def test_to_dict_from_dict_round_trip_from_unblocker():
    cfg = ScrapeConfig(url=URL, unblocker=True)
    restored = ScrapeConfig.from_dict(cfg.to_dict())
    assert restored.asp is True
    assert restored.unblocker is True
    assert restored.to_api_params(key="x")["asp"] == "true"


def test_from_dict_accepts_unblocker_key():
    restored = ScrapeConfig.from_dict({"url": URL, "unblocker": True})
    assert restored.asp is True


def test_from_dict_accepts_asp_key():
    restored = ScrapeConfig.from_dict({"url": URL, "asp": True})
    assert restored.asp is True


def test_from_dict_conflict_asp_wins():
    restored = ScrapeConfig.from_dict({"url": URL, "asp": False, "unblocker": True})
    assert restored.asp is False


def test_from_dict_without_either_key_defaults_off():
    assert ScrapeConfig.from_dict({"url": URL}).asp is False


def _exported(**overrides) -> str:
    msgpack = pytest.importorskip("msgpack")

    data = {
        "url": URL,
        "retry": True,
        "headers": {},
        "session": None,
        "session_sticky_proxy": True,
        "cache": False,
        "cache_ttl": None,
        "cache_clear": False,
        "render_js": False,
        "method": "GET",
        "body": None,
        "ssl": False,
        "dns": False,
        "country": None,
        "debug": False,
        "correlation_id": None,
        "tags": [],
        "format": None,
        "js": None,
        "rendering_wait": None,
        "screenshots": None,
        "screenshot_flags": None,
        "proxy_pool": None,
        "auto_scroll": None,
        "cost_budget": None,
    }
    data.update(overrides)

    return base64.b64encode(msgpack.dumps(data)).decode("utf-8")


def test_from_exported_config_accepts_asp_key():
    cfg = ScrapeConfig.from_exported_config(_exported(asp=True))
    assert cfg.asp is True


def test_from_exported_config_accepts_unblocker_key():
    cfg = ScrapeConfig.from_exported_config(_exported(unblocker=True))
    assert cfg.asp is True
    assert cfg.to_api_params(key="x")["asp"] == "true"


def test_from_exported_config_without_either_key_does_not_raise():
    """The old code subscripted data['asp'] and would KeyError here."""
    cfg = ScrapeConfig.from_exported_config(_exported())
    assert cfg.asp is False


# --- ScrapeConfig: positional-argument stability --------------------------


def test_positional_arguments_keep_their_meaning():
    """`unblocker` is appended last, so positional callers must not shift.

    This fails loudly if anyone inserts the new parameter next to `asp`.
    """
    cfg = ScrapeConfig(
        URL,        # url
        False,      # retry
        "POST",     # method
        "fr",       # country
        True,       # render_js
        True,       # cache
        True,       # cache_clear
        True,       # ssl
        True,       # dns
        True,       # asp
    )
    assert cfg.url == URL
    assert cfg.retry is False
    assert cfg.method == "POST"
    assert cfg.country == "fr"
    assert cfg.render_js is True
    assert cfg.cache is True
    assert cfg.cache_clear is True
    assert cfg.ssl is True
    assert cfg.dns is True
    assert cfg.asp is True


# --- CrawlerConfig --------------------------------------------------------


def test_crawler_unblocker_only_emits_asp():
    params = CrawlerConfig(url=URL, unblocker=True).to_api_params()
    assert params["asp"] is True
    assert "unblocker" not in params


def test_crawler_asp_only_still_works():
    assert CrawlerConfig(url=URL, asp=True).to_api_params()["asp"] is True


def test_crawler_both_names_agreeing():
    assert CrawlerConfig(url=URL, asp=True, unblocker=True).to_api_params()["asp"] is True


def test_crawler_conflict_asp_false_wins():
    assert "asp" not in CrawlerConfig(url=URL, asp=False, unblocker=True).to_api_params()


def test_crawler_conflict_asp_true_wins():
    assert CrawlerConfig(url=URL, asp=True, unblocker=False).to_api_params()["asp"] is True


def test_crawler_neither_name_defaults_off():
    cfg = CrawlerConfig(url=URL)
    assert "asp" not in cfg.to_api_params()
    assert cfg.unblocker is False
    assert cfg.asp is False


def test_crawler_unblocker_reflects_asp_both_ways():
    cfg = CrawlerConfig(url=URL, asp=True)
    assert cfg.unblocker is True

    cfg.unblocker = False
    assert cfg.asp is False
    assert "asp" not in cfg.to_api_params()

    cfg.asp = True
    assert cfg.unblocker is True
    assert cfg.to_api_params()["asp"] is True


def test_crawler_multipart_body_keeps_asp_key():
    """POST /crawl sends the config as a JSON part; the key stays `asp` there too."""
    parts = CrawlerConfig(url=URL, unblocker=True).to_multipart_parts()
    assert parts["config"]["asp"] is True
    assert "unblocker" not in parts["config"]


def test_crawler_positional_url_still_first():
    assert CrawlerConfig(URL).to_api_params()["url"] == URL
