"""Live parity matrix: `asp` and `unblocker` must reach the API as one feature.

`tests/test_asp_unblocker_parity.py` proves the SDK *builds* the same request
under either name. That stops at the serializer. This module drives the real
SDK against a real API and reads the answer back off the wire: the API echoes
the parsed config in the response envelope under `config.asp` — the response
field keeps the old name deliberately, it is frozen — and that echoed value is
the observation.

# What each half of this file can and cannot prove

Be precise about this, because the obvious reading is wrong. Every Scrapfly SDK
collapses `unblocker` into the single stored `asp` slot BEFORE serializing
(`scrape_config.py:_resolve_unblocker`), and the wire key is frozen at `asp`.
So legs 1 and 2 put a BYTE-IDENTICAL request on the wire, and so do legs 3 and
4. The SDK matrix therefore proves:

    - the SDK folds both names onto one wire key, observed on the real
      outbound URL rather than re-derived from the serializer, and
    - the API accepts that request and reports the anti-bot state the caller
      asked for.

It does NOT prove the API still honours the `unblocker` spelling, because no
SDK leg ever sends that spelling. That is a real, separately-deployed code path
(`apps/scrapfly/api/scrapfly-api/pkg/scraper/config.go`: `asp := q.Get("asp");
if asp == "" { asp = q.Get("unblocker") }`), it is what a customer on a raw
HTTP client depends on, and the API silently ignores unrecognised query params
— so if that fallback were deleted, `unblocker=true` would quietly return an
UNPROTECTED, billed scrape.

`test_api_honours_the_unblocker_alias_on_the_wire` is the leg that covers it:
it bypasses the SDK's name folding and puts `unblocker=true` on the wire with
no `asp` key at all. Delete the API-side fallback and that test — and only
that test — goes red.

# The matrix

    1. unblocker=True    2. asp=True      -> anti-bot ENABLED, identically
    3. unblocker=False   4. asp=False     -> anti-bot DISABLED, identically
    5. raw `unblocker=true` on the wire   -> API-side alias, no SDK involved

Legs 1, 2 and 5 request the bypass. Each is a real scrape on a real account.
All five live in one module-scoped fixture; every assertion reads that one
cached result set, so adding a test costs nothing and no assertion failure can
trigger a re-scrape.

# Cost, measured rather than assumed

On this shieldless target the enabled legs cost the same as the disabled ones:
`context.cost` came back `{'total': 1, 'details': [PROXY_DATACENTER_NETWORK]}`
for an `unblocker=true` scrape of httpbin.dev, with no anti-bot line item. The
ASP surcharge is charged when a shield is actually engaged, which httpbin.dev
does not do. The five-leg cap and the no-retry rule are therefore discipline
about not hammering a live account, not a credit constraint — but the no-retry
rule still matters for a different reason: a retry would hide a genuine alias
failure behind a second attempt.

Set `SCRAPFLY_SKIP_BILLABLE=1` to run only the two cheap legs while debugging
the harness itself. The equivalence tests then SKIP rather than passing, so a
harness-only run can never be mistaken for a green alias verdict.

Two things keep the equivalence honest rather than vacuous:

  - Each leg must have SUCCEEDED (API 200 and upstream 200). Two legs that fail
    identically are not evidence the names are interchangeable.
  - The enabled pair and the disabled pair must DIFFER from each other. Without
    that, an API that echoed a constant would satisfy "leg 1 == leg 2" and
    "leg 3 == leg 4" while proving nothing.

Run:
    SCRAPFLY_KEY=scp-live-... SCRAPFLY_API_HOST=https://api.scrapfly.home \\
        pytest tests/test_asp_unblocker_parity_integration.py -v -s

Do NOT run this module under `pytest -n` without `--dist loadfile`: a
module-scoped fixture is instantiated once per xdist worker, so `-n 4` would
run the whole billable matrix four times. The fixture refuses to run on any
worker but the first rather than trusting the invocation.
"""

import contextlib
import logging
import os
from typing import Any, Dict, Optional
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

