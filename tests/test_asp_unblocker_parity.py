"""Parity matrix: `asp` and `unblocker` must behave EXACTLY the same.

`tests/test_scrape_config_unblocker.py` proves each name works. That is not the
same guarantee. A customer migrating from `asp` to `unblocker` relies on the two
names being interchangeable *everywhere*, and a targeted assertion like
`params['asp'] == 'true'` cannot see a divergence in any other field: a query
param that only one path emits, a key present under one name and absent under
the other, a different serialized body, a different stored attribute.

So the equivalence tests here compare the WHOLE emitted output — the entire
query-param dict, the entire request body, the entire instance dict — between
two configs that differ only in which input name was used. Whole-output
comparison is the point; it is what turns "the flag is set" into "the two names
are the same request".

The rest is the full truth table with both names present, the wire-key pin
(`asp` goes out, `unblocker` never does), and post-construction parity for the
SDKs' mutable views of the one stored value.

On the sentinel: the parameters default to `_UNSET`, so "not supplied" is a
distinct state from an explicit `False`. Every "not supplied" row below omits
the kwarg entirely — passing `False` would be a different row of this table.
Unlike Go, whose zero-value `bool` cannot express the distinction, Python has
no language-forced exception here: all nine rows are expressible and all nine
are pinned.
"""

import base64
import copy

import pytest

from scrapfly import CrawlerConfig, ScrapeConfig
from scrapfly.scrape_config import Format, FormatOption, ScreenshotFlag

URL = "https://example.com"
KEY = "scp-test-key"


# --- fixtures: configs that differ ONLY in the anti-bot input name --------

# A deliberately loaded config. Whole-output equality is only worth asserting
# when the output has many fields to diverge in; an almost-empty config would
# make the comparison pass for the wrong reason.
_LOADED_SCRAPE = dict(
    retry=False,
    method="POST",
    country="fr",
    render_js=True,
    cache=True,
    cache_clear=True,
    cache_ttl=120,
    ssl=True,
    dns=True,
    debug=True,
    proxy_pool="public_residential_pool",
    session="sess-1",
    session_sticky_proxy=False,
    tags=["alpha", "beta"],
    format=Format.MARKDOWN,
    format_options=[FormatOption.NO_IMAGES],
    correlation_id="corr-1",
    cookies={"cart": "42"},
    body="a=1",
    headers={"x-parity": "1"},
    js="return 1",
    rendering_wait=100,
    rendering_stage="domcontentloaded",
    wait_for_selector="#main",
    screenshots={"main": "fullpage"},
    screenshot_flags=[ScreenshotFlag.LOAD_IMAGES],
    webhook="wh-1",
    timeout=30000,
    js_scenario=[{"click": {"selector": "#a"}}],
    extract={"template": "x"},
    lang=["fr"],
    os="linux",
    auto_scroll=True,
    cost_budget=100,
    browser_brand="chromium",
    geolocation="48.85,2.35",
    proxified_response=True,
)

_LOADED_CRAWLER = dict(
    page_limit=100,
    max_depth=3,
    max_duration=600,
    exclude_paths=["/admin"],
    ignore_base_path_restriction=True,
    follow_external_links=True,
    allowed_external_domains=["cdn.example.com"],
    follow_internal_subdomains=False,
    allowed_internal_subdomains=["blog.example.com"],
    headers={"x-parity": "1"},
    delay=250,
    user_agent="parity/1.0",
    max_concurrency=4,
    rendering_delay=500,
    use_sitemaps=True,
    respect_robots_txt=False,
    ignore_no_follow=True,
    cache=True,
    cache_ttl=60,
    cache_clear=True,
    content_formats=["markdown", "html"],
    extraction_rules={"title": "h1"},
    search=True,
    refresh=True,
    refresh_interval=7200,
    proxy_pool="public_residential_pool",
    country="fr",
    webhook_name="wh-1",
    webhook_events=[CrawlerConfig.WEBHOOK_CRAWLER_FINISHED],
    max_api_credit=1000,
)


def _scrape(loaded: bool = False, **anti_bot) -> ScrapeConfig:
    """Build a ScrapeConfig; `anti_bot` kwargs are passed through verbatim.

    Omitting the kwarg is how "not supplied" is expressed — never `False`.
    """

    kwargs = dict(_LOADED_SCRAPE) if loaded else {}
    kwargs.update(anti_bot)

    return ScrapeConfig(url=URL, **kwargs)


