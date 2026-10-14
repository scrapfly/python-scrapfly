"""Scheduled scrapes, screenshots and crawls, driven through the SDK against a live API.

What a customer relies on, observed from the outside:

  * a schedule of each kind is created, fires on demand, and its fire reaches
    the engine: `consecutive_failures` is read from the run history, so a fire
    the worker could not hand to the engine shows up there (the crawl kind sent
    the project's uuid where the engine wanted its name, and every scheduled
    crawl failed with ERR::WEBHOOK::NOT_FOUND);
  * a schedule bounded to one fire fires on its own clock and ends CANCELLED;
  * pause, resume and cancel move the schedule between its states.

What it cannot see: whether the webhook delivery succeeded. That lands on the
customer's endpoint and in the webhook's own counters, not in this API.

Needs SCRAPFLY_KEY, SCRAPFLY_API_HOST and SCRAPFLY_E2E_WEBHOOK, the name of a
webhook of that key's project and environment. Every schedule it creates is
cancelled before the test returns.
"""

import os
import time
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Iterator, List

import pytest

from scrapfly import ScrapflyClient
from scrapfly.schedule import CreateScheduleRequest, ScheduleEnd, ScheduleRecurrence

pytestmark = [pytest.mark.integration, pytest.mark.e2e]

API_KEY = os.environ.get("SCRAPFLY_KEY", "")
API_HOST = os.environ.get("SCRAPFLY_API_HOST", "https://api.scrapfly.io")
WEBHOOK = os.environ.get("SCRAPFLY_E2E_WEBHOOK", "")

TARGET = "https://web-scraping.dev/product/1"
# Far enough that no fire of its own lands during the test: only `execute` fires it.
NIGHTLY = ScheduleRecurrence(cron="0 3 * * *")

# The worker hands a fire to the engine within seconds; the history is
# written asynchronously right after.
SETTLE_SECONDS = 45


@pytest.fixture
def client() -> ScrapflyClient:
    if not WEBHOOK:
        pytest.skip("set SCRAPFLY_E2E_WEBHOOK to the name of a webhook of this key's project and environment")
    return ScrapflyClient(key=API_KEY, host=API_HOST, verify=False)


@pytest.fixture
def created(client: ScrapflyClient) -> Iterator[List[str]]:
    """Schedules made by the test, cancelled whatever happens."""
    ids: List[str] = []
    yield ids
    for schedule_id in ids:
        try:
            client.cancel_schedule(schedule_id)
        except Exception:
            pass


def request(**kwargs) -> CreateScheduleRequest:
    return CreateScheduleRequest(webhook_name=WEBHOOK, notes="sdk e2e: test_schedule_e2e.py", **kwargs)


KINDS: Dict[str, Callable[[ScrapflyClient, CreateScheduleRequest], dict]] = {
    "api.scrape": lambda c, r: c.create_scrape_schedule({"url": TARGET}, r),
    "api.screenshot": lambda c, r: c.create_screenshot_schedule({"url": TARGET}, r),
    # Subscribed to its start and its end: a crawl with no webhook event sends the webhook nothing.
    "api.crawler": lambda c, r: c.create_crawler_schedule({"url": "https://web-scraping.dev/products", "page_limit": 2, "webhook_events": ["crawler_started", "crawler_finished"]}, r),
}


@pytest.mark.parametrize("kind", list(KINDS))
def test_a_fire_of_each_kind_reaches_the_engine(client: ScrapflyClient, created: List[str], kind: str) -> None:
    schedule = KINDS[kind](client, request(recurrence=NIGHTLY))
    created.append(schedule["id"])
    assert (schedule["kind"], schedule["status"]) == (kind, "ACTIVE")

    fired = client.execute_schedule(schedule["id"])
    assert fired["status"] == "ACTIVE", "a recurring schedule stays active after a fire"

    # A failure lands in the history within seconds; success leaves it at 0.
    deadline = time.monotonic() + SETTLE_SECONDS
    while time.monotonic() < deadline:
        current = client.get_schedule(schedule["id"])
        assert current.get("consecutive_failures", 0) == 0, f"the {kind} fire failed on its way to the engine: {current}"
        time.sleep(5)


def test_a_schedule_bounded_to_one_fire_fires_by_itself_and_ends(client: ScrapflyClient, created: List[str]) -> None:
    # The minimum recurrence is one minute; the first fire is a minute out.
    once = ScheduleRecurrence(interval=1, unit="minute", ends=ScheduleEnd(type="count", count=1))
    schedule = client.create_scrape_schedule({"url": TARGET}, request(recurrence=once))
    created.append(schedule["id"])

    deadline = time.monotonic() + 180
    current = schedule
    while time.monotonic() < deadline and current["status"] != "CANCELLED":
        time.sleep(10)
        current = client.get_schedule(schedule["id"])

    assert current["status"] == "CANCELLED", f"the scheduler never fired it on its own clock: {current}"
    assert current.get("consecutive_failures", 0) == 0, f"its one fire failed: {current}"


def test_pause_resume_and_cancel(client: ScrapflyClient, created: List[str]) -> None:
    schedule = client.create_screenshot_schedule({"url": TARGET}, request(recurrence=NIGHTLY))
    created.append(schedule["id"])

    assert client.pause_schedule(schedule["id"])["status"] == "PAUSED"

    resumed = client.resume_schedule(schedule["id"])
    assert resumed["status"] == "ACTIVE"
    next_fire = datetime.fromisoformat(resumed["next_scheduled_date"].replace("Z", "+00:00"))
    assert datetime.now(timezone.utc) < next_fire <= datetime.now(timezone.utc) + timedelta(days=1), "resumed from now, on its own recurrence"

    client.cancel_schedule(schedule["id"])
    assert client.get_schedule(schedule["id"])["status"] == "CANCELLED"
