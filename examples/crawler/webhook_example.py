"""
Example Crawler Webhook Handler

This example demonstrates how to receive and handle the 8 real crawler
webhook events emitted by the Scrapfly crawler API.

Event envelope
==============

Every crawler webhook follows the same envelope:

    {
        "event":   "<event_name>",
        "payload": { ... event-specific fields ... }
    }

The 8 event names are defined by ``CrawlerWebhookEvent`` and match the
scrape-engine's ``WebhookEvents`` class exactly.
"""

from scrapfly import (
    webhook_from_payload,
    CrawlerWebhookEvent,
    CrawlerLifecycleWebhook,
    CrawlerUrlVisitedWebhook,
    CrawlerUrlSkippedWebhook,
    CrawlerUrlDiscoveredWebhook,
    CrawlerUrlFailedWebhook,
)


# ---------------------------------------------------------------------------
# Example 1: Flask webhook endpoint
# ---------------------------------------------------------------------------


def example_flask_webhook():
    """Simple webhook handling with Flask"""
    from flask import Flask, request

    app = Flask(__name__)
    SIGNING_SECRETS = ('your-secret-hex-here',)

    @app.route('/webhook', methods=['POST'])
    def webhook():
        # Parse and verify the webhook. The envelope is always
        # {"event": ..., "payload": ...}; webhook_from_payload dispatches
        # on the event name and returns a typed dataclass.
        wh = webhook_from_payload(
            request.json,
            signing_secrets=SIGNING_SECRETS,
            signature=request.headers.get('X-Scrapfly-Webhook-Signature'),
        )

        # All webhooks carry the common base fields:
        print(f"[{wh.event}] crawler={wh.crawler_uuid} project={wh.project} "
              f"visited={wh.state.urls_visited}/{wh.state.urls_extracted}")

        # Dispatch on the concrete type for event-specific fields.
        if isinstance(wh, CrawlerLifecycleWebhook):
            # Covers crawler_started / crawler_stopped / crawler_cancelled /
            # crawler_finished. Use wh.event to distinguish which one.
            if wh.event == CrawlerWebhookEvent.CRAWLER_FINISHED.value:
                print(f"  ✓ finished: {wh.state.urls_visited} URLs visited, "
                      f"credits={wh.state.api_credit_used}, "
                      f"stop_reason={wh.state.stop_reason}")
            elif wh.event == CrawlerWebhookEvent.CRAWLER_STARTED.value:
                print(f"  ▶ started at seed_url={wh.seed_url}")
            elif wh.event == CrawlerWebhookEvent.CRAWLER_CANCELLED.value:
                print(f"  ✗ cancelled by user")
            elif wh.event == CrawlerWebhookEvent.CRAWLER_STOPPED.value:
                print(f"  ⚠ stopped (stop_reason={wh.state.stop_reason})")

        elif isinstance(wh, CrawlerUrlVisitedWebhook):
            print(f"  ● visited {wh.url} [{wh.scrape.status_code}] "
                  f"country={wh.scrape.country} log={wh.scrape.log_uuid}")

        elif isinstance(wh, CrawlerUrlDiscoveredWebhook):
            print(f"  ◆ discovered {len(wh.discovered_urls)} URLs "
                  f"via {wh.origin}")

        elif isinstance(wh, CrawlerUrlSkippedWebhook):
            for url, reason in wh.urls.items():
                print(f"  ○ skipped {url} ({reason})")

        elif isinstance(wh, CrawlerUrlFailedWebhook):
            print(f"  ✗ failed {wh.url}: {wh.error}")
            if wh.log_link:
                print(f"    log: {wh.log_link}")

        return '', 200

    app.run(port=5000)


# ---------------------------------------------------------------------------
# Example 2: Sanity-check with a real fixture payload
# ---------------------------------------------------------------------------


if __name__ == '__main__':
    # A real crawler_finished payload — exactly as the scrape-engine emits it
    # (see apps/scrapfly/web-app/src/Template/Docs/crawler-api/
    #  webhooks_example/crawler_finished.json for the canonical reference).
    example_finished = {
        "event": "crawler_finished",
        "payload": {
            "crawler_uuid": "b4867c50-318c-47cd-bfc9-bed67f24771a",
            "project": "default",
            "env": "LIVE",
            "seed_url": "https://web-scraping.dev/products",
            "action": "finished",
            "state": {
                "duration": 6.11,
                "urls_visited": 5,
                "urls_extracted": 49,
                "urls_failed": 0,
                "urls_skipped": 44,
                "urls_to_crawl": 5,
                "api_credit_used": 5,
                "stop_reason": "page_limit",
                "start_time": 1762940028,
                "stop_time": 1762940034.1143808,
            },
            "links": {
                "status": "https://api.scrapfly.io/crawl/b4867c50-318c-47cd-bfc9-bed67f24771a/status",
            },
        },
    }

    wh = webhook_from_payload(example_finished)
    assert isinstance(wh, CrawlerLifecycleWebhook)
    assert wh.event == CrawlerWebhookEvent.CRAWLER_FINISHED.value
    print(f"Parsed: {wh.event}")
    print(f"  crawler_uuid: {wh.crawler_uuid}")
    print(f"  seed_url:     {wh.seed_url}")
    print(f"  state.urls_visited:  {wh.state.urls_visited}")
    print(f"  state.urls_extracted:{wh.state.urls_extracted}")
    print(f"  state.stop_reason:   {wh.state.stop_reason}")
    print(f"  status_link:         {wh.status_link}")