def _crawler(loaded: bool = False, **anti_bot) -> CrawlerConfig:
    kwargs = dict(_LOADED_CRAWLER) if loaded else {}
    kwargs.update(anti_bot)

    return CrawlerConfig(url=URL, **kwargs)


# A whole-output comparison is only as strong as the output has fields to
# diverge in. If a fixture is ever trimmed, or a serializer regresses to
# emitting almost nothing, every equality below would still pass while claiming
# to compare "the ENTIRE map". This floor is what stops that: the Go SDK's
# matrix carries the same guard (`len(legacy) < 25`).
_MIN_LOADED_KEYS = 25


def _assert_not_vacuous(emitted, what: str):
    assert len(emitted) >= _MIN_LOADED_KEYS, (
        f"{what} emits only {len(emitted)} keys ({sorted(emitted)}); a whole-output "
        f"comparison over that proves almost nothing. Expected at least "
        f"{_MIN_LOADED_KEYS} from the loaded fixture."
    )


# --- 1. EQUIVALENCE: whole emitted output, the two names side by side -----


@pytest.mark.parametrize("value", [True, False], ids=["enabled", "disabled"])
@pytest.mark.parametrize("loaded", [False, True], ids=["minimal", "loaded"])
def test_scrape_query_params_identical_under_both_names(value, loaded):
    """The ENTIRE query-param map, not just the `asp` key."""

    by_asp = _scrape(loaded, asp=value).to_api_params(key=KEY)
    by_unblocker = _scrape(loaded, unblocker=value).to_api_params(key=KEY)

    if loaded:
        _assert_not_vacuous(by_asp, "loaded scrape query params")

    assert by_asp == by_unblocker


@pytest.mark.parametrize("value", [True, False], ids=["enabled", "disabled"])
@pytest.mark.parametrize("loaded", [False, True], ids=["minimal", "loaded"])
def test_scrape_to_dict_identical_under_both_names(value, loaded):
    """`to_dict` is what round-trips through `from_dict` and the export path."""

    assert _scrape(loaded, asp=value).to_dict() == _scrape(loaded, unblocker=value).to_dict()


@pytest.mark.parametrize("value", [True, False], ids=["enabled", "disabled"])
@pytest.mark.parametrize("loaded", [False, True], ids=["minimal", "loaded"])
def test_scrape_instance_dict_identical_under_both_names(value, loaded):
    """`api_response.py` serializes `scrape_config.__dict__` for HEAD requests.

    Two stored attributes instead of one property would show up right here as
    a key present under one name and missing under the other.
    """

    assert _scrape(loaded, asp=value).__dict__ == _scrape(loaded, unblocker=value).__dict__


@pytest.mark.parametrize("value", [True, False], ids=["enabled", "disabled"])
@pytest.mark.parametrize("loaded", [False, True], ids=["minimal", "loaded"])
def test_crawler_body_identical_under_both_names(value, loaded):
    """The ENTIRE POST /crawl body."""

    by_asp = _crawler(loaded, asp=value).to_api_params()
    by_unblocker = _crawler(loaded, unblocker=value).to_api_params()

    if loaded:
        _assert_not_vacuous(by_asp, "loaded crawler body")

    assert by_asp == by_unblocker


@pytest.mark.parametrize("value", [True, False], ids=["enabled", "disabled"])
def test_crawler_body_with_key_identical_under_both_names(value):
    assert _crawler(True, asp=value).to_api_params(key=KEY) == _crawler(True, unblocker=value).to_api_params(key=KEY)


@pytest.mark.parametrize("value", [True, False], ids=["enabled", "disabled"])
@pytest.mark.parametrize("loaded", [False, True], ids=["minimal", "loaded"])
def test_crawler_multipart_parts_identical_under_both_names(value, loaded):
    """The multipart form is a second, independent serializer of the same config."""

    assert _crawler(loaded, asp=value).to_multipart_parts() == _crawler(loaded, unblocker=value).to_multipart_parts()


@pytest.mark.parametrize("value", [True, False], ids=["enabled", "disabled"])
def test_crawler_url_list_multipart_identical_under_both_names(value):
    """`url_list` splits the body in two; both halves must still match."""

    by_asp = CrawlerConfig(url_list=[URL, URL + "/b"], asp=value).to_multipart_parts()
    by_unblocker = CrawlerConfig(url_list=[URL, URL + "/b"], unblocker=value).to_multipart_parts()

    assert by_asp == by_unblocker


