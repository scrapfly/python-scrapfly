"""
Crawler API Configuration

This module provides the CrawlerConfig class for configuring crawler jobs.
"""

from typing import Optional, List, Dict, Literal
from ..api_config import BaseApiConfig


class CrawlerConfig(BaseApiConfig):
    """
    Configuration for Scrapfly Crawler API

    The Crawler API performs recursive website crawling with advanced
    configuration, content extraction, and artifact storage.

    Example:
        ```python
        from scrapfly import ScrapflyClient, CrawlerConfig
        client = ScrapflyClient(key='YOUR_API_KEY')
        config = CrawlerConfig(
            url='https://example.com',
            page_limit=100,
            max_depth=3,
            content_formats=['markdown', 'html']
        )

        # Start crawl
        start_response = client.start_crawl(config)
        uuid = start_response.uuid

        # Poll status
        status = client.get_crawl_status(uuid)

        # Get results when complete
        if status.is_complete:
            artifact = client.get_crawl_artifact(uuid)
            pages = artifact.get_pages()
        ```
    """

    WEBHOOK_CRAWLER_STARTED = 'crawler_started'
    WEBHOOK_CRAWLER_URL_VISITED = 'crawler_url_visited'
    WEBHOOK_CRAWLER_URL_SKIPPED = 'crawler_url_skipped'
    WEBHOOK_CRAWLER_URL_DISCOVERED = 'crawler_url_discovered'
    WEBHOOK_CRAWLER_URL_FAILED = 'crawler_url_failed'
    WEBHOOK_CRAWLER_STOPPED = 'crawler_stopped'
    WEBHOOK_CRAWLER_CANCELLED = 'crawler_cancelled'
    WEBHOOK_CRAWLER_FINISHED = 'crawler_finished'

    ALL_WEBHOOK_EVENTS = [
        WEBHOOK_CRAWLER_STARTED,
        WEBHOOK_CRAWLER_URL_VISITED,
        WEBHOOK_CRAWLER_URL_SKIPPED,
        WEBHOOK_CRAWLER_URL_DISCOVERED,
        WEBHOOK_CRAWLER_URL_FAILED,
        WEBHOOK_CRAWLER_STOPPED,
        WEBHOOK_CRAWLER_CANCELLED,
        WEBHOOK_CRAWLER_FINISHED,
    ]

    def __init__(
        self,
        url: str,
        # Crawl limits
        page_limit: Optional[int] = None,
        max_depth: Optional[int] = None,
        max_duration: Optional[int] = None,

        # Path filtering (mutually exclusive)
        exclude_paths: Optional[List[str]] = None,
        include_only_paths: Optional[List[str]] = None,

        # Advanced crawl options
        ignore_base_path_restriction: bool = False,
        follow_external_links: bool = False,
        allowed_external_domains: Optional[List[str]] = None,

        # Request configuration
        headers: Optional[Dict[str, str]] = None,
        delay: Optional[int] = None,
        user_agent: Optional[str] = None,
        max_concurrency: Optional[int] = None,
        rendering_delay: Optional[int] = None,

        # Crawl strategy options
        use_sitemaps: bool = False,
        respect_robots_txt: bool = False,
        ignore_no_follow: bool = False,

        # Cache options
        cache: bool = False,
        cache_ttl: Optional[int] = None,
        cache_clear: bool = False,

        # Content extraction
        content_formats: Optional[List[Literal['html', 'markdown', 'text', 'clean_html']]] = None,
        extraction_rules: Optional[Dict] = None,

        # Web scraping features
        asp: bool = False,
        proxy_pool: Optional[str] = None,
        country: Optional[str] = None,

        # Webhook integration
        webhook_name: Optional[str] = None,
        webhook_events: Optional[List[str]] = None,

        # Cost control
        max_api_credit: Optional[int] = None
    ):
        """
        Initialize a CrawlerConfig

        Args:
            url: Starting URL for the crawl (required)
            page_limit: Maximum number of pages to crawl
            max_depth: Maximum crawl depth from starting URL
            max_duration: Maximum crawl duration in seconds

            exclude_paths: List of path patterns to exclude (mutually exclusive with include_only_paths)
            include_only_paths: List of path patterns to include only (mutually exclusive with exclude_paths)

            ignore_base_path_restriction: Allow crawling outside the base path
            follow_external_links: Follow links to external domains
            allowed_external_domains: List of external domains allowed when follow_external_links is True

            headers: Custom HTTP headers for requests
            delay: Delay between requests in milliseconds
            user_agent: Custom user agent string
            max_concurrency: Maximum concurrent requests
            rendering_delay: Delay for JavaScript rendering in milliseconds

            use_sitemaps: Use sitemap.xml to discover URLs
            respect_robots_txt: Respect robots.txt rules
            ignore_no_follow: Ignore rel="nofollow" attributes

            cache: Enable caching
            cache_ttl: Cache time-to-live in seconds
            cache_clear: Clear cache before crawling

            content_formats: List of content formats to extract ('html', 'markdown', 'text', 'clean_html')
            extraction_rules: Custom extraction rules

            asp: Enable Anti-Scraping Protection bypass
            proxy_pool: Proxy pool to use (e.g., 'public_residential_pool')
            country: Target country for geo-located content

            webhook_name: Webhook name for event notifications
            webhook_events: List of webhook events to trigger

            max_api_credit: Maximum API credits to spend on this crawl
        """
        if exclude_paths and include_only_paths:
            raise ValueError("exclude_paths and include_only_paths are mutually exclusive")

        params = {
            'url': url,
        }

        # Add optional parameters
        if page_limit is not None:
            params['page_limit'] = page_limit
        if max_depth is not None:
            params['max_depth'] = max_depth
        if max_duration is not None:
            params['max_duration'] = max_duration

        # Path filtering
        if exclude_paths:
            params['exclude_paths'] = exclude_paths
        if include_only_paths:
            params['include_only_paths'] = include_only_paths

        # Advanced options
        if ignore_base_path_restriction:
            params['ignore_base_path_restriction'] = True
        if follow_external_links:
            params['follow_external_links'] = True
        if allowed_external_domains:
            params['allowed_external_domains'] = allowed_external_domains

        # Request configuration
        if headers:
            params['headers'] = headers
        if delay is not None:
            params['delay'] = delay
        if user_agent:
            params['user_agent'] = user_agent
        if max_concurrency is not None:
            params['max_concurrency'] = max_concurrency
        if rendering_delay is not None:
            params['rendering_delay'] = rendering_delay

        # Crawl strategy
        if use_sitemaps:
            params['use_sitemaps'] = True
        if respect_robots_txt:
            params['respect_robots_txt'] = True
        if ignore_no_follow:
            params['ignore_no_follow'] = True

        # Cache
        if cache:
            params['cache'] = True
        if cache_ttl is not None:
            params['cache_ttl'] = cache_ttl
        if cache_clear:
            params['cache_clear'] = True

        # Content extraction
        if content_formats:
            params['content_formats'] = content_formats
        if extraction_rules:
            params['extraction_rules'] = extraction_rules

        # Web scraping features
        if asp:
            params['asp'] = True
        if proxy_pool:
            params['proxy_pool'] = proxy_pool
        if country:
            params['country'] = country

        # Webhooks
        if webhook_name:
            params['webhook_name'] = webhook_name

        if webhook_events:
            assert all(
                event in self.ALL_WEBHOOK_EVENTS for event in webhook_events
            ), f"Invalid webhook events. Valid events are: {self.ALL_WEBHOOK_EVENTS}"
            
            params['webhook_events'] = webhook_events

        # Cost control
        if max_api_credit is not None:
            params['max_api_credit'] = max_api_credit

        self._params = params

    def to_api_params(self, key: Optional[str] = None) -> Dict:
        """
        Convert config to API parameters

        :param key: API key (optional, can be added by client)
        :return: Dictionary of API parameters
        """
        params = self._params.copy()
        if key:
            params['key'] = key
        return params