# Drives the live API; skipped by tests/conftest.py without credentials.
pytestmark = [pytest.mark.integration, pytest.mark.e2e]


from scrapfly import ScrapeConfig, ScrapflyClient
from scrapfly.api_response import ScrapeApiResponse


API_KEY = os.environ.get("SCRAPFLY_KEY", "")
API_HOST = os.environ.get("SCRAPFLY_API_HOST", "").rstrip("/")

# conftest.py skips this module when SCRAPFLY_KEY is unset. The host needs its
# own gate: there is deliberately no default here, because the only defaults
# available are wrong in opposite directions — a non-resolving placeholder
# turns a missing variable into a wall of red that reads like an alias
# regression, and api.scrapfly.io would point a dev key at production.
if API_KEY and not API_HOST:
    pytest.skip(
        "live API test: SCRAPFLY_KEY is set but SCRAPFLY_API_HOST is not, and this "
        "module has no safe default host — export SCRAPFLY_API_HOST to run",
        allow_module_level=True,
    )

# Small, stable, cheap, and shieldless: the target is the constant in this
# experiment, not the subject of it.
TARGET_URL = "https://httpbin.dev/html"

# The dev cluster serves a certificate signed by the Scrapfly Dev Root CA,
# which certifi does not carry. Pointing `verify` at that root keeps chain and
# hostname validation ON. `verify=False` is deliberately not used here: this
# suite exists to observe what the API answers, and a test that cannot tell the
# API apart from anything else holding the socket is worth less than it looks.
DEV_ROOT_CA = "/usr/local/share/ca-certificates/scrapfly-local-ca.crt"

# The dev project carries a user throttle rule on the target host
# (SLIDING_WINDOW, max_rate 5, max_concurrency 5, reported under
# `context.throttler`). Five sequential legs do not reliably fit in it, and the
# slot is not released the instant a response is handed back. Pacing keeps the
# matrix observable; it softens no assertion and re-sends no leg.
LEG_PACING_SECONDS = 12

# The echoed anti-bot value is a JSON boolean today. Accept the string spellings
# too so a serialization change surfaces as a parity failure rather than as a
# TypeError somewhere below.
_ENABLED = {True, "true", "True", 1}
_DISABLED = {False, "false", "False", 0, None}

LEGS = {
    "unblocker=True": {"unblocker": True},
    "asp=True": {"asp": True},
    "unblocker=False": {"unblocker": False},
    "asp=False": {"asp": False},
}

BILLABLE_LEGS = ("unblocker=True", "asp=True")
CHEAP_LEGS = ("unblocker=False", "asp=False")

RAW_ALIAS_LEG = "raw unblocker=true"

# Debug escape hatch: run the harness without spending the anti-bot legs. The
# tests that need them SKIP, so this can never read as a green alias verdict.
SKIP_BILLABLE = os.environ.get("SCRAPFLY_SKIP_BILLABLE") == "1"


def _tls_verify():
    """What to hand `ScrapflyClient(verify=...)`: a CA bundle, never a bypass."""
    bundle = os.environ.get("SCRAPFLY_CA_BUNDLE", DEV_ROOT_CA)

    # A checkout without the dev root (a laptop, or a run against
    # api.scrapfly.io) falls back to the system trust store, still verifying.
    return bundle if os.path.isfile(bundle) else True


def redact(text: str) -> str:
    """Strip the API key out of anything headed for test output.

    Every failure message below routes through here. A CI log is frequently
    world-readable and retained for months, and the key is on the query string
    of every URL this module touches — including the one inside a requests
    exception's own repr.
    """
    if not API_KEY:
        return text

    return text.replace(API_KEY, "scp-live-***REDACTED***")


