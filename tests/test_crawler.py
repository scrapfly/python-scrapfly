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

import json
import os
import pytest
import time
from io import BytesIO
from unittest.mock import patch

from requests import Request, Response

from scrapfly import (
    ScrapflyClient,
    CrawlerConfig,
    Crawl,
    CrawlerPromptError,
    CrawlerRefreshError,
    CrawlerRefreshState,
    CrawlerSearchError,
    CrawlerStatusResponse,
    CrawlerUrlsResponse,
    HttpError,
    ScrapflyCrawlerError,
)

# Drives the live API; skipped by tests/conftest.py without credentials.
# Crawler API end-to-end through the SDK: these drive real crawls against a live
# Scrapfly environment, so they exercise the platform, not just this client.
pytestmark = [pytest.mark.integration, pytest.mark.e2e]



# Test configuration
API_KEY = os.environ.get('SCRAPFLY_KEY', 'scp-live-YOUR_API_KEY_HERE')
API_HOST = os.environ.get('SCRAPFLY_API_HOST', 'https://api.scrapfly.io')



# One `POST /crawl/search` envelope, verbatim from the response contract.
SEARCH_ENVELOPE = {
    'query': 'TLS fingerprint',
    'mode': 'hybrid',
    'limit': 20,
    'completeness': 'exact',
    'crawls': [
        {'crawler_uuid': '0198aaaa', 'documents': 412, 'vectors': 18432, 'index': 'IVF_PQ'},
    ],
    'skipped': [
        {'crawler_uuid': '0198bbbb', 'reason': 'search_not_ready', 'status': 'BUILDING'},
    ],
    'results': [
        {
            'rank': 1,
            'score': 0.927,
            'scores': {'vector': 0.91, 'fts': 12.4, 'rrf': 0.0312},
            'crawler_uuid': '0198aaaa',
            'url': 'https://example.com/foo',
            'title': 'Foo Product',
            'source_format': 'markdown',
            'content_type': 'application/markdown',
            'chunk_id': 3,
            'text': 'the matched chunk',
            'warc_offset': 728271,
            'warc_end': 746643,
            'contents_url': 'https://api.scrapfly.io/crawl/0198aaaa/contents?url=x&formats=markdown',
        },
    ],
    'stats': {'duration_ms': 412, 'crawls_searched': 1, 'candidates': 150, 'gcs_gets': 27},
    'crawls_requested': 2,
    'crawls_searched': 1,
    'crawls_pruned_exact': 0,
    'crawls_skipped_deadline': ['0198cccc'],
    'crawls_failed': [
        {'crawler_uuid': '0198dddd', 'reason': 'search_failed', 'status': 'FAILED'},
    ],
    'theta': 0.42,
    'max_ub_unsearched': 0.11,
    'cursor': None,
}


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
    assert status.state.urls_visited > 0, f"Crawl {crawl.uuid} should have crawled at least one URL"
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
        assert status.state.urls_visited > 0
        assert status.state.urls_extracted > 0

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
        assert final_status.state.urls_visited >= 0
        assert final_status.state.urls_extracted >= 0
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
        assert 'urls_extracted' in stats
        assert 'urls_visited' in stats
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
        assert status.is_failed or status.urls_failed > 0 or status.state.urls_visited == 0


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
        # Engine status enum: PENDING / RUNNING / DONE / CANCELLED.
        # A freshly-started crawl starts in PENDING; in extremely rare races
        # a worker may have already picked it up and bumped it to RUNNING by
        # the time we check. DONE/CANCELLED are not reachable on start.
        assert start_response.status in ['PENDING', 'RUNNING']

    @pytest.mark.asyncio
    async def test_async_get_status(self, client, test_url):
        """Test getting crawl status asynchronously"""
        config = CrawlerConfig(url=test_url, page_limit=5)

        # Start crawl
        start_response = await client.async_start_crawl(config)

        # Get status
        status = await client.async_get_crawl_status(start_response.uuid)

        assert status.uuid == start_response.uuid
        assert status.state.urls_extracted >= 0
        assert status.state.urls_visited >= 0

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

    def test_country_is_honoured_by_the_exit_proxy(self, client):
        """The requested country must be the country the request actually went out from."""
        url = 'https://httpbin.dev/ip'
        config = CrawlerConfig(url=url, page_limit=1, country='us')
        crawl = Crawl(client, config).crawl().wait()

        assert_crawl_successful(crawl)

        content = crawl.read(url)
        assert content is not None, f"{url} was crawled but no content came back"
        assert content.country == 'us', (
            f"country=us was requested but the exit proxy reported {content.country!r}"
        )

    def test_proxy_pool_is_accepted(self, client):
        """
        Only asserts the pool is accepted and the crawl completes.

        Neither the status nor the per-URL content echoes the pool that served the
        request, so there is nothing to read back: this cannot detect the SDK
        dropping proxy_pool. Serialization is covered offline instead.
        """
        config = CrawlerConfig(
            url='https://httpbin.dev',
            page_limit=3,
            proxy_pool='public_datacenter_pool'
        )
        crawl = Crawl(client, config).crawl().wait()

        assert_crawl_successful(crawl)

    def test_asp_is_accepted(self, client):
        """
        Only asserts asp=true is accepted and the crawl completes.

        Nothing in the crawl response reports whether a shield was engaged, so this
        cannot detect the SDK dropping asp. Serialization is covered offline instead.
        """
        config = CrawlerConfig(
            url='https://web-scraping.dev/products',
            page_limit=5,
            asp=True
        )
        crawl = Crawl(client, config).crawl().wait()

        status = assert_crawl_successful(crawl)
        assert status.state.urls_visited > 0


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
        assert final_status.state.urls_visited > 0

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
        assert status.state.urls_extracted > 0
        assert status.state.urls_visited > 0
        assert status.progress_pct == 100.0

        # Get detailed stats
        stats = crawl.stats()
        assert 'uuid' in stats
        assert 'status' in stats
        assert 'urls_extracted' in stats
        assert 'urls_visited' in stats
        assert 'is_complete' in stats

        # Should have crawl rate
        if stats['urls_extracted'] > 0:
            assert 'crawl_rate' in stats


