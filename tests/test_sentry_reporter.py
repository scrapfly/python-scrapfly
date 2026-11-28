import warnings

import pytest

sentry_sdk = pytest.importorskip("sentry_sdk")

from scrapfly.reporter.sentry import SentryReporter


class FakeResponse:
    config = {"project": "default", "env": "live", "url": "https://web-scraping.dev/products"}
    scrape_result = {
        "log_url": "https://scrapfly.io/dashboard/monitoring/log/01",
        "url": "https://web-scraping.dev/products",
        "status_code": 503,
    }
    error = {"code": "ERR::SCRAPE::BAD_UPSTREAM_RESPONSE"}


@pytest.fixture
def events():
    captured = []
    # before_send returns None (the result of list.append), so no event leaves the process.
    sentry_sdk.init(
        dsn="https://key@localhost/1",
        default_integrations=False,
        before_send=lambda event, hint: captured.append(event),
    )
    yield captured
    sentry_sdk.init()


def test_a_report_carries_the_scrape_tags_and_extras_with_its_exception(events):
    SentryReporter()(error=ValueError("boom"), scrape_api_response=FakeResponse())

    [event] = events
    assert event["exception"]["values"][-1]["type"] == "ValueError"
    assert event["tags"] == {
        "scrapfly_project": "default",
        "scrapfly_env": "live",
        "scrapfly_upstream_status_code": 503,
        "scrapfly_error_code": "ERR::SCRAPE::BAD_UPSTREAM_RESPONSE",
    }
    assert event["extra"]["scrape_config"] == FakeResponse.config
    assert event["extra"]["log_url"] == "https://scrapfly.io/dashboard/monitoring/log/01"
    assert event["extra"]["upstream_url"] == "https://web-scraping.dev/products"


def test_the_tags_of_a_report_stay_on_its_own_event(events):
    SentryReporter()(error=ValueError("boom"), scrape_api_response=FakeResponse())
    sentry_sdk.capture_message("after the report")

    report, after = events
    assert "scrapfly_error_code" in report["tags"]
    assert "scrapfly_error_code" not in after.get("tags", {})
    assert "log_url" not in after.get("extra", {})


def test_a_report_emits_no_deprecation_warning(events):
    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        SentryReporter()(error=ValueError("boom"), scrape_api_response=FakeResponse())

    assert len(events) == 1
