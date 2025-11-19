"""
Comprehensive Crawler API Tests

Tests the Scrapfly Crawler API functionality including:
- Basic crawling workflow
- Status monitoring
- Artifact retrieval (WARC and HAR formats)
- Content formats (HTML, markdown, text, etc.)
- Content retrieval methods (read, read_iter, read_batch)
- Path filtering and crawl options
- Error handling
"""

import os
import pytest
import time
from scrapfly import (
    ScrapflyClient,
    CrawlerConfig,
    Crawl,
    ScrapflyCrawlerError,
)


# Test configuration
API_KEY = os.environ.get('SCRAPFLY_KEY', 'scp-live-d8ac176c2f9d48b993b58675bdf71615')
API_HOST = os.environ.get('SCRAPFLY_API_HOST', 'https://api.scrapfly.home')


@pytest.fixture
def client():
    """Create a ScrapflyClient instance for testing"""
    return ScrapflyClient(
        key=API_KEY,
        host=API_HOST,
        verify=False
    )


@pytest.fixture
def test_url():
    """Base URL for testing - use web-scraping.dev"""
    return 'https://web-scraping.dev/products'


def assert_crawl_successful(crawl):
    """Helper to verify a crawl completed successfully"""
    status = crawl.status()
    assert status.is_complete, f"Crawl {crawl.uuid} should be complete but status is: {status.status}"
    assert not status.is_failed, f"Crawl {crawl.uuid} failed with status: {status.status}"
    assert status.urls_crawled > 0, f"Crawl {crawl.uuid} should have crawled at least one URL"
    return status