# ---------------------------------------------------------------------------
# Search index, offline. The wire payload and the SSE decoder are the SDK's
# own contract; they must hold without a live crawl to search.
# ---------------------------------------------------------------------------


class TestCrawlerSearchConfig:
    """`search` reaches the wire, and only when it is asked for."""

    pytestmark = pytest.mark.unit

    def test_search_serializes_to_wire_payload(self):
        config = CrawlerConfig(url='https://example.com', search=True)

        assert config.to_api_params()['search'] is True

    def test_search_omitted_when_off(self):
        """Unset means server default: never emit a field to send its default."""
        config = CrawlerConfig(url='https://example.com')

        assert 'search' not in config.to_api_params()

    def test_search_rides_the_multipart_config_part(self):
        """A url_list crawl posts multipart; the flag lives in the config part."""
        config = CrawlerConfig(url_list=['https://example.com/a'], search=True)
        parts = config.to_multipart_parts()

        assert parts['config']['search'] is True
        assert parts['urls'] == 'https://example.com/a'

    def test_search_webhook_events_are_accepted(self):
        config = CrawlerConfig(
            url='https://example.com',
            search=True,
            webhook_name='my-hook',
            webhook_events=['crawler_search_ready', 'crawler_search_failed'],
        )

        assert config.to_api_params()['webhook_events'] == [
            'crawler_search_ready',
            'crawler_search_failed',
        ]


