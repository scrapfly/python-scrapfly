"""
Crawler API Webhook Models

This module provides models for handling Crawler API webhook events.
All webhooks follow the standard format with signature verification support.
"""

from typing import Dict, Optional, Union, Tuple
from datetime import datetime
from enum import Enum
from dataclasses import dataclass


class CrawlerWebhookEvent(Enum):
    """Crawler webhook event types"""
    STARTED = 'crawl.started'
    URL_DISCOVERED = 'crawl.url_discovered'
    URL_FAILED = 'crawl.url_failed'
    COMPLETED = 'crawl.completed'


@dataclass
class CrawlerWebhookBase:
    """
    Base class for all crawler webhook payloads.

    All webhook events share these common fields:
    - event: The event type (crawl.started, crawl.url_discovered, etc.)
    - uuid: The crawler job UUID
    - timestamp: When the event occurred (ISO 8601 format)
    """
    event: str
    uuid: str
    timestamp: datetime

    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlerWebhookBase':
        """Create webhook instance from dictionary payload"""
        # Parse timestamp if it's a string
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            # Handle ISO 8601 format
            if timestamp.endswith('Z'):
                timestamp = timestamp[:-1] + '+00:00'
            timestamp = datetime.fromisoformat(timestamp)

        return cls(
            event=data['event'],
            uuid=data['uuid'],
            timestamp=timestamp
        )


@dataclass
class CrawlStartedWebhook(CrawlerWebhookBase):
    """
    Webhook payload for crawl.started event.

    Sent when a crawler job starts running.

    Additional fields:
    - status: Current crawler status (should be 'RUNNING')

    Example payload:
    {
        "event": "crawl.started",
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "status": "RUNNING",
        "timestamp": "2025-01-16T10:30:00Z"
    }
    """
    status: str

    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlStartedWebhook':
        """Create webhook instance from dictionary payload"""
        base = CrawlerWebhookBase.from_dict(data)
        return cls(
            event=base.event,
            uuid=base.uuid,
            timestamp=base.timestamp,
            status=data['status']
        )


@dataclass
class CrawlUrlDiscoveredWebhook(CrawlerWebhookBase):
    """
    Webhook payload for crawl.url_discovered event.

    Sent when a new URL is discovered during crawling.

    Additional fields:
    - url: The discovered URL
    - depth: Depth level of the URL from the starting URL

    Example payload:
    {
        "event": "crawl.url_discovered",
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "url": "https://example.com/page",
        "depth": 1,
        "timestamp": "2025-01-16T10:30:05Z"
    }
    """
    url: str
    depth: int

    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlUrlDiscoveredWebhook':
        """Create webhook instance from dictionary payload"""
        base = CrawlerWebhookBase.from_dict(data)
        return cls(
            event=base.event,
            uuid=base.uuid,
            timestamp=base.timestamp,
            url=data['url'],
            depth=data['depth']
        )


@dataclass
class CrawlUrlFailedWebhook(CrawlerWebhookBase):
    """
    Webhook payload for crawl.url_failed event.

    Sent when a URL fails to be crawled.

    Additional fields:
    - url: The URL that failed
    - error: Error message describing the failure
    - status_code: HTTP status code if available (optional)

    Example payload:
    {
        "event": "crawl.url_failed",
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "url": "https://example.com/page",
        "error": "HTTP 404 Not Found",
        "status_code": 404,
        "timestamp": "2025-01-16T10:30:10Z"
    }
    """
    url: str
    error: str
    status_code: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlUrlFailedWebhook':
        """Create webhook instance from dictionary payload"""
        base = CrawlerWebhookBase.from_dict(data)
        return cls(
            event=base.event,
            uuid=base.uuid,
            timestamp=base.timestamp,
            url=data['url'],
            error=data['error'],
            status_code=data.get('status_code')
        )


