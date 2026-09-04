"""
Unit tests for the crawler webhook parser.

These tests use hand-crafted payloads that mirror *exactly* what the
scrape-engine emits in
``apps/scrapfly/scrape-engine/scrape_engine/scrape_engine/crawler/webhook_manager.py``.

For each of the 11 crawler events the scrape-engine dispatches
(``dispatch_crawler_start``, ``dispatch_crawler_stop``, ``dispatch_url_*``,
``dispatch_crawler_search``, ``dispatch_crawler_updated``),
we build a payload that matches the engine's ``data`` dict 1:1 and assert
that ``webhook_from_payload`` parses it into the correct typed dataclass
with every field populated.

Implementation is the source of truth — not the example JSON fixtures in
``apps/scrapfly/web-app/src/Template/Docs/crawler-api/webhooks_example/``
(one of those is already known to drift vs the engine — see
``crawler_url_failed.json::links`` which is missing the ``scrape`` key that
the engine always emits).

These tests are pure: no network, no credentials.
"""

import pytest

from scrapfly import (
    CrawlerLifecycleWebhook,
    CrawlerSearchWebhook,
    CrawlerUpdatedWebhook,
    CrawlerUrlDiscoveredWebhook,
    CrawlerUrlFailedWebhook,
    CrawlerUrlSkippedWebhook,
    CrawlerUrlVisitedWebhook,
    CrawlerWebhookEvent,
    webhook_from_payload,
)


# ---------------------------------------------------------------------------
# Fixture factory helpers — mirror the engine's ``data`` dicts 1:1
# ---------------------------------------------------------------------------


def _state(**overrides):
    """
    Build a ``state`` block identical in shape to
    ``CrawlJob.state.to_dict()`` in the scrape-engine.
    """
    base = {
        "duration": 6.11,
        "urls_visited": 5,
        "urls_extracted": 49,
        "urls_failed": 0,
        "urls_skipped": 44,
        "urls_to_crawl": 5,
        "api_credit_used": 5,
        "stop_reason": None,
        "start_time": 1762940028,
        "stop_time": 1762940034.1143808,
    }
    base.update(overrides)
    return base


def _lifecycle_envelope(event_name, action, stop_reason=None):
    """
    Mirror of ``webhook_manager.dispatch_crawler_start`` /
    ``dispatch_crawler_stop`` (lines 251-264 / 193-207).
    """
    return {
        "event": event_name,
        "payload": {
            "crawler_uuid": "b4867c50-318c-47cd-bfc9-bed67f24771a",
            "project": "default",
            "env": "LIVE",
            "seed_url": "https://web-scraping.dev/products",
            "action": action,
            "state": _state(stop_reason=stop_reason),
            "links": {
                "status": "https://api.scrapfly.io/crawl/b4867c50-318c-47cd-bfc9-bed67f24771a/status",
            },
        },
    }


# ---------------------------------------------------------------------------
# Lifecycle events (4): started / stopped / cancelled / finished
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "event_name,action,stop_reason",
    [
        (CrawlerWebhookEvent.CRAWLER_STARTED.value,   "started",   None),
        (CrawlerWebhookEvent.CRAWLER_STOPPED.value,   "stopped",   "seed_url_failed"),
        (CrawlerWebhookEvent.CRAWLER_CANCELLED.value, "cancelled", "user_cancelled"),
        (CrawlerWebhookEvent.CRAWLER_FINISHED.value,  "finished",  "page_limit"),
    ],
)
def test_lifecycle_events(event_name, action, stop_reason):
    envelope = _lifecycle_envelope(event_name, action, stop_reason=stop_reason)

    wh = webhook_from_payload(envelope)

    assert isinstance(wh, CrawlerLifecycleWebhook)
    assert wh.event == event_name
    assert wh.crawler_uuid == "b4867c50-318c-47cd-bfc9-bed67f24771a"
    assert wh.project == "default"
    assert wh.env == "LIVE"
    assert wh.action == action
    assert wh.seed_url == "https://web-scraping.dev/products"
    assert wh.status_link.endswith("/status")

    # State parity with the wire vocabulary
    assert wh.state.urls_visited == 5
    assert wh.state.urls_extracted == 49
    assert wh.state.urls_to_crawl == 5
    assert wh.state.urls_failed == 0
    assert wh.state.urls_skipped == 44
    assert wh.state.api_credit_used == 5
    assert wh.state.stop_reason == stop_reason
    assert wh.state.start_time == 1762940028
    assert wh.state.duration == 6.11