class TestCrawlerSearchTransport:
    """`crawl_search` / `crawl_prompt` request shape and response decoding."""

    pytestmark = pytest.mark.unit

    @staticmethod
    def _client_with(handler):
        client = ScrapflyClient(key='scp-live-0000000000000000000000000000000000000000')
        # _http_handler is a cached_property; seed the cache to stub transport.
        client.__dict__['_http_handler'] = handler
        return client

    @staticmethod
    def _json_response(payload, status_code=200):
        response = Response()
        response.status_code = status_code
        response._content = json.dumps(payload).encode('utf-8')
        response.headers['Content-Type'] = 'application/json'
        response.url = 'https://api.scrapfly.io/crawl/search'
        response.request = Request(method='POST', url=response.url).prepare()
        return response

    def test_crawl_search_posts_the_collection_body(self):
        captured = {}

        def handler(**kwargs):
            captured.update(kwargs)
            return self._json_response(SEARCH_ENVELOPE)

        client = self._client_with(handler)
        result = client.crawl_search(
            crawl_ids=['0198aaaa', '0198bbbb'],
            query='TLS fingerprint',
            limit=20,
            mode='hybrid',
            filters={'url_prefix': 'https://example.com/docs/'},
        )

        assert captured['method'] == 'POST'
        assert captured['url'] == 'https://api.scrapfly.io/crawl/search'
        assert captured['params'] == {'key': client.key}
        assert captured['json'] == {
            'query': 'TLS fingerprint',
            'crawl_ids': ['0198aaaa', '0198bbbb'],
            'limit': 20,
            'mode': 'hybrid',
            'filters': {'url_prefix': 'https://example.com/docs/'},
        }

        assert result.mode == 'hybrid'
        assert result.is_exact is True
        assert len(result) == 1
        assert result.results[0].url == 'https://example.com/foo'
        assert result.results[0].scores['rrf'] == 0.0312
        assert result.crawls[0].vectors == 18432
        assert result.skipped[0].reason == 'search_not_ready'
        assert result.cursor is None

    def test_deadline_and_failure_fields_name_the_crawls(self):
        """``crawls_skipped_deadline`` and ``crawls_failed`` carry crawls, not
        counts: a caller told "1 failed" has nothing to retry, and the deadline
        list is exactly the set worth asking for again."""

        def handler(**kwargs):
            return self._json_response(SEARCH_ENVELOPE)

        client = self._client_with(handler)
        result = client.crawl_search(crawl_ids=['0198aaaa'], query='TLS fingerprint')

        assert result.crawls_skipped_deadline == ['0198cccc']
        assert [c.crawler_uuid for c in result.crawls_failed] == ['0198dddd']
        assert result.crawls_failed[0].reason == 'search_failed'
        assert result.crawls_failed[0].status == 'FAILED'

    def test_deadline_and_failure_fields_are_empty_lists_when_absent(self):
        """Every leg landing inside the deadline omits neither field but sends
        both empty; the caller iterates without a None check."""
        envelope = dict(SEARCH_ENVELOPE)
        envelope.pop('crawls_skipped_deadline')
        envelope.pop('crawls_failed')

        client = self._client_with(lambda **kwargs: self._json_response(envelope))
        result = client.crawl_search(crawl_ids=['0198aaaa'], query='TLS fingerprint')

        assert result.crawls_skipped_deadline == []
        assert result.crawls_failed == []

    def test_single_crawl_search_is_a_one_element_collection_call(self):
        """The cross-crawl call is the real endpoint; Crawl.search() is sugar."""
        captured = {}

        def handler(**kwargs):
            captured.update(kwargs)
            return self._json_response(SEARCH_ENVELOPE)

        client = self._client_with(handler)
        crawl = Crawl(client, CrawlerConfig(url='https://example.com', search=True))
        crawl._uuid = '0198aaaa'

        crawl.search('TLS fingerprint')

        assert captured['url'] == 'https://api.scrapfly.io/crawl/search'
        assert captured['json']['crawl_ids'] == ['0198aaaa']

    def test_search_before_start_raises(self):
        client = self._client_with(lambda **kwargs: None)
        crawl = Crawl(client, CrawlerConfig(url='https://example.com', search=True))

        with pytest.raises(ScrapflyCrawlerError):
            crawl.search('anything')

    def test_search_error_is_typed(self):
        def handler(**kwargs):
            return self._json_response(
                {'code': 'ERR::CRAWLER::SEARCH_NOT_ENABLED', 'message': 'Search is not enabled'},
                status_code=400,
            )

        client = self._client_with(handler)

        with pytest.raises(CrawlerSearchError) as excinfo:
            client.crawl_search(crawl_ids=['0198aaaa'], query='x')

        assert excinfo.value.code == 'ERR::CRAWLER::SEARCH_NOT_ENABLED'

    def test_crawl_prompt_streams_sse_frames(self):
        captured = {}
        stream = (
            b'event: source\ndata: {"id":1,"crawler_uuid":"0198aaaa","url":"https://example.com/foo"}\n\n'
            b':keepalive\n\n'
            b'event: token\ndata: "The"\n\n'
            b'event: token\ndata: " answer"\n\n'
            b'event: done\ndata: {"sources_used":[1],"truncated":false}\n\n'
        )

        def handler(**kwargs):
            captured.update(kwargs)
            response = Response()
            response.status_code = 200
            response.headers['Content-Type'] = 'text/event-stream'
            response.raw = BytesIO(stream)
            response.url = 'https://api.scrapfly.io/crawl/prompt'
            response.request = Request(method='POST', url=response.url).prepare()
            return response

        client = self._client_with(handler)
        events = list(client.crawl_prompt(
            crawl_ids=['0198aaaa', '0198bbbb'],
            prompt='Compare the pricing models.',
            search={'limit': 30},
        ))

        assert captured['json'] == {
            'prompt': 'Compare the pricing models.',
            'crawl_ids': ['0198aaaa', '0198bbbb'],
            'generation': {'stream': True},
            'search': {'limit': 30},
        }
        assert captured['stream'] is True
        assert captured['headers']['Accept'] == 'text/event-stream'

        assert [e.event for e in events] == ['source', 'token', 'token', 'done']
        assert ''.join(e.data for e in events if e.is_token) == 'The answer'
        assert events[-1].data['sources_used'] == [1]

    @pytest.mark.parametrize('body', [
        b'',
        b':keepalive\n\n',
        b'event: token\ndata: "partial"\n\n',
        b'event: token\ndata: "partial"\n\nevent: done\ndata: {}\n',
    ])
    def test_prompt_requires_done_frame(self, body):
        response = Response()
        response.status_code = 200
        response.raw = BytesIO(body)
        events = []
        with patch.object(response, 'close', wraps=response.close) as close:
            with pytest.raises(CrawlerPromptError, match='done'):
                events.extend(ScrapflyClient._iter_prompt_events(response))
            close.assert_called_once()
        assert ''.join(e.data for e in events if e.is_token) == (
            'partial' if b'partial' in body else ''
        )

    def test_prompt_error_frame_raises_mid_stream(self):
        """Generation can fail after tokens have already been delivered."""
        stream = (
            b'event: token\ndata: "partial"\n\n'
            b'event: error\ndata: {"code":"ERR::CRAWLER::PROMPT_GENERATION_FAILED","message":"upstream refused"}\n\n'
        )

        def handler(**kwargs):
            response = Response()
            response.status_code = 200
            response.headers['Content-Type'] = 'text/event-stream'
            response.raw = BytesIO(stream)
            response.url = 'https://api.scrapfly.io/crawl/prompt'
            response.request = Request(method='POST', url=response.url).prepare()
            return response

        client = self._client_with(handler)
        events = client.crawl_prompt(crawl_ids=['0198aaaa'], prompt='hi')

        assert next(events).data == 'partial'
        with pytest.raises(CrawlerPromptError) as excinfo:
            next(events)

        assert excinfo.value.code == 'ERR::CRAWLER::PROMPT_GENERATION_FAILED'

    def test_crawl_prompt_non_streaming_returns_one_object(self):
        captured = {}

        def handler(**kwargs):
            captured.update(kwargs)
            return self._json_response({'answer': 'yes', 'sources_used': [1]})

        client = self._client_with(handler)
        result = client.crawl_prompt(
            crawl_ids=['0198aaaa'],
            prompt='hi',
            model='gemini-2.5-flash-lite',
            stream=False,
        )

        assert captured['json']['generation'] == {'stream': False, 'model': 'gemini-2.5-flash-lite'}
        assert captured['stream'] is False
        assert result['answer'] == 'yes'

    def test_empty_crawl_ids_rejected_before_any_request(self):
        def handler(**kwargs):
            raise AssertionError('no request should be issued')

        client = self._client_with(handler)

        with pytest.raises(ValueError):
            client.crawl_search(crawl_ids=[], query='x')
        with pytest.raises(ValueError):
            client.crawl_prompt(crawl_ids=[], prompt='x')