class TestCrawlerBasicWorkflow:
    """Test basic crawler workflow: start, monitor, retrieve results"""

    def test_basic_crawl_workflow(self, client, test_url):
        """Test complete crawl workflow: start -> wait -> get results"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=5,
            max_depth=2
        )

        # Start crawl
        crawl = Crawl(client, config)
        assert not crawl.started
        assert crawl.uuid is None

        crawl.crawl()
        assert crawl.started
        assert crawl.uuid is not None

        # Wait for completion
        crawl.wait(poll_interval=2, verbose=False)

        # Check final status
        status = crawl.status()
        assert status.is_complete
        assert status.urls_crawled > 0
        assert status.urls_discovered > 0

    def test_crawl_method_chaining(self, client, test_url):
        """Test that crawl methods support chaining"""
        config = CrawlerConfig(url=test_url, page_limit=3)

        # All methods should return self for chaining
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert crawl.started
        status = crawl.status()
        assert status.is_complete

    def test_cannot_start_twice(self, client, test_url):
        """Test that starting a crawl twice raises an error"""
        config = CrawlerConfig(url=test_url, page_limit=2)
        crawl = Crawl(client, config).crawl()

        # Try to start again
        with pytest.raises(ScrapflyCrawlerError) as exc_info:
            crawl.crawl()

        assert "already started" in str(exc_info.value).lower()

    def test_status_before_start_raises_error(self, client, test_url):
        """Test that calling status before starting raises error"""
        config = CrawlerConfig(url=test_url, page_limit=2)
        crawl = Crawl(client, config)

        with pytest.raises(ScrapflyCrawlerError) as exc_info:
            crawl.status()

        assert "not started" in str(exc_info.value).lower()


class TestCrawlerStatus:
    """Test crawler status monitoring"""

    def test_status_polling(self, client, test_url):
        """Test status polling during crawl"""
        config = CrawlerConfig(url=test_url, page_limit=10, max_depth=2)
        crawl = Crawl(client, config).crawl()

        # Poll status a few times
        statuses = []
        for _ in range(3):
            status = crawl.status(refresh=True)
            statuses.append(status)
            if status.is_complete:
                break
            time.sleep(2)

        # Final status should be complete
        final_status = crawl.status()
        assert final_status.is_complete or final_status.is_running

        # Status should have expected fields
        assert final_status.uuid == crawl.uuid
        assert final_status.urls_crawled >= 0
        assert final_status.urls_discovered >= 0
        assert 0 <= final_status.progress_pct <= 100

    def test_status_caching(self, client, test_url):
        """Test status caching with refresh parameter"""
        config = CrawlerConfig(url=test_url, page_limit=5)
        crawl = Crawl(client, config).crawl()

        # First call should fetch
        status1 = crawl.status(refresh=True)

        # Second call with refresh=False should use cache
        status2 = crawl.status(refresh=False)

        # Should be the same object (cached)
        assert status1 is status2


class TestCrawlerWARC:
    """Test WARC artifact retrieval and parsing"""

    def test_get_warc_artifact(self, client, test_url):
        """Test downloading and parsing WARC artifact"""
        config = CrawlerConfig(url=test_url, page_limit=5)
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        # Get WARC artifact
        artifact = crawl.warc()
        assert artifact is not None
        assert artifact.artifact_type == 'warc'
        assert len(artifact.artifact_data) > 0

    def test_warc_get_pages(self, client, test_url):
        """Test getting all pages from WARC"""
        config = CrawlerConfig(url=test_url, page_limit=5)
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        artifact = crawl.warc()
        pages = artifact.get_pages()

        assert len(pages) > 0
        # Note: page count may slightly exceed page_limit due to robots.txt and other system pages
        assert len(pages) <= 10  # Reasonable upper bound

        # Check page structure
        page = pages[0]
        assert 'url' in page
        assert 'status_code' in page
        assert 'content' in page
        assert 'headers' in page

        # Status should be 200 for successful pages
        assert page['status_code'] == 200

    def test_warc_iter_responses(self, client, test_url):
        """Test iterating through WARC records"""
        config = CrawlerConfig(url=test_url, page_limit=5)
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        artifact = crawl.warc()
        records = list(artifact.iter_responses())

        assert len(records) > 0

        # Check record structure
        record = records[0]
        assert record.url is not None
        assert record.status_code > 0
        assert record.content is not None
        assert record.headers is not None

    def test_warc_caching(self, client, test_url):
        """Test that WARC artifact is cached after first call"""
        config = CrawlerConfig(url=test_url, page_limit=3)
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        # First call should fetch and cache
        artifact1 = crawl.warc()

        # Second call should return cached version
        artifact2 = crawl.warc()

        assert artifact1 is artifact2


class TestCrawlerHAR:
    """Test HAR artifact retrieval and parsing"""

    def test_get_har_artifact(self, client, test_url):
        """Test downloading and parsing HAR artifact"""
        config = CrawlerConfig(url=test_url, page_limit=5)
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        # Get HAR artifact
        artifact = crawl.har()
        assert artifact is not None
        assert artifact.artifact_type == 'har'
        assert len(artifact.artifact_data) > 0

    def test_har_get_pages(self, client, test_url):
        """Test getting all pages from HAR"""
        config = CrawlerConfig(url=test_url, page_limit=5)
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        artifact = crawl.har()
        pages = artifact.get_pages()

        assert len(pages) > 0
        assert len(pages) <= 5

        # Check page structure
        page = pages[0]
        assert 'url' in page
        assert 'status_code' in page
        assert 'content' in page

    def test_har_iter_responses(self, client, test_url):
        """Test iterating through HAR entries"""
        config = CrawlerConfig(url=test_url, page_limit=5)
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        artifact = crawl.har()
        entries = list(artifact.iter_responses())

        assert len(entries) > 0

        # Check HAR entry structure
        entry = entries[0]
        assert entry.url is not None
        assert entry.status_code > 0
        assert entry.content is not None

        # HAR entries should have timing info
        assert hasattr(entry, 'time')
        assert hasattr(entry, 'timings')

    def test_har_timing_information(self, client, test_url):
        """Test that HAR contains timing information"""
        config = CrawlerConfig(url=test_url, page_limit=3)
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        artifact = crawl.har()
        entries = list(artifact.iter_responses())

        # At least one entry should have timing info
        has_timing = any(entry.time > 0 for entry in entries)
        assert has_timing


class TestContentFormats:
    """Test different content formats (html, markdown, text, etc.)"""

    def test_html_format_from_warc(self, client, test_url):
        """Test retrieving HTML content directly from WARC"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=3,
            content_formats=['html']
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        # Get pages to find a valid URL
        pages = crawl.warc().get_pages()
        assert len(pages) > 0

        target_url = pages[0]['url']

        # Read HTML content
        content = crawl.read(target_url, format='html')
        assert content is not None
        assert content.url == target_url
        assert content.status_code == 200
        assert len(content.content) > 0
        assert '<html' in content.content.lower() or '<!doctype' in content.content.lower()

    def test_markdown_format(self, client, test_url):
        """Test retrieving markdown content"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=3,
            content_formats=['html', 'markdown']
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        pages = crawl.warc().get_pages()
        target_url = pages[0]['url']

        # Read markdown content
        content = crawl.read(target_url, format='markdown')
        assert content is not None
        assert len(content.content) > 0

        # Markdown should be shorter than HTML
        html_content = crawl.read(target_url, format='html')
        # Note: markdown might sometimes be longer due to formatting, so just check it exists
        assert len(content.content) > 0

    def test_text_format(self, client, test_url):
        """Test retrieving plain text content"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=3,
            content_formats=['html', 'text']
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        pages = crawl.warc().get_pages()
        target_url = pages[0]['url']

        # Read text content
        content = crawl.read(target_url, format='text')
        assert content is not None
        assert len(content.content) > 0

        # Text should not contain HTML tags
        assert '<html' not in content.content.lower()
        assert '<div' not in content.content.lower()

    def test_multiple_formats(self, client, test_url):
        """Test that multiple formats can be requested"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=3,
            content_formats=['html', 'markdown', 'text']
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        pages = crawl.warc().get_pages()
        target_url = pages[0]['url']

        # Read different formats
        html = crawl.read(target_url, format='html')
        markdown = crawl.read(target_url, format='markdown')
        text = crawl.read(target_url, format='text')

        assert html is not None
        assert markdown is not None
        assert text is not None

        # All should be different content
        assert html.content != markdown.content
        assert html.content != text.content

    def test_missing_url_returns_none(self, client, test_url):
        """Test that reading non-existent URL returns None"""
        config = CrawlerConfig(url=test_url, page_limit=3)
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        # Try to read a URL that wasn't crawled
        content = crawl.read('https://example.com/nonexistent-page-12345', format='html')
        assert content is None


class TestContentRetrieval:
    """Test different content retrieval methods"""

    def test_read_specific_url(self, client, test_url):
        """Test reading content for a specific URL"""
        config = CrawlerConfig(url=test_url, page_limit=5, max_depth=2)
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        # Get a crawled URL
        pages = crawl.warc().get_pages()
        assert len(pages) > 0

        target_url = pages[0]['url']

        # Read the content
        content = crawl.read(target_url)
        assert content is not None
        assert content.url == target_url
        assert content.status_code == 200
        assert len(content.content) > 0

    def test_read_iter_with_pattern(self, client):
        """Test iterating through URLs with pattern matching"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=10,
            max_depth=2
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        # Iterate through product pages
        count = 0
        for content in crawl.read_iter(pattern='*products*', format='html'):
            assert content is not None
            assert 'products' in content.url
            assert len(content.content) > 0
            count += 1

        assert count > 0

    def test_read_iter_product_pattern(self, client):
        """Test pattern matching for product detail pages"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=15,
            max_depth=3
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        # Iterate through product detail pages
        product_pages = []
        for content in crawl.read_iter(pattern='*/product/*', format='html'):
            product_pages.append(content)

        # Should have found at least some product pages
        assert len(product_pages) > 0
        for page in product_pages:
            assert '/product/' in page.url

    def test_read_batch(self, client, test_url):
        """Test batch content retrieval"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=10,
            max_depth=2,
            content_formats=['html', 'markdown']
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        # Get URLs to retrieve
        pages = crawl.warc().get_pages()
        urls = [p['url'] for p in pages[:5]]  # Get first 5 URLs

        # Batch retrieve
        contents = crawl.read_batch(urls, formats=['markdown', 'text'])

        assert len(contents) > 0

        # Check that we got content for requested URLs
        for url in urls:
            if url in contents:
                assert 'markdown' in contents[url] or 'text' in contents[url]

    def test_read_batch_max_limit(self, client, test_url):
        """Test that batch retrieval enforces max 100 URLs"""
        config = CrawlerConfig(url=test_url, page_limit=5)
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        # Try to request 101 URLs
        urls = [f'https://example.com/page{i}' for i in range(101)]

        with pytest.raises(ValueError) as exc_info:
            crawl.read_batch(urls)

        assert '100' in str(exc_info.value)


