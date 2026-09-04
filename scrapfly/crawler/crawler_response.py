"""
Crawler API Response Classes

This module provides response wrapper classes for the Crawler API.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Iterator, List, Union
from .warc_utils import WarcParser, WarcRecord, parse_warc
from .har_utils import HarArchive, HarEntry


class CrawlerStartResponse:
    """
    Response from starting a crawler job

    Returned by ScrapflyClient.start_crawl() method.

    Strict parsing: ``uuid`` and ``status`` are part of the documented contract
    and are required. A missing field raises ``KeyError`` so the caller knows
    immediately that the API contract changed.

    Attributes:
        uuid: Unique identifier for the crawler job
        status: Initial status (typically 'PENDING')
    """

    def __init__(self, response_data: Dict[str, Any]):
        """
        Initialize from API response

        Args:
            response_data: Raw API response dictionary
        """
        self._data = response_data
        # API canonical name is `crawler_uuid`; we accept `uuid` only as a
        # legacy fallback, in case an older server emits the short form.
        if 'crawler_uuid' in response_data:
            self.uuid = response_data['crawler_uuid']
        elif 'uuid' in response_data:
            self.uuid = response_data['uuid']
        else:
            raise KeyError(
                "CrawlerStartResponse: required field 'crawler_uuid' (or legacy 'uuid') is missing"
            )
        self.status = response_data['status']
        assert isinstance(self.uuid, str) and self.uuid, (
            f"CrawlerStartResponse: uuid must be a non-empty string, got {self.uuid!r}"
        )
        assert isinstance(self.status, str) and self.status, (
            f"CrawlerStartResponse: status must be a non-empty string, got {self.status!r}"
        )

    def __repr__(self):
        return f"CrawlerStartResponse(uuid={self.uuid}, status={self.status})"


class CrawlerState:
    """
    Nested ``state`` block of a crawler status response.

    Field names match the wire format emitted by Scrapfly, which
    is the single source of truth. Go and TypeScript SDKs expose the same
    names on their ``status.state`` object.

    Attributes:
        urls_visited: Number of URLs successfully crawled.
        urls_extracted: Total URLs discovered (seed + links + sitemaps).
        urls_to_crawl: Derived as ``urls_extracted - urls_skipped`` server-side.
        urls_failed: URLs that failed to crawl.
        urls_skipped: URLs skipped (filtered by exclude rules, robots.txt, etc.).
        api_credit_used: Total API credits consumed by this crawl.
        duration: Elapsed time in seconds.
        start_time: Unix epoch seconds when the first worker picked up the job,
            or ``None`` while the job is still in ``PENDING``.
        stop_time: Unix epoch seconds when the crawler reached a terminal state,
            or ``None`` while still running.
        stop_reason: Reason for stop (``page_limit``, ``max_duration``, etc.),
            or ``None`` while still running.
    """

    __slots__ = (
        'urls_visited', 'urls_extracted', 'urls_to_crawl',
        'urls_failed', 'urls_skipped',
        'api_credit_used', 'duration',
        'start_time', 'stop_time', 'stop_reason',
    )

    def __init__(self, state: Dict[str, Any]):
        assert isinstance(state, dict), (
            f"CrawlerState: expected dict, got {type(state).__name__}"
        )
        self.urls_visited: int = state['urls_visited']
        self.urls_extracted: int = state['urls_extracted']
        self.urls_to_crawl: int = state['urls_to_crawl']
        self.urls_failed: int = state['urls_failed']
        self.urls_skipped: int = state['urls_skipped']
        self.api_credit_used = state['api_credit_used']
        self.duration = state['duration']
        # Nullable during PENDING — before a worker has picked up the job.
        self.start_time: Optional[int] = state.get('start_time')
        self.stop_time: Optional[int] = state.get('stop_time')
        self.stop_reason: Optional[str] = state.get('stop_reason')

    def __repr__(self):
        return (
            f"CrawlerState(visited={self.urls_visited}, extracted={self.urls_extracted}, "
            f"to_crawl={self.urls_to_crawl}, failed={self.urls_failed}, "
            f"skipped={self.urls_skipped})"
        )


class CrawlerStatusResponse:
    """
    Response from checking crawler job status.

    Returned by :py:meth:`ScrapflyClient.get_crawl_status`. Provides real-time
    progress tracking for crawler jobs.

    **Field names match the wire format.** Scrapfly is the source of
    truth; the Go and TypeScript SDKs expose identical names. Access state
    counters via the nested ``state`` attribute:

        >>> status.state.urls_visited
        12
        >>> status.state.urls_extracted
        34

    Attributes:
        uuid: Crawler job UUID.
        status: Current status (``PENDING``, ``RUNNING``, ``DONE``, ``CANCELLED``).
        is_success: Whether the crawler job completed successfully (``None`` while running).
        is_finished: Whether the crawler job has finished (regardless of success/failure).
        state: :class:`CrawlerState` — all the per-crawl counters and timings.
        search: :class:`CrawlerSearchState` when the crawl was started with
            ``search=True``, otherwise ``None``.
        refresh: :class:`CrawlerRefreshState` when the crawl re-scrapes itself
            on a period, otherwise ``None``.
    """

    # Status constants
    STATUS_PENDING = 'PENDING'
    STATUS_RUNNING = 'RUNNING'
    STATUS_DONE = 'DONE'
    STATUS_CANCELLED = 'CANCELLED'

    def __init__(self, response_data: Dict[str, Any]):
        """
        Initialize from API response.

        Strict parsing: required fields (``crawler_uuid``, ``status``,
        ``is_success``, ``is_finished``, and the documented ``state.*``
        metrics) are read with direct access so missing keys raise
        ``KeyError`` at parse time. This catches API contract drift loud and
        early.

        Args:
            response_data: Raw API response dictionary.
        """
        self._data = response_data

        # Identification — accept legacy `uuid` only as fallback.
        if 'crawler_uuid' in response_data:
            self.uuid = response_data['crawler_uuid']
        elif 'uuid' in response_data:
            self.uuid = response_data['uuid']
        else:
            raise KeyError(
                "CrawlerStatusResponse: required field 'crawler_uuid' (or legacy 'uuid') is missing"
            )
        self.status = response_data['status']
        # `is_success` may legitimately be `null` while still running.
        self.is_success = response_data['is_success']
        self.is_finished = response_data['is_finished']

        assert isinstance(self.uuid, str) and self.uuid, (
            f"CrawlerStatusResponse: uuid must be a non-empty string, got {self.uuid!r}"
        )
        assert isinstance(self.status, str) and self.status, (
            f"CrawlerStatusResponse: status must be a non-empty string, got {self.status!r}"
        )
        assert isinstance(self.is_finished, bool), (
            f"CrawlerStatusResponse: is_finished must be bool, got {type(self.is_finished).__name__}"
        )
        assert self.is_success is None or isinstance(self.is_success, bool), (
            f"CrawlerStatusResponse: is_success must be bool or None, got {type(self.is_success).__name__}"
        )

        # Nested state — canonical shape matching Go / TS SDKs.
        self.state = CrawlerState(response_data['state'])

        # Search index state. Optional: only crawls started with search=True
        # carry the block, and older API builds omit it entirely.
        search = response_data.get('search')
        self.search: Optional[CrawlerSearchState] = (
            CrawlerSearchState.from_dict(search) if search else None
        )

        # Auto-refresh state. Optional: only crawls that re-scrape themselves
        # carry the block. Built from the whole payload rather than the nested
        # dict because CrawlerRefreshState accepts either envelope.
        self.refresh: Optional[CrawlerRefreshState] = (
            CrawlerRefreshState(response_data)
            if isinstance(response_data.get('refresh'), dict) else None
        )

    @property
    def is_complete(self) -> bool:
        """Whether the crawler reached DONE with is_success=True."""
        return self.status == self.STATUS_DONE and self.is_success is True

    @property
    def is_running(self) -> bool:
        """Whether the crawler is currently PENDING or RUNNING."""
        return self.status in (self.STATUS_PENDING, self.STATUS_RUNNING)

    @property
    def is_failed(self) -> bool:
        """Whether the crawler reached DONE with is_success=False."""
        return self.status == self.STATUS_DONE and self.is_success is False

    @property
    def is_cancelled(self) -> bool:
        """Whether the crawler was cancelled."""
        return self.status == self.STATUS_CANCELLED

    @property
    def progress_pct(self) -> float:
        """
        Visited/extracted ratio as a percentage (0-100).

        Returns 0.0 when no URLs have been extracted yet.
        """
        if self.state.urls_extracted == 0:
            return 0.0
        return (self.state.urls_visited / self.state.urls_extracted) * 100

    def __repr__(self):
        return (f"CrawlerStatusResponse(uuid={self.uuid}, status={self.status}, "
                f"progress={self.progress_pct:.1f}%, "
                f"visited={self.state.urls_visited}/{self.state.urls_extracted})")


class CrawlerUrlEntry:
    """
    Single URL entry from ``GET /crawl/{uuid}/urls``.

    The endpoint streams one record per line as ``text/plain``. For
    ``visited`` and ``pending`` URLs each line is just the URL; for ``failed``
    or ``skipped`` URLs the line is ``url,reason``. Streaming text is used
    because this endpoint is expected to scale to millions of records per
    job — JSON is not a suitable wire format at that volume.

    Attributes:
        url: The crawled URL
        status: The filter status used by the caller (``visited``, ``pending``,
            ``failed`` or ``skipped``). Echoed from the request parameter so
            downstream code can disambiguate mixed buffers.
        reason: Only set for ``failed`` / ``skipped`` URLs; ``None`` otherwise.
    """

    __slots__ = ('url', 'status', 'reason')

    def __init__(self, url: str, status: str, reason: Optional[str] = None):
        assert isinstance(url, str) and url, (
            f"CrawlerUrlEntry: url must be a non-empty string, got {url!r}"
        )
        assert isinstance(status, str) and status, (
            f"CrawlerUrlEntry: status must be a non-empty string, got {status!r}"
        )
        self.url = url
        self.status = status
        self.reason = reason

    def __repr__(self):
        if self.reason is not None:
            return f"CrawlerUrlEntry(url={self.url!r}, status={self.status!r}, reason={self.reason!r})"
        return f"CrawlerUrlEntry(url={self.url!r}, status={self.status!r})"


class CrawlerUrlsResponse:
    """
    Response from ``GET /crawl/{crawler_uuid}/urls``.

    The server returns a streaming ``text/plain`` body with one record per
    line. This class parses that stream into a materialised ``List`` of
    :class:`CrawlerUrlEntry` records for caller convenience.

    Pagination: the wire protocol carries no global ``total``, and the API
    forwards only the status filter to the crawler, so ``page`` and
    ``per_page`` are echoes of the caller's request parameters over a body
    that already holds the whole server-side page.

    Attributes:
        urls: List of :class:`CrawlerUrlEntry` records on this page
        page: 1-based page number (echoed from the request)
        per_page: Page size (echoed from the request)
    """

    __slots__ = ('urls', 'page', 'per_page')

    def __init__(self, urls: List['CrawlerUrlEntry'], page: int, per_page: int):
        self.urls = urls
        self.page = page
        self.per_page = per_page

    @classmethod
    def from_text(
        cls,
        body: str,
        status_hint: str,
        page: int,
        per_page: int,
    ) -> 'CrawlerUrlsResponse':
        """
        Parse the raw text body returned by ``GET /crawl/{uuid}/urls``.

        - Empty lines are ignored (trailing newlines, blank records).
        - For ``visited`` / ``pending`` status each line is one URL.
        - For ``failed`` / ``skipped`` status each line is ``url,reason``.
        - When the caller passed no ``status`` filter, the server defaults to
          ``visited``; the caller is expected to pass that as ``status_hint``
          so every parsed record gets the right status tag.

        Args:
            body: Raw response body text.
            status_hint: The status filter the caller used.
            page: Caller-provided page (echoed on the response object).
            per_page: Caller-provided per_page (echoed on the response object).
        """
        entries: List[CrawlerUrlEntry] = []
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line:
                continue
            if status_hint in ('visited', 'pending'):
                entries.append(CrawlerUrlEntry(url=line, status=status_hint))
            else:
                # `url,reason` — split on the first comma only. URLs never
                # contain an unencoded comma in the path/query, so this is
                # unambiguous.
                comma_idx = line.find(',')
                if comma_idx == -1:
                    entries.append(CrawlerUrlEntry(url=line, status=status_hint))
                else:
                    entries.append(
                        CrawlerUrlEntry(
                            url=line[:comma_idx],
                            status=status_hint,
                            reason=line[comma_idx + 1:] or None,
                        )
                    )
        return cls(entries, page, per_page)

    def __len__(self) -> int:
        return len(self.urls)

    def __iter__(self) -> Iterator[CrawlerUrlEntry]:
        return iter(self.urls)

    def __repr__(self):
        return (
            f"CrawlerUrlsResponse(page={self.page}, per_page={self.per_page}, "
            f"urls={len(self.urls)})"
        )



@dataclass
class CrawlerSearchState:
    """
    The ``search`` block describing a crawl's index, as carried by
    ``GET /crawl/{uuid}/status`` and by the two search webhooks.

    Attributes:
        status: ``DISABLED``, ``BUILDING``, ``READY``, ``PARTIAL`` or ``FAILED``.
            Only ``READY`` and ``PARTIAL`` are searchable.
        manifest: Storage path of the index manifest, ``None`` until the
            artifact is published.
        documents: Crawled documents represented in the index.
        vectors: Embedded chunks.
        dropped: Chunks discarded during the build (embedding failures,
            oversized rows).
        queue_depth: Chunks still waiting to be embedded at snapshot time.
        fragments: Published Lance fragments.
        error: Failure reason when ``status`` is ``FAILED``.
        built_at: ISO-8601 timestamp of the terminal publish.
        index: Vector index type (e.g. ``IVF_PQ``), ``None`` when the row
            count stayed below the index threshold.
        generation: Build generation, bumped when a paused crawl resumes and
            rebuilds. Results from different generations are not comparable.
    """

    status: str
    manifest: Optional[str] = None
    documents: Optional[int] = None
    vectors: Optional[int] = None
    dropped: Optional[int] = None
    queue_depth: Optional[int] = None
    fragments: Optional[int] = None
    error: Optional[str] = None
    built_at: Optional[str] = None
    index: Optional[str] = None
    generation: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CrawlerSearchState':
        return cls(
            status=data['status'],
            manifest=data.get('manifest'),
            documents=data.get('documents'),
            vectors=data.get('vectors'),
            dropped=data.get('dropped'),
            queue_depth=data.get('queue_depth'),
            fragments=data.get('fragments'),
            error=data.get('error'),
            built_at=data.get('built_at'),
            index=data.get('index'),
            generation=data.get('generation'),
        )

    @property
    def is_searchable(self) -> bool:
        """Whether the index can answer a query right now."""
        return self.status in ('READY', 'PARTIAL')


@dataclass
class CrawlerSearchResult:
    """
    One matched chunk from ``POST /crawl/search``.

    A result is a *chunk*, not a page: ``chunk_id`` orders chunks within one
    crawled document and ``text`` is only the matched slice. Use
    ``contents_url`` (or ``warc_offset``/``warc_end``) to expand a hit back to
    the full document.

    Attributes:
        rank: 1-based position in the merged ranking.
        score: The ranking score used for ordering (RRF in hybrid mode).
        scores: Per-leg scores (``vector``, ``fts``, ``rrf``); which keys are
            present depends on the mode.
        crawler_uuid: The crawl this chunk came from.
        url: The crawled URL.
        title: Document title, ``None`` when the page had none.
        source_format: Which stored format was indexed (``markdown``, ``text``,
            ``clean_html``, ``html``).
        content_type: Content type of the stored document.
        chunk_id: Chunk index within the document.
        text: The matched chunk text.
        warc_offset: Byte offset of the document record in the crawl WARC.
        warc_end: End byte offset of that record.
        contents_url: Ready-made ``/crawl/{uuid}/contents`` URL for the
            document this chunk belongs to.
    """

    rank: int
    score: float
    crawler_uuid: str
    url: str
    chunk_id: int
    text: str
    scores: Dict[str, float] = field(default_factory=dict)
    title: Optional[str] = None
    source_format: Optional[str] = None
    content_type: Optional[str] = None
    warc_offset: Optional[int] = None
    warc_end: Optional[int] = None
    contents_url: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CrawlerSearchResult':
        return cls(
            rank=data['rank'],
            score=data['score'],
            crawler_uuid=data['crawler_uuid'],
            url=data['url'],
            chunk_id=data['chunk_id'],
            text=data['text'],
            scores=data.get('scores') or {},
            title=data.get('title'),
            source_format=data.get('source_format'),
            content_type=data.get('content_type'),
            warc_offset=data.get('warc_offset'),
            warc_end=data.get('warc_end'),
            contents_url=data.get('contents_url'),
        )


@dataclass
class CrawlerSearchCrawl:
    """A crawl that was actually opened and searched."""

    crawler_uuid: str
    documents: Optional[int] = None
    vectors: Optional[int] = None
    index: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CrawlerSearchCrawl':
        return cls(
            crawler_uuid=data['crawler_uuid'],
            documents=data.get('documents'),
            vectors=data.get('vectors'),
            index=data.get('index'),
        )


@dataclass
class CrawlerSearchSkipped:
    """
    A requested crawl that contributed nothing, and why.

    Skips are never fatal: the search still answers with whatever the other
    crawls returned. ``reason`` is one of ``search_not_enabled``,
    ``search_not_ready``, ``search_failed``, ``search_disabled``,
    ``incompatible_index``, ``deadline``.
    """

    crawler_uuid: str
    reason: str
    status: Optional[str] = None

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CrawlerSearchSkipped':
        return cls(
            crawler_uuid=data['crawler_uuid'],
            reason=data['reason'],
            status=data.get('status'),
        )


class CrawlerSearchResponse:
    """
    Response from ``POST /crawl/search``.

    Returned by :py:meth:`ScrapflyClient.crawl_search`.

    The envelope states its own completeness: ``completeness == 'exact'`` with
    most crawls unopened is the normal outcome, because the fan-out proves via
    an admissible bound that the unopened crawls held nothing better.
    ``'partial'`` means the deadline cut the fan-out short.

    Attributes:
        query: The query as the server understood it.
        mode: ``vector``, ``fts`` or ``hybrid``.
        limit: The effective result cap.
        completeness: ``exact`` or ``partial``.
        results: Ranked :class:`CrawlerSearchResult` list.
        crawls: Crawls that were opened and searched.
        skipped: Requested crawls that contributed nothing, with a reason.
        stats: Timing/IO counters (``duration_ms``, ``crawls_searched``,
            ``candidates``, ``gcs_gets``).
        crawls_skipped_deadline: Crawler UUIDs the deadline cut before their
            leg ran.
        crawls_failed: Crawls whose leg errored, as
            :class:`CrawlerSearchSkipped` rows.
        cursor: Opaque token for the next page, ``None`` on the last page.
            Paging is cursor-based: an offset over a partial fan-out would
            re-run the legs and shift ranks.
    """

    def __init__(self, response_data: Dict[str, Any]):
        self._data = response_data

        self.query: str = response_data['query']
        self.mode: str = response_data['mode']
        self.limit: int = response_data['limit']
        self.completeness: str = response_data['completeness']

        self.results: List[CrawlerSearchResult] = [
            CrawlerSearchResult.from_dict(r) for r in response_data['results']
        ]
        self.crawls: List[CrawlerSearchCrawl] = [
            CrawlerSearchCrawl.from_dict(c) for c in (response_data.get('crawls') or [])
        ]
        self.skipped: List[CrawlerSearchSkipped] = [
            CrawlerSearchSkipped.from_dict(s) for s in (response_data.get('skipped') or [])
        ]
        self.stats: Dict[str, Any] = response_data.get('stats') or {}

        self.crawls_requested: Optional[int] = response_data.get('crawls_requested')
        self.crawls_searched: Optional[int] = response_data.get('crawls_searched')
        self.crawls_pruned_exact: Optional[int] = response_data.get('crawls_pruned_exact')
        # These two name the crawls, they do not count them: a caller told
        # "3 failed" cannot act on it, and the crawls it can retry are the ones
        # the deadline cut.
        self.crawls_skipped_deadline: List[str] = list(
            response_data.get('crawls_skipped_deadline') or []
        )
        self.crawls_failed: List[CrawlerSearchSkipped] = [
            CrawlerSearchSkipped.from_dict(c) for c in (response_data.get('crawls_failed') or [])
        ]
        self.theta: Optional[float] = response_data.get('theta')
        self.max_ub_unsearched: Optional[float] = response_data.get('max_ub_unsearched')

        self.cursor: Optional[str] = response_data.get('cursor')

    @property
    def is_exact(self) -> bool:
        """Whether the ranking is provably complete for the requested crawls."""
        return self.completeness == 'exact'

    def __len__(self) -> int:
        return len(self.results)

    def __iter__(self) -> Iterator[CrawlerSearchResult]:
        return iter(self.results)

    def __repr__(self):
        return (
            f"CrawlerSearchResponse(query={self.query!r}, mode={self.mode}, "
            f"results={len(self.results)}, completeness={self.completeness}, "
            f"skipped={len(self.skipped)})"
        )


@dataclass
class CrawlerPromptEvent:
    """
    One frame of the ``POST /crawl/prompt`` SSE stream.

    Frame order is ``source``* → ``token``* → (``error``) → ``done``.
    Keepalive comment frames are consumed by the reader and never surfaced.

    Attributes:
        event: ``source``, ``token``, ``error`` or ``done``.
        data: The decoded frame payload: a str for ``token``, a dict for the
            other three.
    """

    event: str
    data: Any

    @property
    def is_token(self) -> bool:
        return self.event == 'token'

    @property
    def is_done(self) -> bool:
        return self.event == 'done'


@dataclass
class CrawlerRefreshEntry:
    """
    One row of a crawl's refresh timeline.

    Counts describe the whole run; ``sample_updated`` / ``sample_removed``
    carry at most ten URLs each. The full URL lists are never inlined, so a
    5,000-page crawl does not put 5,000 strings into every status poll.

    Attributes:
        at: ISO-8601 timestamp of the run.
        generation: Refresh generation this run produced, 1 for the first.
        added: URLs discovered by this run that the crawl did not hold.
        updated: Known URLs whose content fingerprint changed.
        removed: Known URLs that no longer exist and were dropped.
        unchanged: Known URLs re-scraped with an identical fingerprint. These
            cost no embedding and no index write.
        failed: URLs the run could not fetch. They keep their previous content.
        duration_ms: Wall time of the run.
        search_status: Index status after the run, ``None`` when the crawl has
            no search index.
        error: Failure reason when the run itself failed.
        sample_updated: Up to ten re-indexed URLs.
        sample_removed: Up to ten dropped URLs.
    """

    at: Optional[str] = None
    generation: Optional[int] = None
    added: int = 0
    updated: int = 0
    removed: int = 0
    unchanged: int = 0
    failed: int = 0
    duration_ms: Optional[int] = None
    search_status: Optional[str] = None
    error: Optional[str] = None
    sample_updated: List[str] = field(default_factory=list)
    sample_removed: List[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CrawlerRefreshEntry':
        return cls(
            at=data.get('at'),
            generation=data.get('generation'),
            added=data.get('added') or 0,
            updated=data.get('updated') or 0,
            removed=data.get('removed') or 0,
            unchanged=data.get('unchanged') or 0,
            failed=data.get('failed') or 0,
            duration_ms=data.get('duration_ms'),
            search_status=data.get('search_status'),
            error=data.get('error'),
            sample_updated=list(data.get('sample_updated') or []),
            sample_removed=list(data.get('sample_removed') or []),
        )

    @property
    def changed(self) -> int:
        """Pages the run actually touched. Zero means the site stood still."""
        return self.added + self.updated + self.removed


class CrawlerRefreshState:
    """
    The ``refresh`` block of a crawl, as carried by
    ``GET /crawl/{uuid}/status`` and returned by the three refresh calls.

    Attributes:
        enabled: Whether the crawl re-scrapes itself on a period.
        interval_seconds: Period between runs, 0 when disabled.
        status: ``DISABLED``, ``SCHEDULED``, ``RUNNING`` or ``FAILED``.
        generation: Number of refresh runs completed so far.
        last_run_at: ISO-8601 timestamp of the last completed run.
        next_run_at: ISO-8601 timestamp of the next due run, ``None`` when
            disabled.
        started_at: ISO-8601 start of the run in flight, ``None`` unless
            ``status`` is ``RUNNING``. Rendered by ``GET /crawl/{uuid}/status``
            only.
        consecutive_failures: Failed runs since the last success, back to 0 on
            any success. Same status-only route as ``started_at``.
        error: Failure reason when ``status`` is ``FAILED``.
        history: Newest-last timeline, capped at the 50 most recent runs.
    """

    def __init__(self, response_data: Dict[str, Any]):
        self._data = response_data

        # The three refresh endpoints answer with the state at the top level;
        # GET /status nests it under "refresh". One lookup, so the isinstance
        # narrowing holds for every read below it.
        nested = response_data.get('refresh')
        block = nested if isinstance(nested, dict) else response_data

        self.enabled: bool = bool(block.get('enabled', False))
        self.interval_seconds: int = int(block.get('interval_seconds') or 0)
        self.status: str = block.get('status') or 'DISABLED'
        self.generation: int = int(block.get('generation') or 0)
        self.last_run_at: Optional[str] = block.get('last_run_at')
        self.next_run_at: Optional[str] = block.get('next_run_at')
        # ``GET /crawl/{uuid}/status`` relays the engine's refresh block
        # verbatim; the three refresh calls render a typed block that declares
        # neither of these, so both have to survive their absence.
        self.started_at: Optional[str] = block.get('started_at')
        self.consecutive_failures: int = int(block.get('consecutive_failures') or 0)
        self.error: Optional[str] = block.get('error')
        self.history: List[CrawlerRefreshEntry] = [
            CrawlerRefreshEntry.from_dict(e) for e in (block.get('history') or [])
        ]

    @property
    def is_running(self) -> bool:
        """Whether a refresh run is in flight right now."""
        return self.status == 'RUNNING'

    @property
    def last_run(self) -> Optional[CrawlerRefreshEntry]:
        """Most recent timeline row, ``None`` before the first run."""
        return self.history[-1] if self.history else None

    def __len__(self) -> int:
        return len(self.history)

    def __iter__(self) -> Iterator[CrawlerRefreshEntry]:
        return iter(self.history)

    def __repr__(self):
        return (
            f"CrawlerRefreshState(enabled={self.enabled}, status={self.status}, "
            f"interval_seconds={self.interval_seconds}, generation={self.generation}, "
            f"next_run_at={self.next_run_at!r})"
        )


class CrawlerArtifactResponse:
    """
    Response from downloading crawler artifacts

    Returned by ScrapflyClient.get_crawl_artifact() method.

    Provides high-level access to crawl results with automatic WARC/HAR parsing.
    Users don't need to understand WARC or HAR format to use this class.

    Example:
        ```python
        # Get WARC artifact (default)
        artifact = client.get_crawl_artifact(uuid)

        # Get HAR artifact
        artifact = client.get_crawl_artifact(uuid, artifact_type='har')

        # Easy mode: get all pages as dicts
        pages = artifact.get_pages()
        for page in pages:
            print(f"{page['url']}: {page['status_code']}")
            html = page['content'].decode('utf-8')

        # Memory-efficient: iterate one page at a time
        for record in artifact.iter_responses():
            print(f"{record.url}: {record.status_code}")
            process(record.content)

        # Save to file
        artifact.save('crawl_results.warc.gz')
        ```
    """

    def __init__(self, artifact_data: bytes, artifact_type: str = 'warc'):
        """
        Initialize from artifact data

        Args:
            artifact_data: Raw artifact file bytes
            artifact_type: Type of artifact ('warc' or 'har')
        """
        self._artifact_data = artifact_data
        self._artifact_type = artifact_type
        self._warc_parser: Optional[WarcParser] = None
        self._har_parser: Optional[HarArchive] = None

    @property
    def artifact_type(self) -> str:
        """Get artifact type ('warc' or 'har')"""
        return self._artifact_type

    @property
    def artifact_data(self) -> bytes:
        """Get raw artifact data (for advanced users)"""
        return self._artifact_data

    @property
    def warc_data(self) -> bytes:
        """Get raw WARC data (deprecated, use artifact_data)"""
        return self._artifact_data

    @property
    def parser(self) -> Union[WarcParser, HarArchive]:
        """Get artifact parser instance (lazy-loaded)"""
        if self._artifact_type == 'har':
            if self._har_parser is None:
                self._har_parser = HarArchive(self._artifact_data)
            return self._har_parser
        else:
            if self._warc_parser is None:
                self._warc_parser = parse_warc(self._artifact_data)
            return self._warc_parser

    def iter_records(self) -> Iterator[Union[WarcRecord, HarEntry]]:
        """
        Iterate through all records

        For WARC: iterates through all WARC records
        For HAR: iterates through all HAR entries

        Yields:
            WarcRecord or HarEntry: Each record in the artifact
        """
        if self._artifact_type == 'har':
            return self.parser.iter_entries()
        else:
            return self.parser.iter_records()

    def iter_responses(self) -> Iterator[Union[WarcRecord, HarEntry]]:
        """
        Iterate through HTTP response records only

        This is more memory-efficient than get_pages() for large crawls.

        For WARC: iterates through response records
        For HAR: iterates through all entries (HAR only contains responses)

        Yields:
            WarcRecord or HarEntry: HTTP response records with url, status_code, headers, content
        """
        if self._artifact_type == 'har':
            return self.parser.iter_entries()
        else:
            return self.parser.iter_responses()

    def get_pages(self) -> List[Dict]:
        """
        Get all crawled pages as simple dictionaries

        This is the easiest way to access crawl results.
        Works with both WARC and HAR formats.

        Returns:
            List of dicts with keys: url, status_code, headers, content

        Example:
            ```python
            pages = artifact.get_pages()
            for page in pages:
                print(f"{page['url']}: {len(page['content'])} bytes")
                html = page['content'].decode('utf-8')
            ```
        """
        if self._artifact_type == 'har':
            # Convert HAR entries to page dicts
            pages = []
            for entry in self.parser.iter_entries():
                pages.append({
                    'url': entry.url,
                    'status_code': entry.status_code,
                    'headers': entry.response_headers,
                    'content': entry.content
                })
            return pages
        else:
            return self.parser.get_pages()

    @property
    def total_pages(self) -> int:
        """Get total number of pages in the artifact"""
        return len(self.get_pages())

    def save(self, filepath: str):
        """
        Save WARC data to file

        Args:
            filepath: Path to save the WARC file

        Example:
            ```python
            artifact.save('crawl_results.warc.gz')
            ```
        """
        with open(filepath, 'wb') as f:
            f.write(self.warc_data)

    def __repr__(self):
        return f"CrawlerArtifactResponse(size={len(self.warc_data)} bytes)"