# ---------------------------------------------------------------------------
# crawler_url_visited
# ---------------------------------------------------------------------------


def test_url_visited():
    """
    Mirrors ``webhook_manager.dispatch_url_visited`` (lines 128-154).
    The engine just forwards ``content_payload`` as ``scrape``; real
    production payloads always include status_code / country / log_uuid /
    log_url / content so the dataclass requires them.
    """
    envelope = {
        "event": CrawlerWebhookEvent.CRAWLER_URL_VISITED.value,
        "payload": {
            "crawler_uuid": "60cf1121-9de4-43fc-a0c6-7dda1721a65b",
            "project": "default",
            "env": "LIVE",
            "url": "https://web-scraping.dev/products",
            "action": "visited",
            "state": _state(urls_visited=1, urls_extracted=1, urls_to_crawl=0, api_credit_used=1),
            "scrape": {
                "status_code": 200,
                "country": "de",
                "log_uuid": "01K9VPD22494F0ZEX7DGEZQ4ES",
                "log_url": "https://scrapfly.io/dashboard/monitoring/log/01K9VPD22494F0ZEX7DGEZQ4ES",
                "content": {
                    "html": "<html>...</html>",
                    "text": "lorem ipsum",
                },
            },
        },
    }

    wh = webhook_from_payload(envelope)

    assert isinstance(wh, CrawlerUrlVisitedWebhook)
    assert wh.event == "crawler_url_visited"
    assert wh.url == "https://web-scraping.dev/products"
    assert wh.action == "visited"
    assert wh.scrape.status_code == 200
    assert wh.scrape.country == "de"
    assert wh.scrape.log_uuid == "01K9VPD22494F0ZEX7DGEZQ4ES"
    assert wh.scrape.log_url.startswith("https://scrapfly.io/dashboard/")
    assert wh.scrape.content["html"].startswith("<html>")
    assert wh.scrape.content["text"] == "lorem ipsum"
    assert wh.state.urls_visited == 1


# ---------------------------------------------------------------------------
# crawler_url_skipped
# ---------------------------------------------------------------------------


def test_url_skipped():
    """Mirrors ``webhook_manager.dispatch_url_skipped`` (lines 101-126)."""
    envelope = {
        "event": CrawlerWebhookEvent.CRAWLER_URL_SKIPPED.value,
        "payload": {
            "crawler_uuid": "b4867c50-318c-47cd-bfc9-bed67f24771a",
            "project": "default",
            "env": "LIVE",
            "action": "skipped",
            "state": _state(urls_visited=1, urls_extracted=22, urls_skipped=21, urls_to_crawl=1, stop_reason="page_limit"),
            "urls": {
                "https://web-scraping.dev/product/2?variant=one": "page_limit",
                "https://web-scraping.dev/product/25": "page_limit",
                "https://web-scraping.dev/product/15": "page_limit",
            },
        },
    }

    wh = webhook_from_payload(envelope)

    assert isinstance(wh, CrawlerUrlSkippedWebhook)
    assert wh.event == "crawler_url_skipped"
    assert wh.action == "skipped"
    assert len(wh.urls) == 3
    assert wh.urls["https://web-scraping.dev/product/25"] == "page_limit"
    assert wh.state.stop_reason == "page_limit"


# ---------------------------------------------------------------------------
# crawler_url_discovered
# ---------------------------------------------------------------------------