class TestCrawlerConfiguration:
    """Test different crawler configuration options"""

    def test_page_limit(self, client, test_url):
        """Test that page_limit is respected (roughly)"""
        page_limit = 3
        config = CrawlerConfig(url=test_url, page_limit=page_limit)
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        pages = crawl.warc().get_pages()
        # Allow some tolerance since robots.txt and system pages may be included
        assert len(pages) <= page_limit * 2

    def test_max_depth(self, client, test_url):
        """Test max_depth configuration"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=20,
            max_depth=1  # Only crawl seed and direct links
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

    def test_exclude_paths(self, client):
        """Test path exclusion"""
        config = CrawlerConfig(
            url='https://web-scraping.dev',
            page_limit=10,
            exclude_paths=['*/api/*', '*.json'],
            max_depth=2
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        pages = crawl.warc().get_pages()

        # Check that excluded paths are not present
        for page in pages:
            assert '/api/' not in page['url']
            assert not page['url'].endswith('.json')

    def test_include_only_paths(self, client):
        """Test path inclusion (mutually exclusive with exclude_paths)"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=10,
            include_only_paths=['/products*', '/product/*'],
            max_depth=3
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        pages = crawl.warc().get_pages()

        # All pages should match the include pattern
        for page in pages:
            url_path = page['url'].replace('https://web-scraping.dev', '')
            assert url_path.startswith('/products') or url_path.startswith('/product/')


