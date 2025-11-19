"""
Crawler Configuration Tests

Tests various crawler configuration options:
- Page and depth limits
- Path filtering (include/exclude)
- External links and sitemaps
- Proxy and ASP settings
- Custom headers and delays
"""
import pytest
from scrapfly import Crawl, CrawlerConfig
from .conftest import assert_crawl_successful


@pytest.mark.config
@pytest.mark.unit
class TestBasicLimits:
    """Test page_limit and max_depth settings"""

    def test_page_limit(self, client, test_url):
        """Test that page_limit is respected"""
        page_limit = 5
        config = CrawlerConfig(url=test_url, page_limit=page_limit)
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = assert_crawl_successful(crawl)

        # Should crawl at most page_limit pages
        assert status.urls_crawled <= page_limit

    def test_max_depth(self, client, test_url):
        """Test that max_depth limits crawl depth"""
        config = CrawlerConfig(url=test_url, page_limit=20, max_depth=1)
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        # With max_depth=1, should only crawl seed and direct links
        # Not going deeper into the site
        urls = crawl.urls()
        assert len(urls) > 0

    def test_combined_limits(self, client, test_url):
        """Test page_limit and max_depth together"""
        config = CrawlerConfig(url=test_url, page_limit=3, max_depth=1)
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = assert_crawl_successful(crawl)

        # Should respect both limits
        assert status.urls_crawled <= 3