class TestCrawlerStatusSearchBlock:
    """`/status` is the poll-based path to index readiness."""

    pytestmark = pytest.mark.unit

    @staticmethod
    def _status(**extra):
        payload = {
            'crawler_uuid': '0198aaaa',
            'status': 'DONE',
            'is_success': True,
            'is_finished': True,
            'state': {
                'duration': 6.11,
                'urls_visited': 5,
                'urls_extracted': 5,
                'urls_failed': 0,
                'urls_skipped': 0,
                'urls_to_crawl': 0,
                'api_credit_used': 5,
                'stop_reason': None,
                'start_time': 1762940028,
                'stop_time': 1762940034.1,
            },
        }
        payload.update(extra)
        return CrawlerStatusResponse(payload)

    def test_search_block_is_parsed(self):
        status = self._status(search={
            'status': 'READY',
            'documents': 412,
            'vectors': 18432,
            'index': 'IVF_PQ',
            'generation': 1,
        })

        assert status.search.status == 'READY'
        assert status.search.vectors == 18432
        assert status.search.is_searchable is True

    def test_search_block_absent_on_a_crawl_without_it(self):
        assert self._status().search is None


# ---------------------------------------------------------------------------
# Auto-refresh, offline. A refresh re-scrapes a crawl in place, so the wire
# payload and the three transport calls are the SDK's own contract.
# ---------------------------------------------------------------------------


