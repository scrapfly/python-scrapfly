"""
Crawler API Webhook Models

Typed wrappers around the 8 real crawler webhook payloads emitted by the
scrape-engine. This module is the Python-side mirror of the authoritative
event list in
``apps/scrapfly/scrape-engine/scrape_engine/scrape_engine/crawler/webhook_manager.py``
(class ``WebhookEvents``) and the example payloads in
``apps/scrapfly/web-app/src/Template/Docs/crawler-api/webhooks_example/*.json``.

Design notes
------------
- Every webhook has the envelope ``{"event": <name>, "payload": {...}}``.
  There is **no** top-level ``uuid`` or ``timestamp`` field — the crawler UUID
  lives at ``payload.crawler_uuid`` and the only timing information is
  ``payload.state.start_time`` / ``payload.state.stop_time`` (unix epoch
  seconds, nullable during PENDING).
- All 5 payload shapes share these common fields: ``crawler_uuid``, ``project``,
  ``env``, ``action``, ``state``. They are modelled by :class:`CrawlerWebhookBase`.
- The 4 lifecycle events (``crawler_started`` / ``crawler_stopped`` /
  ``crawler_cancelled`` / ``crawler_finished``) share an identical shape — one
  dataclass handles all four.
- Field names match the wire format exactly. Missing required fields raise
  ``KeyError`` at parse time (strict parsing — same philosophy as
  :class:`CrawlerStatusResponse`).
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

from .crawler_response import CrawlerState


class CrawlerWebhookEvent(str, Enum):
    """
    Crawler webhook event names.

    These MUST stay in sync with
    ``apps/scrapfly/scrape-engine/scrape_engine/scrape_engine/crawler/webhook_manager.py``
    class ``WebhookEvents``. The scrape-engine is the source of truth.
    """

    CRAWLER_STARTED = 'crawler_started'
    CRAWLER_STOPPED = 'crawler_stopped'
    CRAWLER_CANCELLED = 'crawler_cancelled'
    CRAWLER_FINISHED = 'crawler_finished'
    CRAWLER_URL_VISITED = 'crawler_url_visited'
    CRAWLER_URL_SKIPPED = 'crawler_url_skipped'
    CRAWLER_URL_DISCOVERED = 'crawler_url_discovered'
    CRAWLER_URL_FAILED = 'crawler_url_failed'


# ---------------------------------------------------------------------------
# Base / common fields
# ---------------------------------------------------------------------------


@dataclass
class CrawlerWebhookBase:
    """
    Common fields carried by every crawler webhook payload.

    Attributes:
        event: The wire event name (``crawler_started``, etc.).
        crawler_uuid: The crawler job UUID.
        project: Project slug the crawler belongs to.
        env: Environment (``LIVE`` or ``TEST``).
        action: Short action tag emitted by the scrape-engine
            (``started``, ``visited``, ``skipped``, ``url_discovery``,
            ``failed``, ``stopped``, ``cancelled``, ``finished``).
        state: Nested state counters at the moment the webhook was emitted.
    """

    event: str
    crawler_uuid: str
    project: str
    env: str
    action: str
    state: CrawlerState

    @staticmethod
    def _parse_base(event: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Extract the 5 fields every webhook carries. Used by subclass
        ``from_payload()`` factories.
        """
        return {
            'event': event,
            'crawler_uuid': payload['crawler_uuid'],
            'project': payload['project'],
            'env': payload['env'],
            'action': payload['action'],
            'state': CrawlerState(payload['state']),
        }


# ---------------------------------------------------------------------------
# Lifecycle events: crawler_started / stopped / cancelled / finished
# All four share an identical payload shape, so one dataclass handles them.
# ---------------------------------------------------------------------------


@dataclass
class CrawlerLifecycleWebhook(CrawlerWebhookBase):
    """
    Payload for the 4 lifecycle events: ``crawler_started``,
    ``crawler_stopped``, ``crawler_cancelled``, ``crawler_finished``.

    These events all carry the same fields: the seed URL, the common base
    (crawler_uuid / project / env / action / state), and a ``links.status``
    URL pointing at the crawl status endpoint. Disambiguate by inspecting
    ``self.event`` (use :class:`CrawlerWebhookEvent`).

    Attributes:
        seed_url: The root URL the crawl was started from.
        status_link: URL to fetch the live crawler status.
    """

    seed_url: str
    status_link: str

    @classmethod
    def from_payload(cls, event: str, payload: Dict[str, Any]) -> 'CrawlerLifecycleWebhook':
        base = cls._parse_base(event, payload)
        return cls(
            **base,
            seed_url=payload['seed_url'],
            status_link=payload['links']['status'],
        )