@pytest.mark.parametrize("value", [True, False], ids=["enabled", "disabled"])
def test_scrape_from_dict_identical_under_both_keys(value):
    """Same guarantee on the deserialization path: `{'asp': x}` vs `{'unblocker': x}`."""

    # `screenshots` is passed explicitly: `from_dict` defaults it to `[]`, and
    # `to_api_params` then calls `.items()` on that list under render_js. That
    # defect is name-independent (it fires with neither name supplied) and so
    # is out of scope here.
    base = {
        "url": URL,
        "render_js": True,
        "country": "fr",
        "cache": True,
        "screenshots": {"main": "fullpage"},
    }

    by_asp = ScrapeConfig.from_dict({**base, "asp": value})
    by_unblocker = ScrapeConfig.from_dict({**base, "unblocker": value})

    assert by_asp.to_api_params(key=KEY) == by_unblocker.to_api_params(key=KEY)
    assert by_asp.to_dict() == by_unblocker.to_dict()


@pytest.mark.parametrize("value", [True, False], ids=["enabled", "disabled"])
def test_scrape_round_trip_identical_under_both_names(value):
    """Construct under each name, export, re-import: still the same request."""

    by_asp = ScrapeConfig.from_dict(_scrape(True, asp=value).to_dict())
    by_unblocker = ScrapeConfig.from_dict(_scrape(True, unblocker=value).to_dict())

    _assert_not_vacuous(by_asp.to_api_params(key=KEY), "round-tripped scrape query params")

    assert by_asp.to_api_params(key=KEY) == by_unblocker.to_api_params(key=KEY)
    assert by_asp.to_dict() == by_unblocker.to_dict()


