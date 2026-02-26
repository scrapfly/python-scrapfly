"""
Example Crawler Webhook Handler

This example demonstrates how to receive and handle Crawler API webhooks.
"""

from scrapfly import (
    webhook_from_payload,
    CrawlStartedWebhook,
    CrawlUrlDiscoveredWebhook,
    CrawlUrlFailedWebhook,
    CrawlCompletedWebhook,
)


# Example: Simple Flask webhook endpoint
def example_flask_webhook():
    """Simple webhook handling with Flask"""
    from flask import Flask, request

    app = Flask(__name__)
    SIGNING_SECRETS = ('your-secret-key-here',)

    @app.route('/webhook', methods=['POST'])
    def webhook():
        # Parse and verify the webhook
        webhook_obj = webhook_from_payload(
            request.json,
            signing_secrets=SIGNING_SECRETS,
            signature=request.headers.get('X-Scrapfly-Webhook-Signature')
        )

        # Handle different webhook types
        if isinstance(webhook_obj, CrawlStartedWebhook):
            print(f"Crawl {webhook_obj.uuid} started")

        elif isinstance(webhook_obj, CrawlUrlDiscoveredWebhook):
            print(f"Discovered: {webhook_obj.url} (depth {webhook_obj.depth})")

        elif isinstance(webhook_obj, CrawlUrlFailedWebhook):
            print(f"Failed: {webhook_obj.url} - {webhook_obj.error}")

        elif isinstance(webhook_obj, CrawlCompletedWebhook):
            print(f"Completed: {webhook_obj.urls_crawled}/{webhook_obj.urls_discovered} URLs")

        return '', 200

    app.run(port=5000)


# Example: Using built-in webhook server
def example_builtin_server():
    """Using Scrapfly's built-in webhook server"""
    from scrapfly.webhook import create_server, ResourceType

    def callback(data, resource_type, request):
        if resource_type == ResourceType.CRAWLER.value:
            webhook_obj = webhook_from_payload(data)
            print(f"Received {webhook_obj.event} for {webhook_obj.uuid}")

    app = create_server(
        signing_secrets=('your-secret-key-here',),
        callback=callback
    )
    app.run(port=5000)


# Test with example payloads
if __name__ == '__main__':
    EXAMPLE_PAYLOADS = {
        'started': {
            "event": "crawl.started",
            "uuid": "test-uuid",
            "status": "RUNNING",
            "timestamp": "2025-01-16T10:30:00Z"
        },
        'url_discovered': {
            "event": "crawl.url_discovered",
            "uuid": "test-uuid",
            "url": "https://example.com/page",
            "depth": 1,
            "timestamp": "2025-01-16T10:30:05Z"
        },
        'url_failed': {
            "event": "crawl.url_failed",
            "uuid": "test-uuid",
            "url": "https://example.com/404",
            "error": "HTTP 404 Not Found",
            "status_code": 404,
            "timestamp": "2025-01-16T10:30:10Z"
        },
        'completed': {
            "event": "crawl.completed",
            "uuid": "test-uuid",
            "status": "COMPLETED",
            "urls_discovered": 100,
            "urls_crawled": 95,
            "urls_failed": 5,
            "timestamp": "2025-01-16T10:35:00Z"
        }
    }

    print("Testing webhook parsing:\n")
    for name, payload in EXAMPLE_PAYLOADS.items():
        webhook = webhook_from_payload(payload)
        print(f"{webhook.event}: {webhook.uuid} at {webhook.timestamp}")
