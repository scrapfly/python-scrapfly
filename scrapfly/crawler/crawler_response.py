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
        # API returns 'crawler_uuid' not 'uuid'
        self.uuid = response_data.get('crawler_uuid') or response_data.get('uuid')
        self.status = response_data.get('status')

    def __repr__(self):
        return f"CrawlerStartResponse(uuid={self.uuid}, status={self.status})"


class CrawlerStatusResponse:
    """
    Response from checking crawler job status

    Returned by ScrapflyClient.get_crawl_status() method.

    Provides real-time progress tracking for crawler jobs.

    Attributes:
        uuid: Crawler job UUID
        status: Current status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED, DONE)
        is_success: Whether the crawler job completed successfully
        is_finished: Whether the crawler job has finished (regardless of success/failure)
        api_credit_cost: Total API credits consumed by this crawl
        stop_reason: Reason why the crawler stopped (e.g., 'seed_url_failed', 'page_limit_reached'), None if still running
        urls_discovered: Total URLs discovered so far
        urls_crawled: Number of URLs successfully crawled
        urls_pending: Number of URLs waiting to be crawled
        urls_failed: Number of URLs that failed to crawl
    """

    # Status constants
    STATUS_PENDING = 'PENDING'
    STATUS_RUNNING = 'RUNNING'
    STATUS_COMPLETED = 'COMPLETED'
    STATUS_DONE = 'DONE'
    STATUS_FAILED = 'FAILED'
    STATUS_CANCELLED = 'CANCELLED'

    def __init__(self, response_data: Dict[str, Any]):
        """
        Initialize from API response

        Args:
            response_data: Raw API response dictionary
        """
        self._data = response_data
        # API returns crawler_uuid in status response
        self.uuid = response_data.get('crawler_uuid') or response_data.get('uuid')
        self.status = response_data.get('status')

        # New fields from API
        self.is_success = response_data.get('is_success', False)
        self.is_finished = response_data.get('is_finished', False)

        # Parse state dict if present (actual API format)
        state = response_data.get('state', {})
        if state:
            # Actual API response structure
            self.urls_discovered = state.get('urls_extracted', 0)
            self.urls_crawled = state.get('urls_visited', 0)
            self.urls_pending = state.get('urls_to_crawl', 0)
            self.urls_failed = state.get('urls_failed', 0)
            self.stop_reason = state.get('stop_reason')
            # API credit cost is in the state dict as 'api_credit_used'
            self.api_credit_cost = state.get('api_credit_used', 0)
        else:
            # Fallback for simpler format (if docs change)
            self.urls_discovered = response_data.get('urls_discovered', 0)
            self.urls_crawled = response_data.get('urls_crawled', 0)
            self.urls_pending = response_data.get('urls_pending', 0)
            self.urls_failed = response_data.get('urls_failed', 0)
            self.stop_reason = None
            self.api_credit_cost = response_data.get('api_credit_cost', 0)

    @property
    def is_complete(self) -> bool:
        """Check if crawler job is complete"""
        return self.status in (self.STATUS_COMPLETED, self.STATUS_DONE)

    @property
    def is_running(self) -> bool:
        """Check if crawler job is currently running"""
        return self.status in (self.STATUS_PENDING, self.STATUS_RUNNING)

    @property
    def is_failed(self) -> bool:
        """Check if crawler job failed"""
        return self.status == self.STATUS_FAILED

    @property
    def is_cancelled(self) -> bool:
        """Check if crawler job was cancelled"""
        return self.status == self.STATUS_CANCELLED

    @property
    def progress_pct(self) -> float:
        """
        Calculate progress percentage

        Returns:
            Progress as percentage (0-100)
        """
        if self.urls_discovered == 0:
            return 0.0
        return (self.urls_crawled / self.urls_discovered) * 100

    def __repr__(self):
        return (f"CrawlerStatusResponse(uuid={self.uuid}, status={self.status}, "
                f"progress={self.progress_pct:.1f}%, "
                f"crawled={self.urls_crawled}/{self.urls_discovered})")


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