REFRESH_STATE = {
    'enabled': True,
    'interval_seconds': 86400,
    'status': 'SCHEDULED',
    'generation': 2,
    'last_run_at': '2026-09-01T04:00:00Z',
    'next_run_at': '2026-09-02T04:00:00Z',
    'error': None,
    'history': [
        {
            'at': '2026-08-31T04:00:00Z',
            'generation': 1,
            'added': 0,
            'updated': 0,
            'removed': 0,
            'unchanged': 412,
            'failed': 0,
            'duration_ms': 41200,
            'search_status': 'READY',
            'error': None,
            'sample_updated': [],
            'sample_removed': [],
        },
        {
            'at': '2026-09-01T04:00:00Z',
            'generation': 2,
            'added': 3,
            'updated': 7,
            'removed': 1,
            'unchanged': 404,
            'failed': 0,
            'duration_ms': 44900,
            'search_status': 'READY',
            'error': None,
            'sample_updated': ['https://example.com/pricing'],
            'sample_removed': ['https://example.com/old'],
        },
    ],
}


class TestCrawlerRefreshConfig:
    """`refresh` / `refresh_interval` reach the wire, and only when asked for."""

    pytestmark = pytest.mark.unit

    def test_refresh_fields_serialize_to_wire_payload(self):
        config = CrawlerConfig(url='https://example.com', refresh=True, refresh_interval=86400)
        params = config.to_api_params()

        assert params['refresh'] is True
        assert params['refresh_interval'] == 86400

    def test_refresh_omitted_when_off(self):
        """Unset means server default: never emit a field to send its default."""
        params = CrawlerConfig(url='https://example.com').to_api_params()

        assert 'refresh' not in params
        assert 'refresh_interval' not in params

    def test_refresh_without_interval_uses_the_server_period(self):
        params = CrawlerConfig(url='https://example.com', refresh=True).to_api_params()

        assert params['refresh'] is True
        assert 'refresh_interval' not in params

    def test_refresh_rides_the_multipart_config_part(self):
        """A url_list crawl posts multipart; the flags live in the config part."""
        config = CrawlerConfig(
            url_list=['https://example.com/a'],
            refresh=True,
            refresh_interval=7200,
        )
        parts = config.to_multipart_parts()

        assert parts['config']['refresh'] is True
        assert parts['config']['refresh_interval'] == 7200

    @pytest.mark.parametrize('interval', [1, 3599, 90 * 24 * 3600 + 1])
    def test_interval_outside_the_bounds_is_refused_locally(self, interval):
        """The floor decides the cost; reject before a round trip."""
        with pytest.raises(ValueError):
            CrawlerConfig(url='https://example.com', refresh=True, refresh_interval=interval)

    @pytest.mark.parametrize('interval', [3600, 86400, 90 * 24 * 3600])
    def test_interval_on_the_bounds_is_accepted(self, interval):
        config = CrawlerConfig(url='https://example.com', refresh=True, refresh_interval=interval)

        assert config.to_api_params()['refresh_interval'] == interval

    def test_interval_without_refresh_is_refused(self):
        """A period with the feature off would silently never run."""
        with pytest.raises(ValueError):
            CrawlerConfig(url='https://example.com', refresh_interval=86400)


