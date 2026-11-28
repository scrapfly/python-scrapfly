import pytest

sentry_sdk = pytest.importorskip("sentry_sdk")

from scrapfly.reporter.sentry import SentryReporter


class FakeResponse:
    config = {"project": "p", "env": "live", "url": "https://example.com"}
    scrape_result = {"log_url": "https://log", "url": "https://example.com", "status_code": 503}
    error = {"code": "ERR::TEST"}


def test_reports_error_with_scrapfly_context():
    events = []
    sentry_sdk.init(dsn="https://key@localhost/1", default_integrations=False,
                    before_send=lambda event, hint: events.append(event))  # returning None drops the event

    SentryReporter()(error=ValueError("boom"), scrape_api_response=FakeResponse())

    assert events[0]["tags"]["scrapfly_error_code"] == "ERR::TEST"
    assert events[0]["tags"]["scrapfly_upstream_status_code"] == 503
    assert events[0]["extra"]["log_url"] == "https://log"