@dataclass
class CrawlCompletedWebhook(CrawlerWebhookBase):
    """
    Webhook payload for crawl.completed event.

    Sent when a crawler job completes (successfully or with errors).

    Additional fields:
    - status: Final crawler status (COMPLETED, FAILED, etc.)
    - urls_discovered: Total number of URLs discovered
    - urls_crawled: Number of URLs successfully crawled
    - urls_failed: Number of URLs that failed

    Example payload:
    {
        "event": "crawl.completed",
        "uuid": "550e8400-e29b-41d4-a716-446655440000",
        "status": "COMPLETED",
        "urls_discovered": 100,
        "urls_crawled": 95,
        "urls_failed": 5,
        "timestamp": "2025-01-16T10:35:00Z"
    }
    """
    status: str
    urls_discovered: int
    urls_crawled: int
    urls_failed: int

    @classmethod
    def from_dict(cls, data: Dict) -> 'CrawlCompletedWebhook':
        """Create webhook instance from dictionary payload"""
        base = CrawlerWebhookBase.from_dict(data)
        return cls(
            event=base.event,
            uuid=base.uuid,
            timestamp=base.timestamp,
            status=data['status'],
            urls_discovered=data['urls_discovered'],
            urls_crawled=data['urls_crawled'],
            urls_failed=data['urls_failed']
        )


# Type alias for any crawler webhook
CrawlerWebhook = Union[
    CrawlStartedWebhook,
    CrawlUrlDiscoveredWebhook,
    CrawlUrlFailedWebhook,
    CrawlCompletedWebhook
]


def webhook_from_payload(
    payload: Dict,
    signing_secrets: Optional[Tuple[str]] = None,
    signature: Optional[str] = None
) -> CrawlerWebhook:
    """
    Create a typed webhook instance from a raw payload dictionary.

    This helper automatically determines the webhook type based on the 'event' field
    and returns the appropriate typed webhook instance.

    Args:
        payload: The webhook payload as a dictionary
        signing_secrets: Optional tuple of signing secrets (hex strings) for verification
        signature: Optional webhook signature header for verification

    Returns:
        A typed webhook instance (CrawlStartedWebhook, CrawlUrlDiscoveredWebhook, etc.)

    Raises:
        ValueError: If the event type is unknown
        WebhookSignatureMissMatch: If signature verification fails

    Example:
        ```python
        from scrapfly import webhook_from_payload

        # From Flask request
        @app.route('/webhook', methods=['POST'])
        def handle_webhook():
            webhook = webhook_from_payload(
                request.json,
                signing_secrets=('your-secret-key',),
                signature=request.headers.get('X-Scrapfly-Webhook-Signature')
            )

            if isinstance(webhook, CrawlCompletedWebhook):
                print(f"Crawl {webhook.uuid} completed!")
                print(f"Crawled {webhook.urls_crawled} URLs")

            return '', 200
        ```
    """
    # Verify signature if provided
    if signing_secrets and signature:
        from ..api_response import ResponseBodyHandler
        from json import dumps

        handler = ResponseBodyHandler(signing_secrets=signing_secrets)
        message = dumps(payload, separators=(',', ':')).encode('utf-8')
        if not handler.verify(message, signature):
            from ..errors import WebhookSignatureMissMatch
            raise WebhookSignatureMissMatch()

    # Determine event type and create appropriate webhook instance
    event = payload.get('event')

    if event == CrawlerWebhookEvent.STARTED.value:
        return CrawlStartedWebhook.from_dict(payload)
    elif event == CrawlerWebhookEvent.URL_DISCOVERED.value:
        return CrawlUrlDiscoveredWebhook.from_dict(payload)
    elif event == CrawlerWebhookEvent.URL_FAILED.value:
        return CrawlUrlFailedWebhook.from_dict(payload)
    elif event == CrawlerWebhookEvent.COMPLETED.value:
        return CrawlCompletedWebhook.from_dict(payload)
    else:
        raise ValueError(f"Unknown crawler webhook event type: {event}")