def test_url_discovered():
    """Mirrors ``webhook_manager.dispatch_urls_discovered`` (lines 71-99)."""
    envelope = {
        "event": CrawlerWebhookEvent.CRAWLER_URL_DISCOVERED.value,
        "payload": {
            "crawler_uuid": "92e97a67-a962-4dcd-9b3e-261e4d4cb6f5",
            "project": "default",
            "env": "LIVE",
            "action": "url_discovery",
            "state": _state(urls_visited=0, urls_extracted=0, urls_to_crawl=0, api_credit_used=1),
            "origin": "navigation",
            "discovered_urls": [
                "https://web-scraping.dev/product/5",
                "https://web-scraping.dev/product/1",
                "https://web-scraping.dev/product/3",
                "https://web-scraping.dev/product/4",
                "https://web-scraping.dev/product/2",
            ],
        },
    }

    wh = webhook_from_payload(envelope)

    assert isinstance(wh, CrawlerUrlDiscoveredWebhook)
    assert wh.event == "crawler_url_discovered"
    assert wh.action == "url_discovery"
    assert wh.origin == "navigation"
    assert len(wh.discovered_urls) == 5
    assert wh.discovered_urls[0] == "https://web-scraping.dev/product/5"


# ---------------------------------------------------------------------------
# crawler_url_failed
# ---------------------------------------------------------------------------


def test_url_failed_with_log_and_scrape_links():
    """
    Mirrors ``webhook_manager.dispatch_url_failed`` (lines 28-69).

    The engine always emits **both** links: ``log`` (nullable — line 57 passes
    None when no scrape_log_uuid is available) and ``scrape`` (line 58, always
    present).
    """
    envelope = {
        "event": CrawlerWebhookEvent.CRAWLER_URL_FAILED.value,
        "payload": {
            "crawler_uuid": "5caa5439-03a4-4c74-9a4c-0597e190dd72",
            "project": "default",
            "env": "LIVE",
            "action": "failed",
            "state": _state(urls_visited=0, urls_extracted=0, urls_to_crawl=0, api_credit_used=0),
            "url": "https://web-scraping.dev/products",
            "error": "ERR::SCRAPE::NETWORK_ERROR",
            "scrape_config": {
                "method": "GET",
                "url": "https://web-scraping.dev/products",
                "asp": False,
                "country": "de",
            },
            "links": {
                "log": "https://api.scrapfly.io/crawl/5caa5439.../logs?url=...",
                "scrape": "https://api.scrapfly.io/scrape?url=...",
            },
        },
    }

    wh = webhook_from_payload(envelope)

    assert isinstance(wh, CrawlerUrlFailedWebhook)
    assert wh.event == "crawler_url_failed"
    assert wh.url == "https://web-scraping.dev/products"
    assert wh.error == "ERR::SCRAPE::NETWORK_ERROR"
    assert wh.scrape_config["method"] == "GET"
    assert wh.log_link == "https://api.scrapfly.io/crawl/5caa5439.../logs?url=..."
    assert wh.scrape_link == "https://api.scrapfly.io/scrape?url=..."


def test_url_failed_with_null_log_link():
    """
    ``links.log`` is ``None`` when the failure happened before a scrape log
    was created (engine line 57: ``if scrape_log_uuid else None``).
    ``links.scrape`` must still be present.
    """
    envelope = {
        "event": CrawlerWebhookEvent.CRAWLER_URL_FAILED.value,
        "payload": {
            "crawler_uuid": "5caa5439-03a4-4c74-9a4c-0597e190dd72",
            "project": "default",
            "env": "LIVE",
            "action": "failed",
            "state": _state(),
            "url": "https://web-scraping.dev/products",
            "error": "ERR::PROXY::CONNECTION_FAILED",
            "scrape_config": {"method": "GET", "url": "https://web-scraping.dev/products"},
            "links": {
                "log": None,
                "scrape": "https://api.scrapfly.io/scrape?url=...",
            },
        },
    }

    wh = webhook_from_payload(envelope)

    assert wh.log_link is None
    assert wh.scrape_link.startswith("https://api.scrapfly.io/scrape")


# ---------------------------------------------------------------------------
# crawler_search_ready / crawler_search_failed
# ---------------------------------------------------------------------------


def _search_envelope(event_name, search):
    """
    Mirror of ``webhook_manager.dispatch_crawler_search``. These two events
    are the only ones the engine emits **without** an ``action`` tag.
    """
    return {
        "event": event_name,
        "payload": {
            "crawler_uuid": "b4867c50-318c-47cd-bfc9-bed67f24771a",
            "project": "default",
            "env": "LIVE",
            "seed_url": "https://web-scraping.dev/products",
            "state": _state(),
            "search": search,
            "links": {
                "status": "https://api.scrapfly.io/crawl/b4867c50-318c-47cd-bfc9-bed67f24771a/status",
            },
        },
    }