# ---------------------------------------------------------------------------
# crawler_url_visited
# ---------------------------------------------------------------------------


@dataclass
class CrawlerScrapeResult:
    """
    The ``scrape`` sub-object of a ``crawler_url_visited`` payload.

    Attributes:
        status_code: HTTP status code returned by the target URL.
        country: 2-letter country code of the proxy that performed the scrape.
        log_uuid: ULID of the scrape log (used to fetch the full log later).
        log_url: Human-browseable dashboard URL for the log.
        content: Map of requested content format (``html``, ``text``,
            ``markdown``, ``clean_html``, ``json``, etc.) to the actual
            rendered string. The keys depend on what the caller requested
            in ``content_formats``.
    """

    status_code: int
    country: str
    log_uuid: str
    log_url: str
    content: Dict[str, Any]

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CrawlerScrapeResult':
        return cls(
            status_code=data['status_code'],
            country=data['country'],
            log_uuid=data['log_uuid'],
            log_url=data['log_url'],
            content=data['content'],
        )


@dataclass
class CrawlerUrlVisitedWebhook(CrawlerWebhookBase):
    """
    Payload for the ``crawler_url_visited`` event.

    Emitted after each URL has been successfully scraped.

    Attributes:
        url: The URL that was just visited.
        scrape: Scrape result details (status code, country, log link, content).
    """

    url: str
    scrape: CrawlerScrapeResult

    @classmethod
    def from_payload(cls, event: str, payload: Dict[str, Any]) -> 'CrawlerUrlVisitedWebhook':
        base = cls._parse_base(event, payload)
        return cls(
            **base,
            url=payload['url'],
            scrape=CrawlerScrapeResult.from_dict(payload['scrape']),
        )


# ---------------------------------------------------------------------------
# crawler_url_skipped
# ---------------------------------------------------------------------------


@dataclass
class CrawlerUrlSkippedWebhook(CrawlerWebhookBase):
    """
    Payload for the ``crawler_url_skipped`` event.

    Emitted in a single batch when the crawler decides to skip a set of
    URLs (e.g. when reaching ``page_limit`` with discovered-but-unvisited
    URLs still in the queue).

    Attributes:
        urls: Mapping from URL to the reason it was skipped
            (e.g. ``"page_limit"``, ``"excluded"``, ``"robots_txt"``).
    """

    urls: Dict[str, str]

    @classmethod
    def from_payload(cls, event: str, payload: Dict[str, Any]) -> 'CrawlerUrlSkippedWebhook':
        base = cls._parse_base(event, payload)
        return cls(**base, urls=payload['urls'])


# ---------------------------------------------------------------------------
# crawler_url_discovered
# ---------------------------------------------------------------------------


@dataclass
class CrawlerUrlDiscoveredWebhook(CrawlerWebhookBase):
    """
    Payload for the ``crawler_url_discovered`` event.

    Emitted when the crawler extracts one or more new URLs from a source.

    Attributes:
        origin: How the URLs were discovered (e.g. ``"navigation"``,
            ``"sitemap"``).
        discovered_urls: The newly-discovered URLs as a list.
    """

    origin: str
    discovered_urls: List[str]

    @classmethod
    def from_payload(cls, event: str, payload: Dict[str, Any]) -> 'CrawlerUrlDiscoveredWebhook':
        base = cls._parse_base(event, payload)
        return cls(
            **base,
            origin=payload['origin'],
            discovered_urls=payload['discovered_urls'],
        )


# ---------------------------------------------------------------------------
# crawler_url_failed
# ---------------------------------------------------------------------------


@dataclass
class CrawlerUrlFailedWebhook(CrawlerWebhookBase):
    """
    Payload for the ``crawler_url_failed`` event.

    Emitted when a URL cannot be crawled (network error, scrape error,
    blocked, etc.).

    Attributes:
        url: The URL that failed.
        error: The scrapfly error code (e.g. ``ERR::SCRAPE::NETWORK_ERROR``).
        scrape_config: The scrape config that was used for the failed attempt.
        log_link: URL to the full scrape log for this failure. Can be
            ``None`` — the scrape-engine emits ``null`` when no log was
            recorded (e.g. the failure happened before the request was ever
            executed). See
            ``scrape_engine/crawler/webhook_manager.py::dispatch_url_failed``
            line 57.
        scrape_link: URL that re-runs the same scrape as a one-off. Always
            present on the wire (non-nullable). See line 58 of the engine.
    """

    url: str
    error: str
    scrape_config: Dict[str, Any]
    log_link: Optional[str]
    scrape_link: str

    @classmethod
    def from_payload(cls, event: str, payload: Dict[str, Any]) -> 'CrawlerUrlFailedWebhook':
        base = cls._parse_base(event, payload)
        return cls(
            **base,
            url=payload['url'],
            error=payload['error'],
            scrape_config=payload['scrape_config'],
            log_link=payload['links'].get('log'),
            scrape_link=payload['links']['scrape'],
        )


