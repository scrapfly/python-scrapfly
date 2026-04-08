"""
Crawler API Response Classes

This module provides response wrapper classes for the Crawler API.
"""

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

    Field names match the wire format emitted by the scrape-engine
    (``apps/scrapfly/scrape-engine/scrape_engine/crawler/config.py``), which
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

    **Field names match the wire format.** The scrape-engine is the source of
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

    Pagination: the wire protocol carries no global ``total``. ``page`` and
    ``per_page`` are echoes of the caller's request parameters — request
    further pages by incrementing ``page`` until the response has no records.

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