_EXPORT_BASE = {
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


def _exported(**overrides) -> str:
    msgpack = pytest.importorskip("msgpack")

    data = copy.deepcopy(_EXPORT_BASE)
    data.update(overrides)

    return base64.b64encode(msgpack.dumps(data)).decode("utf-8")


@pytest.mark.parametrize("value", [True, False], ids=["enabled", "disabled"])
def test_scrape_from_exported_config_identical_under_both_keys(value):
    by_asp = ScrapeConfig.from_exported_config(_exported(asp=value))
    by_unblocker = ScrapeConfig.from_exported_config(_exported(unblocker=value))

    assert by_asp.to_api_params(key=KEY) == by_unblocker.to_api_params(key=KEY)
    assert by_asp.to_dict() == by_unblocker.to_dict()


# --- 2. THE FULL TRUTH TABLE, both names present -------------------------

# (id, constructor kwargs, resolved value)
#
# Precedence: an explicitly supplied `asp` wins; `unblocker` is consulted only
# when `asp` was not supplied. The two names are NEVER OR-ed — that is what the
# two conflict rows exist to pin.
#
# "not supplied" is an ABSENT kwarg, never `False`. The exception is the `None`
# block at the end: `None` is a THIRD spelling of "not supplied", accepted
# because the API says so and because forwarding depends on it (see
# `_resolve_unblocker`).
#
# CROSS-SDK NOTE on the two conflict rows. Python, TypeScript and Rust all
# resolve `asp=False, unblocker=True` to OFF, as pinned here. GO ANSWERS ON for
# that one row: its `ASP` field is a plain `bool`, so a supplied `false` is
# byte-identical to the zero value and cannot be honoured. That divergence is
# documented in go/unblocker.go and go/README.md, and the Go test row that pins
# it is named GO_LANGUAGE_FORCED_EXCEPTION_documented_divergence_not_a_bug. It
# is the ONLY cell where the four SDKs disagree; nothing else in this table may
# be "fixed" to match Go.
TRUTH_TABLE = [
    ("neither-supplied", {}, False),
    ("unblocker-only-true", {"unblocker": True}, True),
    ("unblocker-only-false", {"unblocker": False}, False),
    ("asp-only-true", {"asp": True}, True),
    ("asp-only-false", {"asp": False}, False),
    ("both-true", {"asp": True, "unblocker": True}, True),
    ("both-false", {"asp": False, "unblocker": False}, False),
    ("conflict-asp-false-beats-unblocker-true", {"asp": False, "unblocker": True}, False),
    ("conflict-asp-true-beats-unblocker-false", {"asp": True, "unblocker": False}, True),
    # `None` is NOT a supplied value — the same reading the API takes
    # (its alias resolution treats an absent key, null and
    # "" alike) and the same one TypeScript's `??` takes for `undefined`. These
    # rows are the ones that make `ScrapeConfig(**{**opts, "asp": opts.get("asp")})`
    # safe: a forwarded absent key must not veto an explicit `unblocker=True`.
    ("asp-null-is-not-supplied-unblocker-decides", {"asp": None, "unblocker": True}, True),
    ("asp-null-is-not-supplied-unblocker-false", {"asp": None, "unblocker": False}, False),
    ("asp-null-alone-defaults-off", {"asp": None}, False),
    ("unblocker-null-alone-defaults-off", {"unblocker": None}, False),
    ("both-null-defaults-off", {"asp": None, "unblocker": None}, False),
    # A supplied `asp` still beats a null `unblocker`, in both directions.
    ("asp-true-beats-unblocker-null", {"asp": True, "unblocker": None}, True),
    ("asp-false-beats-unblocker-null", {"asp": False, "unblocker": None}, False),
]

_ROWS = [pytest.param(kwargs, expected, id=name) for name, kwargs, expected in TRUTH_TABLE]


@pytest.mark.parametrize("kwargs,expected", _ROWS)
def test_scrape_truth_table(kwargs, expected):
    cfg = _scrape(**kwargs)

    # Resolved outcome, under both readable names.
    assert cfg.asp is expected
    assert cfg.unblocker is expected

    # Emitted wire key.
    params = cfg.to_api_params(key=KEY)
    if expected:
        assert params["asp"] == "true"
    else:
        assert "asp" not in params
    assert "unblocker" not in params


@pytest.mark.parametrize("kwargs,expected", _ROWS)
def test_crawler_truth_table(kwargs, expected):
    cfg = _crawler(**kwargs)

    assert cfg.asp is expected
    assert cfg.unblocker is expected

    params = cfg.to_api_params()
    if expected:
        assert params["asp"] is True
    else:
        assert "asp" not in params
    assert "unblocker" not in params

    assert cfg.to_multipart_parts()["config"] == params


@pytest.mark.parametrize("kwargs,expected", _ROWS)
def test_scrape_from_dict_truth_table(kwargs, expected):
    """Same table on the deserialization path, keyed exactly as constructed."""

    cfg = ScrapeConfig.from_dict({"url": URL, **kwargs})

    assert cfg.asp is expected
    assert cfg.unblocker is expected
    assert cfg.to_dict()["asp"] is expected
    assert "unblocker" not in cfg.to_dict()

    params = cfg.to_api_params(key=KEY)
    assert params.get("asp") == ("true" if expected else None)
    assert "unblocker" not in params


@pytest.mark.parametrize("kwargs,expected", _ROWS)
def test_scrape_from_exported_config_truth_table(kwargs, expected):
    cfg = ScrapeConfig.from_exported_config(_exported(**kwargs))

    assert cfg.asp is expected
    assert cfg.unblocker is expected
    assert cfg.to_api_params(key=KEY).get("asp") == ("true" if expected else None)


def test_python_sentinel_separates_omitted_from_explicit_false_no_language_exception():
    """Python needs no language-forced exception row; Go's plain bool does.

    The `_UNSET` sentinel makes "asp not supplied" a different state from
    "asp=False", which is exactly what these two rows of the table depend on:
    same `unblocker=True`, opposite outcome. If the sentinel ever collapsed
    into `False`, both rows would resolve the same way and precedence would be
    unimplementable.
    """

    assert _scrape(unblocker=True).asp is True
    assert _scrape(asp=False, unblocker=True).asp is False


# --- 3. WIRE KEY ----------------------------------------------------------


@pytest.mark.parametrize("kwargs,expected", _ROWS)
@pytest.mark.parametrize("loaded", [False, True], ids=["minimal", "loaded"])
def test_unblocker_never_appears_on_the_wire(kwargs, expected, loaded):
    """Emitting the new name, or both names, is a defect.

    Published SDK versions are immutable and upgraded per installation: a build
    that sent `unblocker` to an API deployment that had not learned it yet would
    silently drop a paid feature — the scrape succeeds, is billed, and returns a
    blocked page.
    """

    scrape_params = _scrape(loaded, **kwargs).to_api_params(key=KEY)
    crawler = _crawler(loaded, **kwargs)
    crawler_params = crawler.to_api_params(key=KEY)
    crawler_config_part = crawler.to_multipart_parts()["config"]

    for name, emitted in (
        ("scrape query params", scrape_params),
        ("crawler body", crawler_params),
        ("crawler multipart config", crawler_config_part),
    ):
        assert not [k for k in emitted if "unblocker" in k], f"`unblocker` leaked into {name}"

        if expected:
            assert "asp" in emitted, f"anti-bot flag lost from {name}"
        else:
            assert "asp" not in emitted, f"anti-bot flag wrongly emitted in {name}"


def test_wire_key_count_is_exactly_one():
    """Exactly one anti-bot key goes out, never a duplicate pair."""

    for emitted in (
        _scrape(True, unblocker=True).to_api_params(key=KEY),
        _crawler(True, unblocker=True).to_api_params(key=KEY),
        _crawler(True, unblocker=True).to_multipart_parts()["config"],
    ):
        assert [k for k in emitted if k in ("asp", "unblocker")] == ["asp"]


# --- 4. POST-CONSTRUCTION PARITY -----------------------------------------


@pytest.mark.parametrize("value", [True, False], ids=["enabled", "disabled"])
@pytest.mark.parametrize("write", ["asp", "unblocker"])
def test_scrape_post_construction_write_visible_under_both_names(write, value):
    """The two names are two views of one stored attribute, in both directions."""

    cfg = _scrape(True, asp=not value)
    setattr(cfg, write, value)

    assert cfg.asp is value
    assert cfg.unblocker is value

    # And the mutation reaches the wire, identically to constructing that way.
    assert cfg.to_api_params(key=KEY) == _scrape(True, asp=value).to_api_params(key=KEY)


@pytest.mark.parametrize("value", [True, False], ids=["enabled", "disabled"])
@pytest.mark.parametrize("write", ["asp", "unblocker"])
def test_crawler_post_construction_write_visible_under_both_names(write, value):
    cfg = _crawler(True, asp=not value)
    setattr(cfg, write, value)

    assert cfg.asp is value
    assert cfg.unblocker is value

    assert cfg.to_api_params() == _crawler(True, asp=value).to_api_params()
    assert cfg.to_multipart_parts() == _crawler(True, asp=value).to_multipart_parts()


@pytest.mark.parametrize("write", ["asp", "unblocker"])
def test_scrape_post_construction_toggle_changes_the_wire(write):
    cfg = _scrape()
    assert "asp" not in cfg.to_api_params(key=KEY)

    setattr(cfg, write, True)
    assert cfg.to_api_params(key=KEY)["asp"] == "true"

    setattr(cfg, write, False)
    assert "asp" not in cfg.to_api_params(key=KEY)


@pytest.mark.parametrize("write", ["asp", "unblocker"])
def test_crawler_post_construction_toggle_changes_the_wire(write):
    cfg = _crawler()
    assert "asp" not in cfg.to_api_params()

    setattr(cfg, write, True)
    assert cfg.to_api_params()["asp"] is True

    setattr(cfg, write, False)
    assert "asp" not in cfg.to_api_params()
    assert "unblocker" not in cfg.to_api_params()


@pytest.mark.parametrize("write", ["asp", "unblocker"])
def test_scrape_post_construction_write_stays_out_of_instance_dict(write):
    """Writing through either name must not sprout a second stored key."""

    cfg = _scrape()
    setattr(cfg, write, True)

    assert "unblocker" not in cfg.__dict__
    assert cfg.__dict__["asp"] is True


# --- 5. SAME-OUTCOME INDISTINGUISHABILITY ---------------------------------
#
# Stronger than the per-row assertions above: every row that RESOLVES to the
# same outcome must produce the same WHOLE output, whichever name (or pair of
# names, or `None`) got the caller there. A per-row assertion on the `asp` key
# would still pass if two rows agreed on the toggle and disagreed on some other
# field; this cannot. Ported from the Rust matrix
# (`unblocker_matrix_rows_with_the_same_outcome_are_indistinguishable`) so all
# four SDKs make the claim in its strongest form.


@pytest.mark.parametrize("expected", [True, False], ids=["enabled", "disabled"])
def test_scrape_rows_with_the_same_outcome_are_indistinguishable(expected):
    rows = [(name, kwargs) for name, kwargs, want in TRUTH_TABLE if want is expected]
    assert len(rows) >= 3, "the grouping is only meaningful with several rows per outcome"

    first_name, first_kwargs = rows[0]
    baseline = _scrape(True, **first_kwargs).to_api_params(key=KEY)
    _assert_not_vacuous(baseline, "loaded scrape query params")

    for name, kwargs in rows[1:]:
        assert _scrape(True, **kwargs).to_api_params(key=KEY) == baseline, (
            f"row {name!r} diverges from {first_name!r} although both resolve to {expected}"
        )


@pytest.mark.parametrize("expected", [True, False], ids=["enabled", "disabled"])
def test_crawler_rows_with_the_same_outcome_are_indistinguishable(expected):
    rows = [(name, kwargs) for name, kwargs, want in TRUTH_TABLE if want is expected]

    first_name, first_kwargs = rows[0]
    baseline = _crawler(True, **first_kwargs).to_api_params()
    baseline_multipart = _crawler(True, **first_kwargs).to_multipart_parts()
    _assert_not_vacuous(baseline, "loaded crawler body")

    for name, kwargs in rows[1:]:
        cfg = _crawler(True, **kwargs)
        assert cfg.to_api_params() == baseline, (
            f"row {name!r} diverges from {first_name!r} although both resolve to {expected}"
        )
        assert cfg.to_multipart_parts() == baseline_multipart, (
            f"row {name!r} diverges from {first_name!r} in the multipart form"
        )


# --- 6. CLIENT LAYER ------------------------------------------------------
#
# Every assertion above stops at the config serializer. Nothing in the SDK
# pinned that the key survives the CLIENT: a whitelist, a rename shim or a
# re-serialization between `to_api_params()` and the outgoing request would
# leave the whole matrix green while the wire lost the flag. One test per SDK
# closes that, by capturing what the client actually hands the transport.


class _CapturedRequest(Exception):
    """Raised by the stub transport once it has recorded the request."""

    def __init__(self, kwargs):
        super().__init__("captured")
        self.kwargs = kwargs


def _capture_scrape_request(cfg: ScrapeConfig) -> dict:
    from scrapfly import ScrapflyClient

    client = ScrapflyClient(key=KEY, host="https://api.scrapfly.io")

    def transport(**kwargs):
        raise _CapturedRequest(kwargs)

    # `_http_handler` is a cached_property, so seeding __dict__ replaces the
    # real requests call before it is ever built. Nothing touches the network.
    client.__dict__["_http_handler"] = transport

    with pytest.raises(_CapturedRequest) as raised:
        client.scrape(cfg)

    return raised.value.kwargs


@pytest.mark.parametrize("name", ["asp", "unblocker"])
def test_client_sends_the_asp_wire_key_under_either_input_name(name):
    params = _capture_scrape_request(_scrape(True, **{name: True}))["params"]

    assert params["asp"] == "true"
    assert "unblocker" not in params
    _assert_not_vacuous(params, "client-issued scrape query params")


@pytest.mark.parametrize("name", ["asp", "unblocker"])
def test_client_omits_the_key_when_the_feature_is_off(name):
    params = _capture_scrape_request(_scrape(True, **{name: False}))["params"]

    assert "asp" not in params
    assert "unblocker" not in params


def test_client_request_is_identical_under_both_names():
    """The WHOLE request the client hands the transport, not just the params."""

    by_asp = _capture_scrape_request(_scrape(True, asp=True))
    by_unblocker = _capture_scrape_request(_scrape(True, unblocker=True))

    assert by_asp == by_unblocker


# --- 7. ERROR SURFACE -----------------------------------------------------


def test_unblocker_error_is_the_same_class_as_the_asp_error():
    """The rename reached the error surface too, as an alias and not a subclass.

    Go exposes `ErrUnblockerBypassFailed` and TypeScript `ScrapflyUnblockerError`
    for the same failure; a customer who renamed the config parameter reasonably
    reaches for the matching error name. An alias keeps every existing
    `except ScrapflyAspError` catching exactly what it caught before.
    """

    import scrapfly
    from scrapfly.errors import ScrapflyAspError, ScrapflyUnblockerError

    assert ScrapflyUnblockerError is ScrapflyAspError
    assert scrapfly.ScrapflyUnblockerError is ScrapflyAspError
    assert "ScrapflyUnblockerError" in scrapfly.__all__

    # Catching under either name catches the other, in both directions.
    def _raised():
        return ScrapflyUnblockerError(
            request=None,
            response=None,
            message="shield failed",
            code="ERR::ASP::SHIELD_PROTECTION_FAILED",
            http_status_code=422,
        )

    with pytest.raises(ScrapflyAspError):
        raise _raised()
    with pytest.raises(ScrapflyUnblockerError):
        raise _raised()
    assert issubclass(ScrapflyUnblockerError, ScrapflyAspError)
    assert issubclass(ScrapflyAspError, ScrapflyUnblockerError)