def test_search_ready():
    envelope = _search_envelope(
        CrawlerWebhookEvent.CRAWLER_SEARCH_READY.value,
        {
            "status": "READY",
            "manifest": "crawl/b4867c50/search/manifest.json",
            "documents": 412,
            "vectors": 18432,
            "dropped": 0,
            "queue_depth": 0,
            "fragments": 3,
            "error": None,
            "built_at": "2026-09-02T10:11:12Z",
            "index": "IVF_PQ",
            "embedding_model": "text-embedding-005",
            "embedding_dimension": 768,
            "generation": 1,
        },
    )

    wh = webhook_from_payload(envelope)

    assert isinstance(wh, CrawlerSearchWebhook)
    assert wh.event == "crawler_search_ready"
    assert wh.crawler_uuid == "b4867c50-318c-47cd-bfc9-bed67f24771a"
    assert wh.seed_url == "https://web-scraping.dev/products"
    assert wh.status_link.endswith("/status")
    assert wh.search.status == "READY"
    assert wh.search.documents == 412
    assert wh.search.vectors == 18432
    assert wh.search.index == "IVF_PQ"
    # Which model we embed with is not the customer's business. The fixture
    # still sends both fields because an older API will; a model with no such
    # attribute is what drops them.
    assert not hasattr(wh.search, "embedding_model")
    assert not hasattr(wh.search, "embedding_dimension")
    assert wh.search.generation == 1
    assert wh.search.is_searchable is True
    assert wh.state.urls_visited == 5


def test_search_failed():
    envelope = _search_envelope(
        CrawlerWebhookEvent.CRAWLER_SEARCH_FAILED.value,
        {"status": "FAILED", "error": "embedding backend unavailable", "vectors": 0},
    )

    wh = webhook_from_payload(envelope)

    assert isinstance(wh, CrawlerSearchWebhook)
    assert wh.event == "crawler_search_failed"
    assert wh.search.status == "FAILED"
    assert wh.search.error == "embedding backend unavailable"
    assert wh.search.is_searchable is False
    # The block is sparse on failure; absent counters must not raise.
    assert wh.search.documents is None


def test_search_event_names_parse():
    """
    The parser raises on unknown event names, so both names have to be
    registered in the dispatch table for a subscriber to receive them at all.
    """
    for name in ("crawler_search_ready", "crawler_search_failed"):
        wh = webhook_from_payload(_search_envelope(name, {"status": "READY"}))
        assert wh.event == name


def test_missing_search_block_raises_keyerror():
    """Strict parsing: the block is what the event exists to deliver."""
    envelope = _search_envelope(CrawlerWebhookEvent.CRAWLER_SEARCH_READY.value, {"status": "READY"})
    del envelope["payload"]["search"]

    with pytest.raises(KeyError):
        webhook_from_payload(envelope)

# ---------------------------------------------------------------------------
# crawler_updated
# ---------------------------------------------------------------------------


def _updated_envelope(refresh=None, documents=None):
    """
    Mirror ``dispatch_crawler_updated``: the run's timeline row under
    ``refresh``, the changed URLs under ``documents``.
    """
    return {
        "event": CrawlerWebhookEvent.CRAWLER_UPDATED.value,
        "payload": {
            "crawler_uuid": "b4867c50-318c-47cd-bfc9-bed67f24771a",
            "project": "default",
            "env": "LIVE",
            "seed_url": "https://web-scraping.dev/products",
            "action": "updated",
            "state": _state(stop_reason="no_more_urls"),
            "refresh": refresh if refresh is not None else {
                "at": "2026-09-03T04:12:46.912430Z",
                "generation": 12,
                "added": 1,
                "updated": 2,
                "removed": 1,
                "unchanged": 2,
                "failed": 0,
                "duration_ms": 41870,
                "search_status": "READY",
                "error": None,
            },
            "documents": documents if documents is not None else {
                "updated": [
                    "https://web-scraping.dev/product/25",
                    "https://web-scraping.dev/products",
                    "https://web-scraping.dev/product/1",
                ],
                "removed": ["https://web-scraping.dev/product/9"],
                "truncated": False,
            },
            "links": {
                "status": "https://api.scrapfly.io/crawl/b4867c50-318c-47cd-bfc9-bed67f24771a/status",
            },
        },
    }