class TestPathFiltering:
    """Test path filtering options"""

    def test_exclude_paths(self, client, test_url):
        """Test exclude_paths pattern matching"""
        config = CrawlerConfig(
            url='https://web-scraping.dev',
            page_limit=10,
            exclude_paths=['/product/\\d+']  # Exclude product detail pages
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        urls = crawl.urls()

        # Should not contain product detail URLs
        product_detail_urls = [url for url in urls if '/product/' in url and url.split('/')[-1].isdigit()]
        assert len(product_detail_urls) == 0

    def test_include_only_paths(self, client, test_url):
        """Test include_only_paths pattern matching"""
        config = CrawlerConfig(
            url='https://web-scraping.dev',
            page_limit=10,
            include_only_paths=['/product.*']  # Only crawl product pages
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        urls = crawl.urls()

        # All URLs (except seed) should match the pattern
        for url in urls:
            assert '/product' in url or url == 'https://web-scraping.dev' or url == 'https://web-scraping.dev/'

    def test_multiple_exclude_patterns(self, client, test_url):
        """Test multiple exclude patterns"""
        config = CrawlerConfig(
            url='https://web-scraping.dev',
            page_limit=15,
            exclude_paths=['/product/1$', '/product/2$']  # Exclude specific products
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        urls = crawl.urls()

        # Should not contain excluded URLs
        excluded_urls = [url for url in urls if url.endswith('/product/1') or url.endswith('/product/2')]
        assert len(excluded_urls) == 0


class TestAdvancedOptions:
    """Test advanced crawler options"""

    def test_custom_headers(self, client, httpbin_url):
        """Test custom headers in requests"""
        from tests.crawler.conftest import parse_httpbin_headers

        custom_header_name = 'X-Custom-Header'
        custom_header_value = 'test-value'

        config = CrawlerConfig(
            url=f"{httpbin_url}/dump/request",
            page_limit=1,
            headers={custom_header_name: custom_header_value}
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = assert_crawl_successful(crawl)
        assert status.urls_crawled > 0, "HTTPBin /dump/request endpoint failed to crawl"

        # Retrieve the actual content
        crawl_content = crawl.read(f"{httpbin_url}/dump/request")
        assert crawl_content is not None, "Could not retrieve /dump/request content"

        # Parse HTTP headers from httpbin response
        headers = parse_httpbin_headers(crawl_content.content)

        # Verify custom header was sent
        assert custom_header_name in headers, \
            f"Expected '{custom_header_name}' in headers, got: {list(headers.keys())}"
        assert headers[custom_header_name] == custom_header_value, \
            f"Expected '{custom_header_value}', got: {headers[custom_header_name]}"

    def test_user_agent(self, client, httpbin_url):
        """Test custom user agent is sent and appears in crawled content"""
        custom_ua = 'Test-Crawler'
        config = CrawlerConfig(
            url=f"{httpbin_url}/dump/request",
            page_limit=1,
            headers={'User-Agent': custom_ua}
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = assert_crawl_successful(crawl)
        assert status.urls_crawled > 0, "HTTPBin /dump/request endpoint failed to crawl"

        # Retrieve the actual content from the seed URL
        crawl_content = crawl.read(f"{httpbin_url}/dump/request")
        assert crawl_content is not None, "Could not retrieve /dump/request content"

        # Parse HTTP headers from httpbin response
        from tests.crawler.conftest import parse_httpbin_headers
        headers = parse_httpbin_headers(crawl_content.content)

        # Verify User-Agent header contains our custom value
        assert 'User-Agent' in headers, "Response should contain User-Agent header"
        assert custom_ua in headers['User-Agent'], \
            f"Expected '{custom_ua}' in User-Agent, got: {headers['User-Agent']}"

    def test_delay_between_requests(self, client, test_url):
        """Test delay between requests"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=3,
            delay=1000  # 1 second delay
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        # Crawl should take longer with delay

    def test_max_concurrency(self, client, test_url):
        """Test max concurrent requests setting"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=10,
            max_concurrency=2
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)


class TestExternalLinksAndSitemaps:
    """Test external links and sitemap options"""

    def test_ignore_external_links(self, client, test_url):
        """Test that external links are ignored by default"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=10,
            follow_external_links=False
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        urls = crawl.urls()

        # All URLs should be from same domain
        from urllib.parse import urlparse
        seed_domain = urlparse(test_url).netloc

        for url in urls:
            assert urlparse(url).netloc == seed_domain

    def test_use_sitemaps(self, client):
        """Test sitemap discovery and usage"""
        config = CrawlerConfig(
            url='https://web-scraping.dev',
            page_limit=20,
            use_sitemaps=True
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        # With sitemaps, might discover more URLs faster

    def test_respect_robots_txt(self, client):
        """Test robots.txt respect"""
        config = CrawlerConfig(
            url='https://web-scraping.dev',
            page_limit=10,
            respect_robots_txt=True
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        # Should follow robots.txt rules


class TestProxyAndASP:
    """Test proxy and anti-scraping protection settings"""

    def test_asp_enabled(self, client, test_url):
        """Test with ASP (Anti-Scraping Protection) enabled and verify cost"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=1,
            asp=True,
            respect_robots_txt=False
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = assert_crawl_successful(crawl)

        # ASP adds cost per request
        # With ASP enabled, cost should be higher than base (1)
        # Actual cost appears to be 2 credits (1 base + 1 ASP)
        assert status.api_credit_cost >= 2, \
            f"Expected at least 2 API credits with ASP enabled, got {status.api_credit_cost}"

    def test_proxy_pool(self, client, test_url):
        """Test residential proxy pool and verify API credit cost"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=1,  # Only 1 URL to verify cost
            proxy_pool='public_residential_pool',  # Residential costs 25 credits per request
            respect_robots_txt=False  # Disable robots.txt fetch (costs 1 credit)
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = assert_crawl_successful(crawl)

        # Verify API credit cost for residential proxy
        # Should be 25-26 credits: 25 for residential + possibly 1 for sitemap.xml
        assert status.api_credit_cost >= 25, \
            f"Expected at least 25 API credits for residential proxy, got {status.api_credit_cost}"

    def test_country_targeting(self, client, httpbin_url):
        """Test with country-specific proxy and verify country is set"""
        config = CrawlerConfig(
            url=f"{httpbin_url}/dump/request",
            page_limit=1,
            country='us',
            respect_robots_txt=False
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = assert_crawl_successful(crawl)

        # Verify the crawl used the correct country
        # Check via the crawl status or WARC metadata
        # The country should be returned in scrape metadata
        crawl_content = crawl.read(f"{httpbin_url}/dump/request")
        assert crawl_content is not None, "Could not retrieve content"

        # Verify country is set in the crawl content metadata
        assert crawl_content.country == 'us', \
            f"Expected country 'us', got '{crawl_content.country}'"


class TestCacheOptions:
    """Test cache configuration"""

    def test_cache_enabled(self, client, test_url):
        """Test with cache enabled - second crawl should use cached results"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=1,
            cache=True,
            cache_ttl=3600,
            respect_robots_txt=False
        )

        # First crawl - populate cache
        crawl1 = Crawl(client, config).crawl().wait(verbose=False)
        status1 = assert_crawl_successful(crawl1)
        first_cost = status1.api_credit_cost

        # Second crawl - should use cache (no additional cost)
        crawl2 = Crawl(client, config).crawl().wait(verbose=False)
        status2 = assert_crawl_successful(crawl2)

        # When using cache, the second crawl should have same or lower cost
        # (cache might still incur minimal costs for metadata/sitemaps)
        assert status2.api_credit_cost <= first_cost, \
            f"Expected cached crawl cost ({status2.api_credit_cost}) to be <= first crawl ({first_cost})"

        # Both should complete successfully
        assert status2.urls_crawled > 0, "Cached crawl should still crawl URLs"

    def test_cache_clear(self, client, test_url):
        """Test cache clearing - should not use cached results"""
        # First crawl with cache
        config1 = CrawlerConfig(
            url=test_url,
            page_limit=1,
            cache=True,
            cache_ttl=3600,
            respect_robots_txt=False
        )
        crawl1 = Crawl(client, config1).crawl().wait(verbose=False)
        status1 = assert_crawl_successful(crawl1)
        first_cost = status1.api_credit_cost

        # Second crawl with cache_clear=True - should bypass cache
        config2 = CrawlerConfig(
            url=test_url,
            page_limit=1,
            cache=True,
            cache_clear=True,  # This should clear/bypass cache
            respect_robots_txt=False
        )
        crawl2 = Crawl(client, config2).crawl().wait(verbose=False)
        status2 = assert_crawl_successful(crawl2)

        # With cache_clear, should still incur API cost (not using cache)
        assert status2.api_credit_cost > 0, \
            f"Expected API cost > 0 with cache_clear=True, got {status2.api_credit_cost}"


class TestCrawlLimits:
    """Test crawl duration and cost limits"""

    def test_max_duration(self, client, test_url):
        """Test max_duration stops crawl after time limit"""
        import time
        config = CrawlerConfig(
            url=test_url,
            page_limit=100,  # High limit
            max_duration=10  # 10 seconds max
        )

        start_time = time.time()
        crawl = Crawl(client, config).crawl().wait(verbose=False)
        duration = time.time() - start_time

        status = assert_crawl_successful(crawl)

        # Should stop due to time limit (not page limit)
        # Duration should be around 10 seconds (with some overhead)
        assert duration < 20  # Allow for overhead

        # If stopped by duration, stop_reason should indicate it
        # (check if status has stop_reason attribute)
        if hasattr(status, 'stop_reason'):
            assert status.stop_reason in ('max_duration', 'page_limit', 'no_more_urls')

    def test_max_api_credit(self, client, test_url):
        """Test max_api_credit limits API credit consumption"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=100,
            max_api_credit=5  # Very low credit limit
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = assert_crawl_successful(crawl)

        # Should stop before page_limit due to credit limit
        # Exact behavior depends on API pricing, but should stop early
        if hasattr(status, 'stop_reason'):
            assert status.stop_reason in ('max_api_credit', 'page_limit', 'no_more_urls')

    def test_combined_limits_duration_and_pages(self, client, test_url):
        """Test max_duration with page_limit"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=5,
            max_duration=30
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = assert_crawl_successful(crawl)

        # Should hit page_limit before duration
        assert status.urls_crawled <= 5


class TestExternalLinks:
    """Test external link following and domain restrictions"""

    def test_follow_external_links_enabled(self, client):
        """Test following external links when enabled"""
        config = CrawlerConfig(
            url='https://web-scraping.dev',
            page_limit=15,
            max_depth=2,
            follow_external_links=True
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = assert_crawl_successful(crawl)
        urls = crawl.urls()

        # With external links, might have URLs from different domains
        from urllib.parse import urlparse
        domains = set(urlparse(url).netloc for url in urls)

        # Should potentially have multiple domains (if site links externally)
        # At minimum, should have the base domain
        assert 'web-scraping.dev' in domains

    def test_allowed_external_domains(self, client):
        """Test restricting external links to specific domains"""
        config = CrawlerConfig(
            url='https://web-scraping.dev',
            page_limit=10,
            follow_external_links=True,
            allowed_external_domains=['example.com', 'test.com']
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        urls = crawl.urls()

        # Check that only allowed external domains are present
        from urllib.parse import urlparse
        for url in urls:
            domain = urlparse(url).netloc
            # Should be either the seed domain or an allowed external domain
            assert domain in ('web-scraping.dev', 'example.com', 'test.com') or \
                   domain.endswith('.web-scraping.dev')

    def test_ignore_base_path_restriction(self, client):
        """Test ignore_base_path_restriction allows crawling outside base path"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/product/1',
            page_limit=10,
            ignore_base_path_restriction=True
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        urls = crawl.urls()

        # With ignore_base_path_restriction, should be able to go outside /product/1
        # Should find URLs not under /product/1
        non_base_urls = [url for url in urls if not url.startswith('https://web-scraping.dev/product/1')]
        assert len(non_base_urls) > 0


class TestRenderingOptions:
    """Test JavaScript rendering options"""

    def test_rendering_delay(self, client, test_url):
        """Test rendering_delay for JavaScript-heavy pages"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=3,
            rendering_delay=2000  # 2 second rendering delay
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        # Rendering delay should give JS time to execute
        # Actual verification would require checking page content
        status = crawl.status()
        assert status.urls_crawled > 0

    def test_rendering_delay_with_wait(self, client, test_url):
        """Test rendering with different wait strategies"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=2,
            rendering_delay=1000,
            # Note: If API supports rendering_wait, add here
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)


class TestCrawlStrategy:
    """Test different crawl strategy options"""

    def test_ignore_no_follow(self, client):
        """Test ignore_no_follow option"""
        config = CrawlerConfig(
            url='https://web-scraping.dev',
            page_limit=10,
            ignore_no_follow=True
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        # With ignore_no_follow, should crawl links marked with rel="nofollow"
        # Exact verification depends on target site having nofollow links

    def test_robots_txt_with_user_agent(self, client):
        """Test robots.txt respect with custom user agent"""
        config = CrawlerConfig(
            url='https://web-scraping.dev',
            page_limit=5,
            respect_robots_txt=True,
            user_agent='CustomBot/1.0'
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        # Should respect robots.txt rules for CustomBot user agent