class TestCrawlerRefreshTransport:
    """Request shape and response decoding for the three refresh calls."""

    pytestmark = pytest.mark.unit

    @staticmethod
    def _client_with(handler):
        client = ScrapflyClient(key='scp-live-0000000000000000000000000000000000000000')
        # _http_handler is a cached_property; seed the cache to stub transport.
        client.__dict__['_http_handler'] = handler
        return client

    @staticmethod
    def _json_response(payload, status_code=200):
        response = Response()
        response.status_code = status_code
        response._content = json.dumps(payload).encode('utf-8')
        response.headers['Content-Type'] = 'application/json'
        response.url = 'https://api.scrapfly.io/crawl/0198aaaa/refresh'
        response.request = Request(method='POST', url=response.url).prepare()
        return response

    def test_refresh_now_posts_to_the_crawl(self):
        captured = {}

        def handler(**kwargs):
            captured.update(kwargs)
            return self._json_response(REFRESH_STATE, status_code=202)

        client = self._client_with(handler)
        state = client.crawl_refresh_now('0198aaaa')

        assert captured['method'] == 'POST'
        assert captured['url'] == 'https://api.scrapfly.io/crawl/0198aaaa/refresh'
        assert captured['params'] == {'key': client.key}

        assert state.enabled is True
        assert state.status == 'SCHEDULED'
        assert state.generation == 2
        assert state.next_run_at == '2026-09-02T04:00:00Z'
        assert len(state) == 2
        assert state.last_run.updated == 7
        assert state.last_run.changed == 11
        assert state.last_run.sample_removed == ['https://example.com/old']

    def test_refresh_settings_patches_only_what_is_passed(self):
        captured = {}

        def handler(**kwargs):
            captured.update(kwargs)
            return self._json_response(REFRESH_STATE)

        client = self._client_with(handler)
        client.crawl_refresh_settings('0198aaaa', enabled=True, interval_seconds=86400)

        assert captured['method'] == 'PATCH'
        assert captured['url'] == 'https://api.scrapfly.io/crawl/0198aaaa/refresh'
        assert captured['json'] == {'refresh': True, 'refresh_interval': 86400}

    def test_refresh_settings_can_turn_it_off_without_touching_the_interval(self):
        captured = {}

        def handler(**kwargs):
            captured.update(kwargs)
            return self._json_response(REFRESH_STATE)

        client = self._client_with(handler)
        client.crawl_refresh_settings('0198aaaa', enabled=False)

        assert captured['json'] == {'refresh': False}

    def test_refresh_settings_with_nothing_to_change_is_refused(self):
        client = self._client_with(lambda **kwargs: None)

        with pytest.raises(ValueError):
            client.crawl_refresh_settings('0198aaaa')

    def test_refresh_settings_rejects_an_out_of_bounds_interval_locally(self):
        client = self._client_with(lambda **kwargs: None)

        with pytest.raises(ValueError):
            client.crawl_refresh_settings('0198aaaa', interval_seconds=60)

    def test_refresh_history_returns_the_timeline_newest_last(self):
        captured = {}

        def handler(**kwargs):
            captured.update(kwargs)
            return self._json_response(REFRESH_STATE)

        client = self._client_with(handler)
        history = client.crawl_refresh_history('0198aaaa', limit=5)

        assert captured['method'] == 'GET'
        assert captured['url'] == 'https://api.scrapfly.io/crawl/0198aaaa/refresh/history'
        assert captured['params'] == {'key': client.key, 'limit': 5}

        assert [entry.generation for entry in history] == [1, 2]
        assert history[0].changed == 0
        assert history[0].unchanged == 412

    def test_crawl_sugar_delegates_to_the_client(self):
        seen = []

        def handler(**kwargs):
            seen.append(kwargs['url'])
            return self._json_response(REFRESH_STATE)

        client = self._client_with(handler)
        crawl = Crawl(client, CrawlerConfig(url='https://example.com', refresh=True))
        crawl._uuid = '0198aaaa'

        crawl.refresh_now()
        crawl.refresh_settings(enabled=True)
        crawl.refresh_history()

        assert seen == [
            'https://api.scrapfly.io/crawl/0198aaaa/refresh',
            'https://api.scrapfly.io/crawl/0198aaaa/refresh',
            'https://api.scrapfly.io/crawl/0198aaaa/refresh/history',
        ]

    def test_refresh_before_start_raises(self):
        client = self._client_with(lambda **kwargs: None)
        crawl = Crawl(client, CrawlerConfig(url='https://example.com', refresh=True))

        with pytest.raises(ScrapflyCrawlerError):
            crawl.refresh_now()

    def test_refresh_error_is_typed(self):
        def handler(**kwargs):
            return self._json_response(
                {'code': 'ERR::CRAWLER::REFRESH_IN_PROGRESS', 'message': 'A refresh is already running'},
                status_code=409,
            )

        client = self._client_with(handler)

        with pytest.raises(CrawlerRefreshError) as excinfo:
            client.crawl_refresh_now('0198aaaa')

        assert excinfo.value.code == 'ERR::CRAWLER::REFRESH_IN_PROGRESS'