def _install_log_redaction() -> None:
    """Redact the key out of every log record, not just this module's messages.

    The SDK's own retry logging is the leak that matters. `client.scrape` is
    wrapped in `@backoff.on_exception(..., max_tries=5)`, and on a network
    failure the `backoff` logger emits the requests exception verbatim — which
    embeds the full request URL, key included, five times per leg. Redacting
    only this module's assertion messages would leave that untouched in the
    captured-log section of a failing run.

    Installed at import rather than in a fixture: the records are emitted
    during fixture SETUP, and fixture ordering would not reliably get a
    redactor in place first.
    """
    if not API_KEY:
        return

    previous = logging.getLogRecordFactory()

    def factory(*args, **kwargs):
        record = previous(*args, **kwargs)
        if isinstance(record.msg, str):
            record.msg = redact(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {k: redact(str(v)) if API_KEY in str(v) else v for k, v in record.args.items()}
            else:
                record.args = tuple(
                    redact(str(a)) if API_KEY in str(a) else a for a in record.args
                )
        return record

    logging.setLogRecordFactory(factory)


_install_log_redaction()


@contextlib.contextmanager
def counting_http_requests():
    """Count every HTTP request that actually leaves the process.

    This has to sit BELOW the retry, not above it. `ScrapflyClient.scrape` is
    decorated with `@backoff.on_exception(backoff.expo, exception=NetworkError,
    max_tries=5)`, so one `scrape()` call can issue five real, separately
    billed scrapes. Counting `scrape()` invocations would report the number the
    matrix advertises no matter how many requests were charged for.

    `requests.sessions.Session.send` is the single choke point: the module-level
    `requests.request` the SDK uses without an open session builds a Session and
    calls it too.
    """
    original = requests.sessions.Session.send
    counter = {"sent": 0}

    def counting_send(self, *args, **kwargs):
        counter["sent"] += 1

        return original(self, *args, **kwargs)

    requests.sessions.Session.send = counting_send
    try:
        yield counter
    finally:
        requests.sessions.Session.send = original


def _is_throttle_refusal(error: BaseException) -> bool:
    """A throttle refusal is the API declining to produce a data point.

    Categorically different from a wrong answer: the scrape never executed, so
    it says nothing about either name. Reporting it as "leg asp=True FAILED"
    sends a reader off to debug an alias that is fine.
    """
    return "ERR::THROTTLE" in str(error) or "429" in str(error)


class Leg:
    """One run of the matrix, including the failure case.

    A leg that raises is recorded rather than propagated. Raising out of the
    module-scoped fixture would abort the other legs and report the failure as
    a setup error; recording it lets the success assertion name the leg and
    print the exception, which is what a real alias regression needs to look
    like.
    """

    def __init__(self, name: str, kwargs: Dict[str, Any]):
        self.name = name
        self.kwargs = kwargs
        self.response: Optional[ScrapeApiResponse] = None
        self.error: Optional[BaseException] = None
        self.skipped = False

    def run(self, client: ScrapflyClient) -> "Leg":
        config = ScrapeConfig(url=TARGET_URL, render_js=False, **self.kwargs)

        try:
            self.response = client.scrape(config)
        except BaseException as exc:  # noqa: BLE001 - recorded, asserted on below
            self.error = exc

        return self

    def skip(self, reason: str) -> "Leg":
        self.skipped = True
        self.skip_reason = reason

        return self

    @property
    def echoed_asp(self):
        """The anti-bot value the API says it parsed, from the response envelope."""
        return self.response.config.get("asp")

    @property
    def cost(self):
        """`context.cost`, so the cost claim in the docstring stays checkable."""
        return (self.response.context or {}).get("cost")

    @property
    def outbound_query(self) -> Dict[str, list]:
        """The query string the SDK actually put on the wire, key stripped."""
        query = parse_qs(urlsplit(self.response.request.url).query, keep_blank_values=True)
        query.pop("key", None)

        return query

    def __repr__(self) -> str:
        if self.skipped:
            return f"<Leg {self.name} SKIPPED: {self.skip_reason}>"

        if self.error is not None:
            return redact(f"<Leg {self.name} FAILED {type(self.error).__name__}: {self.error}>")

        return (
            f"<Leg {self.name} api={self.response.status_code} "
            f"upstream={self.response.upstream_status_code} "
            f"config.asp={self.echoed_asp!r} cost={self.cost}>"
        )


class RawLeg:
    """The API-side alias leg: `unblocker` on the wire, no SDK folding.

    This is the one leg whose failure means the customer-facing promise is
    broken. It does not use ScrapeConfig at all — ScrapeConfig cannot express
    it, because it resolves `unblocker` into `asp` at construction.
    """

    def __init__(self):
        self.name = RAW_ALIAS_LEG
        self.url: Optional[str] = None
        self.status: Optional[int] = None
        self.body: Optional[Dict[str, Any]] = None
        self.error: Optional[BaseException] = None
        self.skipped = False
        self.skip_reason = ""

    def run(self) -> "RawLeg":
        try:
            response = requests.get(
                f"{API_HOST}/scrape",
                # `unblocker` alone. No `asp` key: an `asp` of any value would
                # win the precedence rule server-side and the alias fallback
                # would never be reached.
                params={"key": API_KEY, "url": TARGET_URL, "unblocker": "true"},
                verify=_tls_verify(),
                timeout=180,
            )
            self.url = response.url
            self.status = response.status_code
            self.body = response.json()
        except BaseException as exc:  # noqa: BLE001 - recorded, asserted on below
            self.error = exc

        return self

    def skip(self, reason: str) -> "RawLeg":
        self.skipped = True
        self.skip_reason = reason

        return self

    @property
    def sent_query(self) -> Dict[str, list]:
        query = parse_qs(urlsplit(self.url).query, keep_blank_values=True)
        query.pop("key", None)

        return query

    @property
    def echoed_asp(self):
        return (self.body or {}).get("config", {}).get("asp")

    def __repr__(self) -> str:
        if self.skipped:
            return f"<Leg {self.name} SKIPPED: {self.skip_reason}>"

        if self.error is not None:
            return redact(f"<Leg {self.name} FAILED {type(self.error).__name__}: {self.error}>")

        return (
            f"<Leg {self.name} api={self.status} "
            f"config.asp={self.echoed_asp!r} sent={self.sent_query}>"
        )


@pytest.fixture(scope="module")
def matrix() -> Dict[str, Any]:
    """The five legs, scraped once for the whole module."""
    # A module-scoped fixture is instantiated once PER WORKER PROCESS, so
    # `pytest -n 4` would run this whole billable matrix four times without a
    # word of warning. Enforce the cost guarantee in the file rather than
    # trusting how someone happened to invoke pytest.
    worker = os.environ.get("PYTEST_XDIST_WORKER")
    if worker not in (None, "gw0"):
        pytest.skip(
            f"xdist worker {worker}: the billable matrix runs on gw0 only. Use "
            "`--dist loadfile` to keep this module on one worker."
        )

    import time

    client = ScrapflyClient(key=API_KEY, host=API_HOST, verify=_tls_verify())

    legs: Dict[str, Any] = {}
    dispatched = 0
    with counting_http_requests() as counter:
        for name, kwargs in LEGS.items():
            if name in BILLABLE_LEGS and SKIP_BILLABLE:
                legs[name] = Leg(name, kwargs).skip("SCRAPFLY_SKIP_BILLABLE=1")
                continue

            if dispatched > 0:
                time.sleep(LEG_PACING_SECONDS)
            dispatched += 1
            legs[name] = Leg(name, kwargs).run(client)

        if SKIP_BILLABLE:
            legs[RAW_ALIAS_LEG] = RawLeg().skip("SCRAPFLY_SKIP_BILLABLE=1")
        else:
            time.sleep(LEG_PACING_SECONDS)
            dispatched += 1
            legs[RAW_ALIAS_LEG] = RawLeg().run()

    legs["__cost__"] = {"dispatched": dispatched, "http_requests": counter["sent"]}

    # Printed under -s so the report can quote what the API actually echoed
    # rather than only that the assertions passed.
    print("\n--- asp/unblocker live matrix ---")
    for key, leg in legs.items():
        if key == "__cost__":
            continue
        print(f"  {leg.name:<20} {leg!r}")
    print(f"  {'HTTP requests':<20} {counter['sent']} on the wire for {dispatched} dispatched leg(s)")

    return legs


def _ok(leg) -> Any:
    """Guard: never assert equivalence across legs that did not succeed."""
    if leg.skipped:
        pytest.skip(f"leg {leg.name} not run: {leg.skip_reason}")

    if leg.error is not None and _is_throttle_refusal(leg.error):
        # Distinguishing this from a parity failure matters: the request never
        # reached the target, so it says nothing about either name. The dev
        # account carries a user throttle rule on httpbin.dev, and the suite
        # spends five requests against it. Re-running back to back will trip it.
        pytest.fail(
            redact(
                f"leg {leg.name} was THROTTLED before it ran, so this is an "
                f"environment limit and not an `asp`/`unblocker` divergence: {leg.error}"
            )
        )

    if leg.error is not None:
        # Deliberately pytest.fail rather than `assert leg.error is None`:
        # pytest rewrites the assert and prints the repr of the compared
        # object, which for a requests exception embeds the full request URL —
        # API key included — regardless of what the assertion message says.
        pytest.fail(redact(f"leg {leg.name} raised {type(leg.error).__name__}: {leg.error}"))

    return leg


# --- the request has to have worked at all --------------------------------


@pytest.mark.parametrize("name", list(LEGS))
def test_leg_succeeded(matrix: Dict[str, Any], name: str):
    """Both halves of every comparison below must be a real success.

    Without this, an API that rejected `unblocker` outright would still let
    "leg 1 matches leg 2" pass, because two identical failures compare equal.
    """
    leg = _ok(matrix[name])

    assert leg.response.status_code == 200, (
        f"{leg.name}: Scrapfly API answered {leg.response.status_code}, not 200"
    )
    assert leg.response.upstream_status_code == 200, (
        f"{leg.name}: upstream answered {leg.response.upstream_status_code}, not 200"
    )
    assert leg.response.scrape_success is True, f"{leg.name}: scrape reported unsuccessful"
    assert leg.response.error is None, redact(f"{leg.name}: {leg.response.error}")
    assert leg.response.content, f"{leg.name}: returned an empty body"


@pytest.mark.parametrize("name", list(LEGS))
def test_the_echoed_config_came_from_the_server(matrix: Dict[str, Any], name: str):
    """`config` must be the API's envelope, never the SDK's own config object.

    `ScrapeApiResponse.__init__` has a branch (api_response.py, `if
    self.scrape_config.method == 'HEAD'`) that SYNTHESIZES the whole envelope
    locally and sets `'config': self.scrape_config.__dict__`. Under that
    branch every assertion in this module would be reading back the value the
    test itself just wrote, and would pass unconditionally — including the
    distinguishability guard, because the SDK's own field does move with the
    flag. The matrix never sets `method`, so it takes the GET path; this pins
    that property instead of leaving it to the default.

    `uuid` and `request_id` are stamped by the API and are absent from
    `ScrapeConfig.__dict__`, so their presence is proof of provenance.
    """
    leg = _ok(matrix[name])

    assert leg.response.scrape_config.method != "HEAD", (
        f"{leg.name}: a HEAD request makes ScrapeApiResponse synthesize `config` "
        "from the SDK's own ScrapeConfig, so nothing below observes the API"
    )
    for stamped in ("uuid", "request_id"):
        assert stamped in leg.response.config, (
            f"{leg.name}: echoed config has no `{stamped}` — it does not look "
            "server-sourced, so the equivalence assertions observe nothing"
        )


# --- the API-side alias: the only leg that puts `unblocker` on the wire ---


def test_api_honours_the_unblocker_alias_on_the_wire(matrix: Dict[str, Any]):
    """`unblocker=true` alone, with no `asp` key, must enable the anti-bot.

    This is the leg the rest of the file cannot be: every SDK folds `unblocker`
    into `asp` before serializing, so no SDK leg ever shows the API the new
    name. The server-side fallback is a real, separately deployed line
    (pkg/scraper/config.go: `asp := q.Get("asp"); if asp == "" { asp =
    q.Get("unblocker") }`), and the API silently ignores query params it does
    not recognise — so if that line were deleted, `unblocker=true` would return
    an unprotected, billed scrape and every other test here would stay green.
    """
    leg = _ok(matrix[RAW_ALIAS_LEG])

    query = leg.sent_query
    assert query.get("unblocker") == ["true"], (
        f"harness error: this leg must put `unblocker` on the wire, sent {query!r}"
    )
    assert "asp" not in query, (
        f"harness error: an `asp` key wins the server-side precedence rule and "
        f"the alias fallback would never be reached; sent {query!r}"
    )

    assert leg.status == 200, redact(
        f"raw `unblocker=true` got HTTP {leg.status}: {str(leg.body)[:400]}"
    )
    assert leg.body["result"]["status_code"] == 200, (
        f"raw `unblocker=true`: upstream answered "
        f"{leg.body['result']['status_code']}, not 200"
    )
    assert leg.body["result"]["success"] is True, "raw `unblocker=true`: scrape unsuccessful"

    assert leg.echoed_asp in _ENABLED, (
        f"THE API-SIDE ALIAS IS BROKEN: a request carrying only `unblocker=true` "
        f"was parsed as config.asp={leg.echoed_asp!r}. A customer who migrated to "
        f"the new name on a raw HTTP client is being billed for an UNPROTECTED "
        f"scrape. uuid={leg.body.get('uuid')}"
    )


def test_the_alias_reaches_the_same_state_from_both_directions(matrix: Dict[str, Any]):
    """The SDK's `asp` wire key and the API's `unblocker` alias land together.

    The SDK legs prove the client's fold; the raw leg proves the server's
    fallback. This ties them: the two independent routes to "bypass on" must
    produce the same echoed value.
    """
    sdk = _ok(matrix["asp=True"])
    raw = _ok(matrix[RAW_ALIAS_LEG])

    assert sdk.echoed_asp == raw.echoed_asp, (
        f"SDK `asp=true` echoed config.asp={sdk.echoed_asp!r} but a raw "
        f"`unblocker=true` echoed {raw.echoed_asp!r} — the two spellings do not "
        "reach the same state at the API"
    )


# --- the equivalence itself, observed at the API --------------------------


def test_enabled_legs_report_the_feature_on(matrix: Dict[str, Any]):
    """unblocker=True and asp=True both come back with the anti-bot ENABLED."""
    unblocker, asp = _ok(matrix["unblocker=True"]), _ok(matrix["asp=True"])

    assert unblocker.echoed_asp in _ENABLED, (
        f"unblocker=True was parsed as config.asp={unblocker.echoed_asp!r}, not enabled"
    )
    assert asp.echoed_asp in _ENABLED, (
        f"asp=True was parsed as config.asp={asp.echoed_asp!r}, not enabled"
    )


def test_disabled_legs_report_the_feature_off(matrix: Dict[str, Any]):
    """unblocker=False and asp=False both come back with the anti-bot DISABLED."""
    unblocker, asp = _ok(matrix["unblocker=False"]), _ok(matrix["asp=False"])

    assert unblocker.echoed_asp in _DISABLED, (
        f"unblocker=False was parsed as config.asp={unblocker.echoed_asp!r}, not disabled"
    )
    assert asp.echoed_asp in _DISABLED, (
        f"asp=False was parsed as config.asp={asp.echoed_asp!r}, not disabled"
    )


@pytest.mark.parametrize("pair", [BILLABLE_LEGS, CHEAP_LEGS], ids=["enabled", "disabled"])
def test_the_two_names_echo_the_identical_value(matrix: Dict[str, Any], pair):
    """Not merely "both enabled" — the same value, byte for byte.

    `True` versus `"true"` would satisfy the membership checks above while
    meaning the two names took different paths through the parser.
    """
    left, right = _ok(matrix[pair[0]]), _ok(matrix[pair[1]])

    assert left.echoed_asp == right.echoed_asp and type(left.echoed_asp) is type(right.echoed_asp), (
        f"{left.name} echoed config.asp={left.echoed_asp!r} but "
        f"{right.name} echoed {right.echoed_asp!r}"
    )


def test_enabled_and_disabled_are_distinguishable(matrix: Dict[str, Any]):
    """The anti-vacuity guard for the two tests above.

    If the API echoed a constant, "leg 1 == leg 2" and "leg 3 == leg 4" would
    both hold and the matrix would prove nothing. The echoed value has to
    actually move when the flag moves.
    """
    on = _ok(matrix["unblocker=True"]).echoed_asp
    off = _ok(matrix["unblocker=False"]).echoed_asp

    assert on != off, (
        f"config.asp echoed {on!r} whether the feature was on or off — the "
        "response envelope is not reporting the parsed anti-bot state, so the "
        "equivalence assertions in this module are meaningless"
    )


def test_the_response_envelope_keeps_the_frozen_name(matrix: Dict[str, Any]):
    """`config.asp` is the echoed field under either input name; `unblocker`
    is not introduced into the envelope by using the new name."""
    for name in LEGS:
        leg = _ok(matrix[name])

        assert "asp" in leg.response.config, f"{leg.name}: response config has no `asp` key"
        assert "unblocker" not in leg.response.config, (
            f"{leg.name}: response config grew an `unblocker` key — the envelope "
            "field name is frozen"
        )


# --- what the SDK put on the wire ----------------------------------------


def test_wire_key_is_asp_and_never_unblocker(matrix: Dict[str, Any]):
    """The outbound query carries `asp`; `unblocker` never leaves the SDK.

    Published SDK versions are immutable and upgraded per installation. A build
    that emitted `unblocker` to an API deployment that had not learned it would
    silently drop a paid feature: the scrape succeeds, is billed, and comes back
    unprotected.

    Note what this asserts and what it does not: it pins the CLIENT's fold. It
    is `test_api_honours_the_unblocker_alias_on_the_wire`, not this test, that
    covers the server's half.
    """
    for name in LEGS:
        leg = _ok(matrix[name])
        query = leg.outbound_query

        assert "unblocker" not in query, (
            f"{leg.name}: `unblocker` reached the wire: "
            f"{redact(leg.response.request.url)}"
        )

        if name in BILLABLE_LEGS:
            assert query.get("asp") == ["true"], (
                f"{leg.name}: expected asp=true on the wire, got {query.get('asp')!r}"
            )
        else:
            # Off is expressed by omission, not by `asp=false`.
            assert "asp" not in query, (
                f"{leg.name}: expected no `asp` key when the feature is off, "
                f"got {query.get('asp')!r}"
            )


@pytest.mark.parametrize("pair", [BILLABLE_LEGS, CHEAP_LEGS], ids=["enabled", "disabled"])
def test_the_two_names_send_the_identical_request(matrix: Dict[str, Any], pair):
    """Whole-query equality, not a targeted `asp` check.

    A divergence the alias introduced somewhere else in the query string — an
    extra param under one name, a missing one under the other — is exactly the
    kind of thing a targeted assertion cannot see.
    """
    left, right = _ok(matrix[pair[0]]), _ok(matrix[pair[1]])

    assert left.outbound_query == right.outbound_query, (
        f"{left.name} sent {left.outbound_query!r} but {right.name} sent {right.outbound_query!r}"
    )


def test_the_matrix_cost_exactly_the_advertised_number_of_scrapes(matrix: Dict[str, Any]):
    """Counted at the socket, below the SDK's retry loop.

    `ScrapflyClient.scrape` is decorated with `@backoff.on_exception(backoff.expo,
    exception=NetworkError, max_tries=5)`, so a single leg can become five real,
    separately billed scrapes without the test noticing — the failure mode is a
    slow anti-bot scrape that trips a timeout and gets re-issued while the first
    is still running server-side. Counting `scrape()` calls would report the
    advertised number no matter what was charged; this counts
    `requests.Session.send`.
    """
    cost = matrix["__cost__"]

    assert cost["http_requests"] == cost["dispatched"], (
        f"the matrix dispatched {cost['dispatched']} leg(s) but put "
        f"{cost['http_requests']} HTTP requests on the wire — the SDK retry loop "
        f"re-issued {cost['http_requests'] - cost['dispatched']} real scrape(s), "
        "each one billed"
    )
