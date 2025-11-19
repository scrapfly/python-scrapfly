"""
CrawlContent - Response object for crawled URLs

Provides a unified interface for accessing crawled content with metadata.
"""

from typing import Optional, Dict, Any


class CrawlContent:
    """
    Response object for a single crawled URL

    Provides access to content and metadata for a crawled page.
    Similar to ScrapeApiResponse but for crawler results.

    Attributes:
        url: The crawled URL (mandatory)
        content: Page content in requested format (mandatory)
        status_code: HTTP response status code (mandatory)
        headers: HTTP response headers (optional)
        duration: Request duration in seconds (optional)
        log_id: Scrape log ID for debugging (optional)
        log_url: URL to view scrape logs (optional)
        country: Country the request was made from (optional)

    Example:
        ```python
        # Get content for a URL
        content = crawl.read('https://example.com', format='markdown')

        print(f"URL: {content.url}")
        print(f"Status: {content.status_code}")
        print(f"Duration: {content.duration}s")
        print(f"Content: {content.content}")

        # Access metadata
        if content.log_url:
            print(f"View logs: {content.log_url}")
        ```
    """

    def __init__(
        self,
        url: str,
        content: str,
        status_code: int,
        headers: Optional[Dict[str, str]] = None,
        duration: Optional[float] = None,
        log_id: Optional[str] = None,
        country: Optional[str] = None,
        crawl_uuid: Optional[str] = None
    ):
        """
        Initialize CrawlContent

        Args:
            url: The crawled URL
            content: Page content in requested format
            status_code: HTTP response status code
            headers: HTTP response headers
            duration: Request duration in seconds
            log_id: Scrape log ID
            country: Country the request was made from
            crawl_uuid: Crawl job UUID
        """
        self.url = url
        self.content = content
        self.status_code = status_code
        self.headers = headers or {}
        self.duration = duration
        self.log_id = log_id
        self.country = country
        self._crawl_uuid = crawl_uuid

    @property
    def log_url(self) -> Optional[str]:
        """
        Get URL to view scrape logs

        Returns:
            Log URL if log_id is available, None otherwise
        """
        if self.log_id:
            return f"https://scrapfly.io/dashboard/logs/{self.log_id}"
        return None

    @property
    def success(self) -> bool:
        """Check if the request was successful (2xx status code)"""
        return 200 <= self.status_code < 300

    @property
    def error(self) -> bool:
        """Check if the request resulted in an error (4xx/5xx status code)"""
        return self.status_code >= 400

    def __repr__(self) -> str:
        return (f"CrawlContent(url={self.url!r}, status={self.status_code}, "
                f"content_length={len(self.content)})")

    def __str__(self) -> str:
        return self.content

    def __len__(self) -> int:
        """Get content length"""
        return len(self.content)