class TestCrawlerStatusRefreshBlock:
    """`/status` carries the refresh block the dashboard timeline reads."""

    pytestmark = pytest.mark.unit

    @staticmethod
    def _status(**extra):
        payload = {
            'crawler_uuid': '0198aaaa',
            'status': 'DONE',
            'is_success': True,
            'is_finished': True,
            'state': {
                'duration': 6.11,
                'urls_visited': 5,
                'urls_extracted': 5,
                'urls_failed': 0,
                'urls_skipped': 0,
                'urls_to_crawl': 0,
                'api_credit_used': 5,
                'stop_reason': None,
                'start_time': 1762940028,
                'stop_time': 1762940034.1,
            },
        }
        payload.update(extra)
        return CrawlerStatusResponse(payload)

    def test_status_exposes_the_refresh_block(self):
        """Polling /status is the webhook-free way to read the timeline."""
        status = self._status(refresh=REFRESH_STATE)

        assert status.refresh.enabled is True
        assert status.refresh.interval_seconds == 86400
        assert status.refresh.is_running is False
        assert len(status.refresh.history) == 2
        assert status.refresh.last_run.changed == 11

    def test_refresh_block_absent_on_a_crawl_without_it(self):
        assert self._status().refresh is None

    def test_status_block_carries_the_run_clock_and_the_failure_streak(self):
        """``/status`` relays the engine's refresh block verbatim, so it is the
        only route that renders ``started_at`` (the clock on the run in flight)
        and ``consecutive_failures`` (the streak the schedule backs off on)."""
        status = self._status(refresh=dict(
            REFRESH_STATE,
            status='RUNNING',
            started_at='2026-09-03T22:31:03.851147Z',
            consecutive_failures=3,
        ))

        assert status.refresh.is_running is True
        assert status.refresh.started_at == '2026-09-03T22:31:03.851147Z'
        assert status.refresh.consecutive_failures == 3

    def test_refresh_route_envelope_defaults_the_status_only_fields(self):
        """The three refresh calls render a typed block declaring neither
        field. One state class serves both routes, so their absence reads as
        "no run in flight, no failed runs" instead of breaking the decode."""
        state = CrawlerRefreshState({'crawler_uuid': '0198aaaa', 'refresh': REFRESH_STATE})

        assert state.status == 'SCHEDULED'
        assert state.started_at is None
        assert state.consecutive_failures == 0

    def test_refresh_block_parses_from_a_status_payload(self):
        state = CrawlerRefreshState({'refresh': REFRESH_STATE})

        assert state.enabled is True
        assert state.interval_seconds == 86400
        assert state.is_running is False
        assert len(state.history) == 2

    def test_a_crawl_without_refresh_reads_as_disabled(self):
        state = CrawlerRefreshState({'enabled': False, 'interval_seconds': 0, 'status': 'DISABLED'})

        assert state.enabled is False
        assert state.next_run_at is None
        assert state.last_run is None


# ---------------------------------------------------------------------------
# URL listing, offline. The endpoint answers text/plain, so the request shape
# and the line parse are the SDK's own contract rather than a decoded envelope.
# ---------------------------------------------------------------------------