# ---------------------------------------------------------------------------
# Type alias + dispatcher
# ---------------------------------------------------------------------------


CrawlerWebhook = Union[
    CrawlerLifecycleWebhook,
    CrawlerUrlVisitedWebhook,
    CrawlerUrlSkippedWebhook,
    CrawlerUrlDiscoveredWebhook,
    CrawlerUrlFailedWebhook,
]


# Dispatch table: event name → parser class
_DISPATCH = {
    CrawlerWebhookEvent.CRAWLER_STARTED.value:       CrawlerLifecycleWebhook,
    CrawlerWebhookEvent.CRAWLER_STOPPED.value:       CrawlerLifecycleWebhook,
    CrawlerWebhookEvent.CRAWLER_CANCELLED.value:     CrawlerLifecycleWebhook,
    CrawlerWebhookEvent.CRAWLER_FINISHED.value:      CrawlerLifecycleWebhook,
    CrawlerWebhookEvent.CRAWLER_URL_VISITED.value:   CrawlerUrlVisitedWebhook,
    CrawlerWebhookEvent.CRAWLER_URL_SKIPPED.value:   CrawlerUrlSkippedWebhook,
    CrawlerWebhookEvent.CRAWLER_URL_DISCOVERED.value: CrawlerUrlDiscoveredWebhook,
    CrawlerWebhookEvent.CRAWLER_URL_FAILED.value:    CrawlerUrlFailedWebhook,
}


def webhook_from_payload(
    payload: Dict[str, Any],
    signing_secrets: Optional[Tuple[str, ...]] = None,
    signature: Optional[str] = None,
) -> CrawlerWebhook:
    """
    Parse a raw crawler webhook envelope into a typed dataclass.

    The envelope shape is ``{"event": <name>, "payload": {...}}``. This
    function inspects ``event`` and returns the corresponding typed
    dataclass — one of :data:`CrawlerWebhook`.

    Args:
        payload: The full webhook body as a dict (i.e. what you get from
            ``request.json``).
        signing_secrets: Optional tuple of signing secrets (hex strings) for
            signature verification.
        signature: Optional webhook signature header value
            (``X-Scrapfly-Webhook-Signature``).

    Returns:
        A typed webhook instance matching the event.

    Raises:
        KeyError: If the envelope is missing required fields.
        ValueError: If ``event`` is not one of the known crawler events.
        WebhookSignatureMissMatch: If signature verification fails.

    Example:
        >>> from flask import Flask, request
        >>> from scrapfly import webhook_from_payload, CrawlerLifecycleWebhook
        >>> app = Flask(__name__)
        >>> @app.route('/webhook', methods=['POST'])
        ... def handle_webhook():
        ...     wh = webhook_from_payload(
        ...         request.json,
        ...         signing_secrets=('your-secret-hex',),
        ...         signature=request.headers.get('X-Scrapfly-Webhook-Signature'),
        ...     )
        ...     if isinstance(wh, CrawlerLifecycleWebhook) and wh.event == 'crawler_finished':
        ...         print(f"Crawl {wh.crawler_uuid} finished — "
        ...               f"{wh.state.urls_visited} URLs visited")
        ...     return '', 200
    """
    if signing_secrets and signature:
        from json import dumps

        from ..api_response import ResponseBodyHandler
        from ..errors import WebhookSignatureMissMatch

        handler = ResponseBodyHandler(signing_secrets=signing_secrets)
        message = dumps(payload, separators=(',', ':')).encode('utf-8')
        if not handler.verify(message, signature):
            raise WebhookSignatureMissMatch()

    event = payload['event']
    inner = payload['payload']

    parser = _DISPATCH.get(event)
    if parser is None:
        raise ValueError(
            f"Unknown crawler webhook event: {event!r}. "
            f"Expected one of: {sorted(_DISPATCH.keys())}"
        )
    return parser.from_payload(event, inner)