def test_updated_carries_the_run_and_the_changed_documents():
    wh = webhook_from_payload(_updated_envelope())

    assert isinstance(wh, CrawlerUpdatedWebhook)
    assert wh.event == "crawler_updated"
    assert wh.action == "updated"
    assert wh.crawler_uuid == "b4867c50-318c-47cd-bfc9-bed67f24771a"
    assert wh.seed_url == "https://web-scraping.dev/products"
    assert wh.status_link.endswith("/status")
    assert wh.refresh.generation == 12
    assert wh.refresh.added == 1
    assert wh.refresh.updated == 2
    assert wh.refresh.removed == 1
    assert wh.refresh.unchanged == 2
    assert wh.refresh.failed == 0
    assert wh.refresh.duration_ms == 41870
    assert wh.refresh.search_status == "READY"
    assert wh.refresh.changed == 4
    assert wh.documents.updated == [
        "https://web-scraping.dev/product/25",
        "https://web-scraping.dev/products",
        "https://web-scraping.dev/product/1",
    ]
    assert wh.documents.removed == ["https://web-scraping.dev/product/9"]
    assert wh.documents.truncated is False
    # The samples live in `documents` for this event, so the timeline row's
    # own sample fields are absent rather than a second, shorter copy.
    assert wh.refresh.sample_updated == []
    assert wh.refresh.sample_removed == []


def test_updated_reports_a_capped_list_as_truncated():
    """
    The counts stay whole when the lists are cut, which is what tells a
    consumer to go and read the crawl rather than trust the body.
    """
    urls = [f"https://web-scraping.dev/product/{index}" for index in range(100)]
    envelope = _updated_envelope(
        refresh={"generation": 3, "added": 0, "updated": 250, "removed": 0, "unchanged": 0, "failed": 0},
        documents={"updated": urls, "removed": [], "truncated": True},
    )

    wh = webhook_from_payload(envelope)

    assert len(wh.documents.updated) == 100
    assert wh.documents.truncated is True
    assert wh.refresh.updated == 250


def test_updated_missing_documents_block_raises_keyerror():
    """Strict parsing: the changed URLs are what the event exists to deliver."""
    envelope = _updated_envelope()
    del envelope["payload"]["documents"]

    with pytest.raises(KeyError):
        webhook_from_payload(envelope)


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_unknown_event_raises_valueerror():
    with pytest.raises(ValueError, match="Unknown crawler webhook event"):
        webhook_from_payload({"event": "crawler_time_traveled", "payload": {}})


def test_missing_envelope_field_raises_keyerror():
    with pytest.raises(KeyError):
        webhook_from_payload({"payload": {}})  # no event
    with pytest.raises(KeyError):
        webhook_from_payload({"event": "crawler_started"})  # no payload


def test_missing_required_payload_field_raises_keyerror():
    """
    Strict parsing: a lifecycle event missing ``crawler_uuid`` must fail
    loud — silent defaults would mask contract drift.
    """
    envelope = _lifecycle_envelope(
        CrawlerWebhookEvent.CRAWLER_FINISHED.value,
        "finished",
    )
    del envelope["payload"]["crawler_uuid"]
    with pytest.raises(KeyError):
        webhook_from_payload(envelope)


def test_missing_scrape_link_on_url_failed_raises_keyerror():
    """
    ``links.scrape`` is always emitted by the engine (line 58) — a missing
    one signals engine contract drift and must fail loud.
    """
    envelope = {
        "event": CrawlerWebhookEvent.CRAWLER_URL_FAILED.value,
        "payload": {
            "crawler_uuid": "x",
            "project": "default",
            "env": "LIVE",
            "action": "failed",
            "state": _state(),
            "url": "https://example.com/",
            "error": "ERR::X",
            "scrape_config": {},
            "links": {"log": None},  # no 'scrape' — drift!
        },
    }
    with pytest.raises(KeyError):
        webhook_from_payload(envelope)