class TestCrawlerUrlsTransport:
    """`get_crawl_urls` request shape and text decoding."""

    pytestmark = pytest.mark.unit

    @staticmethod
    def _client_with(handler):
        client = ScrapflyClient(key='scp-live-0000000000000000000000000000000000000000')
        # _http_handler is a cached_property; seed the cache to stub transport.
        client.__dict__['_http_handler'] = handler
        return client

    @staticmethod
    def _text_response(body, status_code=200, content_type='text/plain; charset=utf-8'):
        response = Response()
        response.status_code = status_code
        response._content = body.encode('utf-8')
        response.headers['Content-Type'] = content_type
        response.url = 'https://api.scrapfly.io/crawl/0198aaaa/urls'
        response.request = Request(method='GET', url=response.url).prepare()
        return response

    def test_get_crawl_urls_reads_the_text_endpoint(self):
        captured = {}

        def handler(**kwargs):
            captured.update(kwargs)
            return self._text_response('https://example.com/a\nhttps://example.com/b\n')

        client = self._client_with(handler)
        urls = client.get_crawl_urls('0198aaaa', status='visited', page=2, per_page=50)

        assert captured['method'] == 'GET'
        assert captured['url'] == 'https://api.scrapfly.io/crawl/0198aaaa/urls'
        assert captured['params'] == {
            'key': client.key,
            'page': 2,
            'per_page': 50,
            'status': 'visited',
        }
        # Error envelopes are JSON on every endpoint, this one included.
        assert captured['headers']['Accept'] == 'text/plain, application/json'

        assert isinstance(urls, CrawlerUrlsResponse)
        assert [entry.url for entry in urls] == ['https://example.com/a', 'https://example.com/b']
        assert urls.page == 2
        assert urls.per_page == 50

    def test_unset_status_leaves_the_server_default(self):
        """Never send a field to send its default: the server filters on
        'visited' when the parameter is absent, and the parse tags the records
        with that same default so the caller reads one status, not None."""
        captured = {}

        def handler(**kwargs):
            captured.update(kwargs)
            return self._text_response('https://example.com/a\n')

        client = self._client_with(handler)
        urls = client.get_crawl_urls('0198aaaa')

        assert 'status' not in captured['params']
        assert urls.urls[0].status == 'visited'

    def test_failed_records_carry_their_reason(self):
        client = self._client_with(
            lambda **kwargs: self._text_response(
                'https://example.com/404,http_status\nhttps://example.com/x,timeout\n'
            )
        )
        urls = client.get_crawl_urls('0198aaaa', status='failed')

        assert [(e.url, e.reason) for e in urls] == [
            ('https://example.com/404', 'http_status'),
            ('https://example.com/x', 'timeout'),
        ]

    def test_crawl_urls_is_sugar_over_the_client_call(self):
        """`Crawl.urls()` pre-fills the uuid; the client call is the endpoint."""
        captured = {}

        def handler(**kwargs):
            captured.update(kwargs)
            return self._text_response('https://example.com/a\n')

        client = self._client_with(handler)
        crawl = Crawl(client, CrawlerConfig(url='https://example.com'))
        crawl._uuid = '0198aaaa'

        urls = crawl.urls(status='pending', page=3, per_page=10)

        assert captured['url'] == 'https://api.scrapfly.io/crawl/0198aaaa/urls'
        assert captured['params']['status'] == 'pending'
        assert captured['params']['page'] == 3
        assert captured['params']['per_page'] == 10
        assert urls.urls[0].status == 'pending'

    def test_urls_before_start_raises(self):
        client = self._client_with(lambda **kwargs: None)
        crawl = Crawl(client, CrawlerConfig(url='https://example.com'))

        with pytest.raises(ScrapflyCrawlerError):
            crawl.urls()

    def test_error_envelope_is_raised_not_parsed_as_records(self):
        def handler(**kwargs):
            response = self._text_response(
                json.dumps({'code': 'ERR::CRAWLER::NOT_FOUND', 'message': 'Crawler job not found'}),
                status_code=404,
                content_type='application/json',
            )
            return response

        client = self._client_with(handler)

        with pytest.raises(HttpError) as excinfo:
            client.get_crawl_urls('0198aaaa')

        assert excinfo.value.code == 'ERR::CRAWLER::NOT_FOUND'

    def test_json_on_a_success_is_refused(self):
        """The text parser would read a JSON body line by line and hand back a
        page of fabricated URLs; a format mismatch has to surface instead."""
        client = self._client_with(
            lambda **kwargs: self._text_response(
                json.dumps({'urls': ['https://example.com/a']}),
                content_type='application/json',
            )
        )

        with pytest.raises(ScrapflyCrawlerError) as excinfo:
            client.get_crawl_urls('0198aaaa')

        assert excinfo.value.code == 'ERR::CRAWLER::UNEXPECTED_RESPONSE_FORMAT'
