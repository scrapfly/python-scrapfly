"""
Crawl Object - High-level abstraction for Crawler API

This module provides a Crawl object that manages the state and lifecycle
of a crawler job, making it easy to start, monitor, and retrieve results.
"""

from typing import Optional, Dict, Any, List, Literal, Iterator, Tuple
import time
import fnmatch
import logging
from email import message_from_string
from email.parser import BytesParser
from email.policy import default
from .crawler_config import CrawlerConfig
from .crawler_response import CrawlerStatusResponse, CrawlerArtifactResponse
from .crawl_content import CrawlContent
from ..errors import ScrapflyCrawlerError

logger = logging.getLogger(__name__)

# Valid content formats
ContentFormat = Literal[
    'html',
    'clean_html',
    'markdown',
    'json',
    'text',
    'extracted_data',
    'page_metadata'
]


class Crawl:
    """
    High-level abstraction for managing a crawler job

    The Crawl object maintains the state of a crawler job and provides
    convenient methods for managing its lifecycle.

    Example:
        ```python
        from scrapfly import ScrapflyClient, CrawlerConfig, Crawl

        client = ScrapflyClient(key='your-key')
        config = CrawlerConfig(url='https://example.com', page_limit=10)

        # Create and start crawl
        crawl = Crawl(client, config)
        crawl.crawl()  # Start the crawler

        # Wait for completion
        crawl.wait()

        # Get results
        pages = crawl.warc().get_pages()
        for page in pages:
            print(f"{page['url']}: {page['status_code']}")

        # Or read specific URLs
        html = crawl.read('https://example.com/page1', format='html')
        ```
    """

    def __init__(self, client: 'ScrapflyClient', config: CrawlerConfig):
        """
        Initialize a Crawl object

        Args:
            client: ScrapflyClient instance
            config: CrawlerConfig with crawler settings
        """
        self._client = client
        self._config = config
        self._uuid: Optional[str] = None
        self._status_cache: Optional[CrawlerStatusResponse] = None
        self._artifact_cache: Optional[CrawlerArtifactResponse] = None

    @property
    def uuid(self) -> Optional[str]:
        """Get the crawler job UUID (None if not started)"""
        return self._uuid

    @property
    def started(self) -> bool:
        """Check if the crawler has been started"""
        return self._uuid is not None

    def crawl(self) -> 'Crawl':
        """
        Start the crawler job

        Returns:
            Self for method chaining

        Raises:
            RuntimeError: If crawler already started

        Example:
            ```python
            crawl = Crawl(client, config)
            crawl.crawl()  # Start crawling
            ```
        """
        if self._uuid is not None:
            raise ScrapflyCrawlerError(
                message="Crawler already started",
                code="ALREADY_STARTED",
                http_status_code=400
            )

        response = self._client.start_crawl(self._config)
        self._uuid = response.uuid
        return self

    def status(self, refresh: bool = True) -> CrawlerStatusResponse:
        """
        Get current crawler status

        Args:
            refresh: If True, fetch fresh status from API. If False, return cached status.

        Returns:
            CrawlerStatusResponse with current status

        Raises:
            RuntimeError: If crawler not started yet

        Example:
            ```python
            status = crawl.status()
            print(f"Progress: {status.progress_pct}%")
            print(f"URLs crawled: {status.urls_crawled}")
            ```
        """
        if self._uuid is None:
            raise ScrapflyCrawlerError(
                message="Crawler not started yet. Call crawl() first.",
                code="NOT_STARTED",
                http_status_code=400
            )

        if refresh or self._status_cache is None:
            self._status_cache = self._client.get_crawl_status(self._uuid)

        return self._status_cache

    def wait(
        self,
        poll_interval: int = 5,
        max_wait: Optional[int] = None,
        verbose: bool = False
    ) -> 'Crawl':
        """
        Wait for crawler to complete

        Polls the status endpoint until the crawler finishes.

        Args:
            poll_interval: Seconds between status checks (default: 5)
            max_wait: Maximum seconds to wait (None = wait forever)
            verbose: If True, print progress updates

        Returns:
            Self for method chaining

        Raises:
            RuntimeError: If crawler not started, failed, or timed out

        Example:
            ```python
            # Wait with progress updates
            crawl.crawl().wait(verbose=True)

            # Wait with timeout
            crawl.crawl().wait(max_wait=300)  # 5 minutes max
            ```
        """
        if self._uuid is None:
            raise ScrapflyCrawlerError(
                message="Crawler not started yet. Call crawl() first.",
                code="NOT_STARTED",
                http_status_code=400
            )

        start_time = time.time()
        poll_count = 0

        while True:
            status = self.status(refresh=True)
            poll_count += 1

            if verbose:
                logger.info(f"Poll #{poll_count}: {status.status} - "
                           f"{status.progress_pct:.1f}% - "
                           f"{status.urls_crawled}/{status.urls_discovered} URLs")

            if status.is_complete:
                if verbose:
                    logger.info(f"✓ Crawler completed successfully!")
                return self
            elif status.is_failed:
                raise ScrapflyCrawlerError(
                    message=f"Crawler failed with status: {status.status}",
                    code="FAILED",
                    http_status_code=400
                )
            elif status.is_cancelled:
                raise ScrapflyCrawlerError(
                    message="Crawler was cancelled",
                    code="CANCELLED",
                    http_status_code=400
                )

            # Check timeout
            if max_wait is not None:
                elapsed = time.time() - start_time
                if elapsed > max_wait:
                    raise ScrapflyCrawlerError(
                        message=f"Timeout waiting for crawler (>{max_wait}s)",
                        code="TIMEOUT",
                        http_status_code=400
                    )

            time.sleep(poll_interval)

    def cancel(self) -> bool:
        """
        Cancel the running crawler job

        Returns:
            True if cancelled successfully

        Raises:
            ScrapflyCrawlerError: If crawler not started yet

        Example:
            ```python
            # Start a crawl
            crawl = Crawl(client, config).crawl()

            # Cancel it
            crawl.cancel()
            ```
        """
        if self._uuid is None:
            raise ScrapflyCrawlerError(
                message="Crawler not started yet. Call crawl() first.",
                code="NOT_STARTED",
                http_status_code=400
            )

        return self._client.cancel_crawl(self._uuid)

    def warc(self, artifact_type: str = 'warc') -> CrawlerArtifactResponse:
        """
        Download the crawler artifact (WARC file)

        Args:
            artifact_type: Type of artifact to download (default: 'warc')

        Returns:
            CrawlerArtifactResponse with parsed WARC data

        Raises:
            RuntimeError: If crawler not started yet

        Example:
            ```python
            # Get WARC artifact
            artifact = crawl.warc()

            # Get all pages
            pages = artifact.get_pages()

            # Iterate through responses
            for record in artifact.iter_responses():
                print(record.url)
            ```
        """
        if self._uuid is None:
            raise ScrapflyCrawlerError(
                message="Crawler not started yet. Call crawl() first.",
                code="NOT_STARTED",
                http_status_code=400
            )

        if self._artifact_cache is None:
            self._artifact_cache = self._client.get_crawl_artifact(
                self._uuid,
                artifact_type=artifact_type
            )

        return self._artifact_cache

    def har(self) -> CrawlerArtifactResponse:
        """
        Download the crawler artifact in HAR (HTTP Archive) format

        Returns:
            CrawlerArtifactResponse with parsed HAR data

        Raises:
            RuntimeError: If crawler not started yet

        Example:
            ```python
            # Get HAR artifact
            artifact = crawl.har()

            # Get all pages
            pages = artifact.get_pages()

            # Iterate through HAR entries
            for entry in artifact.iter_responses():
                print(f"{entry.url}: {entry.status_code}")
                print(f"Timing: {entry.time}ms")
            ```
        """
        if self._uuid is None:
            raise ScrapflyCrawlerError(
                message="Crawler not started yet. Call crawl() first.",
                code="NOT_STARTED",
                http_status_code=400
            )

        return self._client.get_crawl_artifact(
            self._uuid,
            artifact_type='har'
        )

    def read(self, url: str, format: ContentFormat = 'html') -> Optional[CrawlContent]:
        """
        Read content from a specific URL in the crawl results

        Args:
            url: The URL to retrieve content for
            format: Content format - 'html', 'markdown', 'text', 'clean_html', 'json',
                   'extracted_data', 'page_metadata'

        Returns:
            CrawlContent object with content and metadata, or None if URL not found

        Example:
            ```python
            # Get HTML content for a specific URL
            content = crawl.read('https://example.com/page1')
            if content:
                print(f"URL: {content.url}")
                print(f"Status: {content.status_code}")
                print(f"Duration: {content.duration}s")
                print(content.content)

            # Get markdown content
            content = crawl.read('https://example.com/page1', format='markdown')
            if content:
                print(content.content)

            # Check if URL was crawled
            if crawl.read('https://example.com/missing') is None:
                print("URL not found in crawl results")
            ```
        """
        if self._uuid is None:
            raise ScrapflyCrawlerError(
                message="Crawler not started yet. Call crawl() first.",
                code="NOT_STARTED",
                http_status_code=400
            )

        # For HTML format, we can get it from the WARC artifact (faster)
        if format == 'html':
            artifact = self.warc()
            for record in artifact.iter_responses():
                if record.url == url:
                    # Extract metadata from WARC headers
                    warc_headers = record.warc_headers or {}
                    duration_str = warc_headers.get('WARC-Scrape-Duration')
                    duration = float(duration_str) if duration_str else None

                    return CrawlContent(
                        url=record.url,
                        content=record.content.decode('utf-8', errors='replace'),
                        status_code=record.status_code,
                        headers=record.headers,
                        duration=duration,
                        log_id=warc_headers.get('WARC-Scrape-Log-Id'),
                        country=warc_headers.get('WARC-Scrape-Country'),
                        crawl_uuid=self._uuid
                    )
            return None

        # For other formats (markdown, text, etc.), use the contents API
        try:
            result = self._client.get_crawl_contents(
                self._uuid,
                format=format
            )

            # The API returns: {"contents": {url: {format: content, ...}, ...}, "links": {...}}
            contents = result.get('contents', {})

            if url in contents:
                content_data = contents[url]
                # Content is always a dict with format keys (e.g., {"html": "...", "markdown": "..."})
                content_str = content_data.get(format)

                if content_str:
                    # For non-HTML formats from contents API, we don't have full metadata
                    # Try to get status code from WARC if possible
                    status_code = 200  # Default
                    headers = {}
                    duration = None
                    log_id = None
                    country = None

                    # Try to get metadata from WARC
                    try:
                        artifact = self.warc()
                        for record in artifact.iter_responses():
                            if record.url == url:
                                status_code = record.status_code
                                headers = record.headers
                                warc_headers = record.warc_headers or {}
                                duration_str = warc_headers.get('WARC-Scrape-Duration')
                                duration = float(duration_str) if duration_str else None
                                log_id = warc_headers.get('WARC-Scrape-Log-Id')
                                country = warc_headers.get('WARC-Scrape-Country')
                                break
                    except:
                        pass

                    return CrawlContent(
                        url=url,
                        content=content_str,
                        status_code=status_code,
                        headers=headers,
                        duration=duration,
                        log_id=log_id,
                        country=country,
                        crawl_uuid=self._uuid
                    )

            return None

        except Exception:
            # If contents API fails, return None
            return None

    def read_iter(
        self,
        pattern: str,
        format: ContentFormat = 'html'
    ) -> Iterator[CrawlContent]:
        """
        Iterate through URLs matching a pattern and yield their content

        Supports wildcard patterns using * and ? for flexible URL matching.

        Args:
            pattern: URL pattern with wildcards (* matches any characters, ? matches one)
                    Examples: "/products?page=*", "https://example.com/*/detail", "*/product/*"
            format: Content format to retrieve

        Yields:
            CrawlContent objects for each matching URL

        Example:
            ```python
            # Get all product pages in markdown
            for content in crawl.read_iter(pattern="*/products?page=*", format="markdown"):
                print(f"{content.url}: {len(content.content)} chars")
                print(f"Duration: {content.duration}s")

            # Get all detail pages
            for content in crawl.read_iter(pattern="*/detail/*"):
                process(content.content)

            # Pattern matching examples:
            # "/products?page=*" matches /products?page=1, /products?page=2, etc.
            # "*/product/*" matches any URL with /product/ in the path
            # "https://example.com/page?" matches https://example.com/page1, page2, etc.
            ```
        """
        if self._uuid is None:
            raise ScrapflyCrawlerError(
                message="Crawler not started yet. Call crawl() first.",
                code="NOT_STARTED",
                http_status_code=400
            )

        # For HTML format, use WARC artifact (faster)
        if format == 'html':
            artifact = self.warc()
            for record in artifact.iter_responses():
                if fnmatch.fnmatch(record.url, pattern):
                    # Extract metadata from WARC headers
                    warc_headers = record.warc_headers or {}
                    duration_str = warc_headers.get('WARC-Scrape-Duration')
                    duration = float(duration_str) if duration_str else None

                    yield CrawlContent(
                        url=record.url,
                        content=record.content.decode('utf-8', errors='replace'),
                        status_code=record.status_code,
                        headers=record.headers,
                        duration=duration,
                        log_id=warc_headers.get('WARC-Scrape-Log-Id'),
                        country=warc_headers.get('WARC-Scrape-Country'),
                        crawl_uuid=self._uuid
                    )
        else:
            # For other formats, use contents API
            try:
                result = self._client.get_crawl_contents(
                    self._uuid,
                    format=format
                )

                contents = result.get('contents', {})

                # Build a metadata cache from WARC for non-HTML formats
                metadata_cache = {}
                try:
                    artifact = self.warc()
                    for record in artifact.iter_responses():
                        warc_headers = record.warc_headers or {}
                        duration_str = warc_headers.get('WARC-Scrape-Duration')
                        metadata_cache[record.url] = {
                            'status_code': record.status_code,
                            'headers': record.headers,
                            'duration': float(duration_str) if duration_str else None,
                            'log_id': warc_headers.get('WARC-Scrape-Log-Id'),
                            'country': warc_headers.get('WARC-Scrape-Country')
                        }
                except:
                    pass

                # Iterate through matching URLs
                for url, content_data in contents.items():
                    if fnmatch.fnmatch(url, pattern):
                        # Content is always a dict with format keys (e.g., {"html": "...", "markdown": "..."})
                        content = content_data.get(format)

                        if content:
                            # Get metadata from cache or use defaults
                            metadata = metadata_cache.get(url, {})
                            yield CrawlContent(
                                url=url,
                                content=content,
                                status_code=metadata.get('status_code', 200),
                                headers=metadata.get('headers', {}),
                                duration=metadata.get('duration'),
                                log_id=metadata.get('log_id'),
                                country=metadata.get('country'),
                                crawl_uuid=self._uuid
                            )

            except Exception:
                # If contents API fails, yield nothing
                return

    def read_batch(
        self,
        urls: List[str],
        formats: List[ContentFormat] = None
    ) -> Dict[str, Dict[str, str]]:
        """
        Retrieve content for multiple URLs in a single batch request

        This is more efficient than calling read() multiple times as it retrieves
        all content in a single API call. Maximum 100 URLs per request.

        Args:
            urls: List of URLs to retrieve (max 100)
            formats: List of content formats to retrieve (e.g., ['markdown', 'text'])
                    If None, defaults to ['html']

        Returns:
            Dictionary mapping URLs to their content in requested formats:
            {
                'https://example.com/page1': {
                    'markdown': '# Page 1...',
                    'text': 'Page 1...'
                },
                'https://example.com/page2': {
                    'markdown': '# Page 2...',
                    'text': 'Page 2...'
                }
            }

        Example:
            ```python
            # Get markdown and text for multiple URLs
            urls = ['https://example.com/page1', 'https://example.com/page2']
            contents = crawl.read_batch(urls, formats=['markdown', 'text'])

            for url, formats in contents.items():
                markdown = formats.get('markdown', '')
                text = formats.get('text', '')
                print(f"{url}: {len(markdown)} chars markdown, {len(text)} chars text")
            ```

        Raises:
            ValueError: If more than 100 URLs are provided
            ScrapflyCrawlerError: If crawler not started or request fails
        """
        if self._uuid is None:
            raise ScrapflyCrawlerError(
                message="Crawler not started yet. Call crawl() first.",
                code="NOT_STARTED",
                http_status_code=400
            )

        if len(urls) > 100:
            raise ValueError("Maximum 100 URLs per batch request")

        if not urls:
            return {}

        # Default to html if no formats specified
        if formats is None:
            formats = ['html']

        # Build URL with formats parameter
        formats_str = ','.join(formats)
        url = f"{self._client.host}/crawl/{self._uuid}/contents/batch"
        params = {
            'key': self._client.key,
            'formats': formats_str
        }

        # Prepare request body (newline-separated URLs)
        body = '\n'.join(urls)

        # Make request
        import requests
        response = requests.post(
            url,
            params=params,
            data=body.encode('utf-8'),
            headers={'Content-Type': 'text/plain'},
            verify=self._client.verify
        )

        if response.status_code != 200:
            raise ScrapflyCrawlerError(
                message=f"Batch content request failed: {response.status_code}",
                code="BATCH_REQUEST_FAILED",
                http_status_code=response.status_code
            )

        # Parse multipart response
        content_type = response.headers.get('Content-Type', '')
        if not content_type.startswith('multipart/related'):
            raise ScrapflyCrawlerError(
                message=f"Unexpected content type: {content_type}",
                code="INVALID_RESPONSE",
                http_status_code=500
            )

        # Extract boundary from Content-Type header
        boundary = None
        for part in content_type.split(';'):
            part = part.strip()
            if part.startswith('boundary='):
                boundary = part.split('=', 1)[1]
                break

        if not boundary:
            raise ScrapflyCrawlerError(
                message="No boundary found in multipart response",
                code="INVALID_RESPONSE",
                http_status_code=500
            )

        # Parse multipart message
        # Prepend Content-Type header to make it a valid email message for the parser
        message_bytes = f"Content-Type: {content_type}\r\n\r\n".encode('utf-8') + response.content
        parser = BytesParser(policy=default)
        message = parser.parsebytes(message_bytes)

        # Extract content from each part
        result = {}

        for part in message.walk():
            # Skip the container itself
            if part.get_content_maintype() == 'multipart':
                continue

            # Get the URL from Content-Location header
            content_location = part.get('Content-Location')
            if not content_location:
                continue

            # Get content type to determine format
            part_content_type = part.get_content_type()
            format_type = None

            # Map MIME types to format names
            if 'markdown' in part_content_type:
                format_type = 'markdown'
            elif 'plain' in part_content_type:
                format_type = 'text'
            elif 'html' in part_content_type:
                format_type = 'html'
            elif 'json' in part_content_type:
                format_type = 'json'

            if not format_type:
                continue

            # Get content
            content = part.get_content()
            if isinstance(content, bytes):
                content = content.decode('utf-8', errors='replace')

            # Initialize URL dict if needed
            if content_location not in result:
                result[content_location] = {}

            # Store content
            result[content_location][format_type] = content

        return result

    def stats(self) -> Dict[str, Any]:
        """
        Get comprehensive statistics about the crawl

        Returns:
            Dictionary with crawl statistics

        Example:
            ```python
            stats = crawl.stats()
            print(f"URLs discovered: {stats['urls_discovered']}")
            print(f"URLs crawled: {stats['urls_crawled']}")
            print(f"Success rate: {stats['success_rate']:.1f}%")
            print(f"Total size: {stats['total_size_kb']:.2f} KB")
            ```
        """
        status = self.status(refresh=False)

        # Basic stats from status
        stats_dict = {
            'uuid': self._uuid,
            'status': status.status,
            'urls_discovered': status.urls_discovered,
            'urls_crawled': status.urls_crawled,
            'urls_pending': status.urls_pending,
            'urls_failed': status.urls_failed,
            'progress_pct': status.progress_pct,
            'is_complete': status.is_complete,
            'is_running': status.is_running,
            'is_failed': status.is_failed,
        }

        # Calculate basic crawl rate (crawled vs discovered)
        if status.urls_discovered > 0:
            stats_dict['crawl_rate'] = (status.urls_crawled / status.urls_discovered) * 100

        # Add artifact stats if available
        if self._artifact_cache is not None:
            pages = self._artifact_cache.get_pages()
            total_size = sum(len(p['content']) for p in pages)
            avg_size = total_size / len(pages) if pages else 0

            stats_dict.update({
                'pages_downloaded': len(pages),
                'total_size_bytes': total_size,
                'total_size_kb': total_size / 1024,
                'total_size_mb': total_size / (1024 * 1024),
                'avg_page_size_bytes': avg_size,
                'avg_page_size_kb': avg_size / 1024,
            })

            # Calculate download rate (pages vs discovered)
            if status.urls_discovered > 0:
                stats_dict['download_rate'] = (len(pages) / status.urls_discovered) * 100

        return stats_dict

    def __repr__(self):
        if self._uuid is None:
            return f"Crawl(not started)"

        status_str = "unknown"
        if self._status_cache:
            status_str = self._status_cache.status

        return f"Crawl(uuid={self._uuid}, status={status_str})"