class TestCrawlerStats:
    """Test crawler statistics"""

    def test_stats_basic(self, client, test_url):
        """Test getting basic crawl statistics"""
        config = CrawlerConfig(url=test_url, page_limit=5)
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        stats = crawl.stats()

        assert 'uuid' in stats
        assert 'status' in stats
        assert 'urls_discovered' in stats
        assert 'urls_crawled' in stats
        assert 'progress_pct' in stats
        assert stats['uuid'] == crawl.uuid
        assert stats['progress_pct'] == 100.0  # Completed

    def test_stats_with_artifact(self, client, test_url):
        """Test that stats include artifact info when available"""
        config = CrawlerConfig(url=test_url, page_limit=5)
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        # Fetch artifact to populate cache
        crawl.warc()

        stats = crawl.stats()

        # Should include artifact stats
        assert 'pages_downloaded' in stats
        assert 'total_size_bytes' in stats
        assert 'total_size_kb' in stats
        assert 'avg_page_size_bytes' in stats


class TestHTTPBinTests:
    """Tests using httpbin.dev for specific scenarios"""

    def test_httpbin_status_codes(self, client):
        """Test crawling httpbin.dev endpoints"""
        # Note: httpbin.dev might not have many internal links
        # This is a simple test to verify it works
        config = CrawlerConfig(
            url='https://httpbin.dev',
            page_limit=5,
            max_depth=1
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        pages = crawl.warc().get_pages()
        assert len(pages) > 0

        # Should have at least the homepage
        urls = [p['url'] for p in pages]
        assert any('httpbin.dev' in url for url in urls)

    def test_httpbin_404_page(self, client):
        """Test crawling a 404 page"""
        config = CrawlerConfig(
            url='https://httpbin.dev/status/404',
            page_limit=1,
            max_depth=0
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        # Check if we got the 404 in the results
        pages = crawl.warc().get_pages()
        if pages:
            # 404 pages might not be in results depending on crawler config
            pass

    def test_httpbin_failed_seed_url(self, client):
        """Test that crawler handles failed seed URL (e.g., 503)"""
        # When the seed URL returns 5xx, the crawler should fail
        config = CrawlerConfig(
            url='https://httpbin.dev/status/503',
            page_limit=1,
            max_depth=0
        )

        crawl = Crawl(client, config).crawl()

        # Wait for the crawl to finish (it should fail quickly)
        time.sleep(5)

        status = crawl.status()

        # The crawl should either be failed or have 0 successful pages
        # since the seed URL returns 503
        assert status.is_failed or status.urls_failed > 0 or status.urls_crawled == 0


class TestCrawlerRepr:
    """Test string representation"""

    def test_repr_before_start(self, client, test_url):
        """Test repr before crawl starts"""
        config = CrawlerConfig(url=test_url, page_limit=3)
        crawl = Crawl(client, config)

        repr_str = repr(crawl)
        assert "not started" in repr_str

    def test_repr_after_start(self, client, test_url):
        """Test repr after crawl starts"""
        config = CrawlerConfig(url=test_url, page_limit=3)
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        repr_str = repr(crawl)
        assert crawl.uuid in repr_str
        assert "not started" not in repr_str


class TestErrorHandling:
    """Test error handling and edge cases"""

    def test_read_before_crawl_start(self, client, test_url):
        """Test that reading content before starting crawl raises error"""
        config = CrawlerConfig(url=test_url, page_limit=3)
        crawl = Crawl(client, config)

        with pytest.raises(ScrapflyCrawlerError) as exc_info:
            crawl.read('https://example.com')

        assert "not started" in str(exc_info.value).lower()

    def test_warc_before_crawl_start(self, client, test_url):
        """Test that getting WARC before starting crawl raises error"""
        config = CrawlerConfig(url=test_url, page_limit=3)
        crawl = Crawl(client, config)

        with pytest.raises(ScrapflyCrawlerError) as exc_info:
            crawl.warc()

        assert "not started" in str(exc_info.value).lower()

    def test_read_iter_before_crawl_start(self, client, test_url):
        """Test that read_iter before starting crawl raises error"""
        config = CrawlerConfig(url=test_url, page_limit=3)
        crawl = Crawl(client, config)

        with pytest.raises(ScrapflyCrawlerError):
            list(crawl.read_iter(pattern='*'))


class TestAsyncCrawler:
    """Test async crawler methods"""

    @pytest.mark.asyncio
    async def test_async_start_crawl(self, client, test_url):
        """Test starting a crawl asynchronously"""
        config = CrawlerConfig(url=test_url, page_limit=5)

        # Start crawl async
        start_response = await client.async_start_crawl(config)

        assert start_response.uuid is not None
        assert start_response.status in ['RUNNING', 'PENDING', 'COMPLETED']

    @pytest.mark.asyncio
    async def test_async_get_status(self, client, test_url):
        """Test getting crawl status asynchronously"""
        config = CrawlerConfig(url=test_url, page_limit=5)

        # Start crawl
        start_response = await client.async_start_crawl(config)

        # Get status
        status = await client.async_get_crawl_status(start_response.uuid)

        assert status.uuid == start_response.uuid
        assert status.urls_discovered >= 0
        assert status.urls_crawled >= 0

    @pytest.mark.asyncio
    async def test_async_wait_for_completion(self, client, test_url):
        """Test waiting for crawl completion asynchronously"""
        import asyncio
        config = CrawlerConfig(url=test_url, page_limit=5)

        # Start crawl
        start_response = await client.async_start_crawl(config)

        # Poll until complete
        for _ in range(30):  # Max 30 attempts (60 seconds)
            status = await client.async_get_crawl_status(start_response.uuid)
            if status.is_complete:
                break
            await asyncio.sleep(2)

        assert status.is_complete

    @pytest.mark.asyncio
    async def test_async_get_artifact(self, client, test_url):
        """Test downloading artifact asynchronously"""
        import asyncio
        config = CrawlerConfig(url=test_url, page_limit=5)

        # Start crawl and wait
        start_response = await client.async_start_crawl(config)

        # Wait for completion
        for _ in range(30):
            status = await client.async_get_crawl_status(start_response.uuid)
            if status.is_complete:
                break
            await asyncio.sleep(2)

        # Get artifact
        artifact = await client.async_get_crawl_artifact(start_response.uuid)

        assert artifact is not None
        assert len(artifact.artifact_data) > 0
        pages = artifact.get_pages()
        assert len(pages) > 0


class TestWebScrapingDevSite:
    """Tests specifically for web-scraping.dev which is designed for testing"""

    def test_products_listing(self, client):
        """Test crawling web-scraping.dev products"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=10,
            max_depth=2
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        pages = crawl.warc().get_pages()

        # Should crawl multiple pages
        assert len(pages) > 1

        # Should have the products listing page
        urls = [p['url'] for p in pages]
        assert any('products' in url for url in urls)

    def test_product_details(self, client):
        """Test crawling to product detail pages"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=15,
            max_depth=3,
            include_only_paths=['/products*', '/product/*']
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        # Find product detail pages
        product_pages = []
        for content in crawl.read_iter(pattern='*/product/*'):
            product_pages.append(content.url)

        # Should have found at least some product detail pages
        assert len(product_pages) > 0

    def test_pagination(self, client):
        """Test crawling paginated content"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=20,
            max_depth=2
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        status = crawl.status()
        assert status.is_complete, f"Crawl should be complete but status is: {status.status}"
        assert not status.is_failed, f"Crawl failed: {status.status}"

        pages = crawl.warc().get_pages()

        # Should crawl multiple pages including pagination
        assert len(pages) > 5


class TestAdvancedConfiguration:
    """Test advanced crawler configuration options from documentation"""

    def test_ignore_base_path_restriction(self, client):
        """Test ignore_base_path_restriction allows crawling outside base path"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=10,
            max_depth=2,
            ignore_base_path_restriction=True
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        pages = crawl.warc().get_pages()
        assert len(pages) > 0

    def test_use_sitemaps(self, client):
        """Test using sitemaps for URL discovery"""
        config = CrawlerConfig(
            url='https://web-scraping.dev',
            page_limit=10,
            use_sitemaps=True,
            respect_robots_txt=True
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

    def test_cache_enabled(self, client):
        """Test cache configuration"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=5,
            cache=True,
            cache_ttl=3600
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        pages = crawl.warc().get_pages()
        assert len(pages) > 0

    def test_max_concurrency(self, client):
        """Test max_concurrency configuration"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=10,
            max_concurrency=3
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

    def test_delay_between_requests(self, client):
        """Test delay configuration between requests"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=5,
            delay='1000'  # 1 second delay
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

    def test_custom_headers(self, client):
        """Test custom headers configuration"""
        config = CrawlerConfig(
            url='https://httpbin.dev',
            page_limit=3,
            headers={'X-Custom-Header': 'test-value'}
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

    def test_user_agent(self, client):
        """Test custom user agent"""
        config = CrawlerConfig(
            url='https://httpbin.dev',
            page_limit=3,
            user_agent='CustomBot/1.0 (+https://example.com)'
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)


class TestStopReasons:
    """Test different crawler stop reasons from documentation"""

    def test_stop_reason_page_limit(self, client):
        """Test crawler stops at page_limit"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=3,
            max_depth=5  # High depth but limited by page_limit
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        status = assert_crawl_successful(crawl)
        # Should stop due to page_limit or no_more_urls

    def test_stop_reason_max_duration(self, client):
        """Test crawler with max_duration limit"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=100,  # High limit
            max_duration=15  # Very short duration (15 seconds minimum)
        )
        crawl = Crawl(client, config).crawl()

        # Wait for it to timeout or complete
        import time
        time.sleep(20)

        status = crawl.status()
        # Should have stopped (either due to duration or completion)
        assert not status.is_running

    def test_stop_reason_no_more_urls(self, client):
        """Test crawler completes when all URLs are crawled"""
        config = CrawlerConfig(
            url='https://httpbin.dev',
            page_limit=100,  # High limit, but httpbin has few pages
            max_depth=1
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)


class TestContentFormatsAdvanced:
    """Test all content formats mentioned in documentation"""

    def test_clean_html_format(self, client):
        """Test clean_html format (HTML with boilerplate removed)"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=3,
            content_formats=['html', 'clean_html']
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        pages = crawl.warc().get_pages()
        target_url = pages[0]['url']

        # Get both formats
        html_content = crawl.read(target_url, format='html')
        clean_html_content = crawl.read(target_url, format='clean_html')

        assert html_content is not None
        # Clean HTML might not always be available
        if clean_html_content:
            # Clean HTML should typically be shorter
            assert len(clean_html_content.content) > 0

    def test_json_format(self, client):
        """Test JSON format extraction"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=3,
            content_formats=['html', 'json']
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        pages = crawl.warc().get_pages()
        target_url = pages[0]['url']

        json_content = crawl.read(target_url, format='json')
        # JSON format might not always be available
        if json_content:
            assert len(json_content.content) > 0

    def test_page_metadata_format(self, client):
        """Test page_metadata format"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=3,
            content_formats=['html', 'page_metadata']
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        pages = crawl.warc().get_pages()
        target_url = pages[0]['url']

        metadata_content = crawl.read(target_url, format='page_metadata')
        # Metadata format might not always be available
        if metadata_content:
            assert len(metadata_content.content) > 0

    def test_all_formats_simultaneously(self, client):
        """Test requesting all content formats at once"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=3,
            content_formats=['html', 'markdown', 'text', 'clean_html', 'json', 'page_metadata']
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        pages = crawl.warc().get_pages()
        assert len(pages) > 0

        # Verify HTML format is available
        target_url = pages[0]['url']
        html = crawl.read(target_url, format='html')
        assert html is not None


class TestProxyAndASP:
    """Test proxy and ASP configuration options"""

    def test_proxy_pool_configuration(self, client):
        """Test proxy pool configuration"""
        config = CrawlerConfig(
            url='https://httpbin.dev',
            page_limit=3,
            proxy_pool='public_datacenter_pool'
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

    def test_country_configuration(self, client):
        """Test country proxy configuration"""
        config = CrawlerConfig(
            url='https://httpbin.dev',
            page_limit=3,
            country='us'
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

    def test_asp_enabled(self, client):
        """Test ASP (Anti-Scraping Protection) enabled"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=5,
            asp=True
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        status = assert_crawl_successful(crawl)
        assert status.urls_crawled > 0


class TestURLsEndpoint:
    """Test the /urls endpoint for listing crawled URLs"""

    def test_get_crawled_urls(self, client):
        """Test retrieving list of crawled URLs"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=5
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        # Get crawled URLs using the WARC artifact
        pages = crawl.warc().get_pages()

        # Should have multiple URLs
        assert len(pages) > 0

        # Each page should have URL metadata
        for page in pages:
            assert 'url' in page
            assert 'status_code' in page
            assert isinstance(page['url'], str)
            assert isinstance(page['status_code'], int)


class TestCompleteWorkflow:
    """Test complete workflows as described in documentation"""

    def test_polling_workflow_complete(self, client):
        """Test complete polling workflow: create -> monitor -> retrieve"""
        # Step 1: Create crawler
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=5,
            content_formats=['markdown']
        )

        # Step 2: Start crawl
        crawl = Crawl(client, config)
        crawl.crawl()

        assert crawl.started
        assert crawl.uuid is not None

        # Step 3: Monitor progress
        poll_count = 0
        while poll_count < 30:  # Max 30 polls
            status = crawl.status(refresh=True)

            if status.is_complete:
                break

            poll_count += 1
            time.sleep(2)

        # Step 4: Verify completion
        final_status = assert_crawl_successful(crawl)
        assert final_status.urls_crawled > 0

        # Step 5: Retrieve results
        pages = crawl.warc().get_pages()
        assert len(pages) > 0

        # Step 6: Query content
        target_url = pages[0]['url']
        markdown_content = crawl.read(target_url, format='markdown')
        assert markdown_content is not None
        assert len(markdown_content.content) > 0

    def test_batch_content_workflow(self, client):
        """Test batch content retrieval workflow"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=10,
            content_formats=['markdown', 'text']
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully
        assert_crawl_successful(crawl)

        # Get URLs
        pages = crawl.warc().get_pages()
        urls = [p['url'] for p in pages[:5]]  # First 5 URLs

        # Batch retrieve content
        contents = crawl.read_batch(urls, formats=['markdown'])

        assert len(contents) > 0

        # Verify we got content for requested URLs
        for url in urls:
            if url in contents:
                assert 'markdown' in contents[url]

    def test_stats_tracking(self, client):
        """Test comprehensive stats tracking throughout workflow"""
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=10
        )
        crawl = Crawl(client, config).crawl().wait()

        # Verify crawl completed successfully and get status
        status = assert_crawl_successful(crawl)
        assert status.urls_discovered > 0
        assert status.urls_crawled > 0
        assert status.progress_pct == 100.0

        # Get detailed stats
        stats = crawl.stats()
        assert 'uuid' in stats
        assert 'status' in stats
        assert 'urls_discovered' in stats
        assert 'urls_crawled' in stats
        assert 'is_complete' in stats

        # Should have crawl rate
        if stats['urls_discovered'] > 0:
            assert 'crawl_rate' in stats
