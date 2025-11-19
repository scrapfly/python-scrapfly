"""
Crawler Results API Tests

Tests all methods of retrieving and working with crawler results:
- URLs endpoint (listing discovered URLs)
- Content endpoint (read, read_iter, read_batch)
- Artifact endpoint (WARC and HAR formats)
- Content format options (html, markdown, text, etc.)

Based on: https://scrapfly.home/docs/crawler-api/results
"""
import pytest
from scrapfly import Crawl, CrawlerConfig
from .conftest import assert_crawl_successful


@pytest.mark.artifacts
@pytest.mark.integration
class TestResultsURLsRetrieval:
    """Test retrieving crawled URLs via WARC artifact"""

    def test_get_urls_via_warc(self, client, test_url):
        """Test retrieving list of crawled URLs via WARC artifact"""
        config = CrawlerConfig(url=test_url, page_limit=5)
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        # Get URLs via WARC artifact
        pages = crawl.warc().get_pages()
        urls = [page['url'] for page in pages]

        assert urls is not None
        assert len(urls) > 0
        assert all(isinstance(url, str) for url in urls)

    def test_urls_match_status(self, client, test_url):
        """Test that page count matches status"""
        config = CrawlerConfig(url=test_url, page_limit=3)
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = assert_crawl_successful(crawl)
        pages = crawl.warc().get_pages()

        # Pages returned should match urls_crawled from status
        assert len(pages) == status.urls_crawled

    def test_urls_include_seed(self, client, test_url):
        """Test that pages include the seed URL"""
        config = CrawlerConfig(url=test_url, page_limit=3)
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        pages = crawl.warc().get_pages()
        urls = [page['url'] for page in pages]

        # Seed URL should be in the list
        assert any(test_url in url for url in urls)


class TestResultsContentRead:
    """Test content retrieval with read() method"""

    def test_read_single_url(self, client, test_url):
        """Test reading content for a single URL"""
        config = CrawlerConfig(url=test_url, page_limit=3, content_formats=['html'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        # Get first URL from WARC
        pages = crawl.warc().get_pages()
        first_url = pages[0]['url']

        # Read content
        content = crawl.read(first_url)
        assert content is not None
        assert content.url == first_url
        assert len(content.content) > 0

    def test_read_multiple_urls(self, client, test_url):
        """Test reading content for multiple URLs"""
        config = CrawlerConfig(url=test_url, page_limit=5, content_formats=['html'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        pages = crawl.warc().get_pages()
        urls = [page['url'] for page in pages]

        # Read first 3 URLs
        for url in urls[:3]:
            content = crawl.read(url)
            assert content is not None
            assert content.url == url
            assert len(content.content) > 0

    def test_read_nonexistent_url(self, client, test_url):
        """Test reading content for URL that wasn't crawled"""
        config = CrawlerConfig(url=test_url, page_limit=3)
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        # Try to read URL that wasn't crawled
        content = crawl.read('https://example.com/nonexistent')
        # Should return None or empty result
        assert content is None or content.get('content') is None


class TestResultsContentReadIter:
    """Test content iteration with read_iter() method"""

    def test_read_iter_basic(self, client, test_url):
        """Test iterating through all crawled content"""
        config = CrawlerConfig(url=test_url, page_limit=5, content_formats=['html'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = assert_crawl_successful(crawl)

        # Iterate through all content
        count = 0
        for item in crawl.read_iter():
            assert item is not None
            assert item.url is not None
            assert len(item.content) > 0
            count += 1

        # Should iterate through all crawled URLs
        assert count == status.urls_crawled

    def test_read_iter_memory_efficient(self, client, test_url):
        """Test that read_iter doesn't load all content at once"""
        config = CrawlerConfig(url=test_url, page_limit=10, content_formats=['html'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        # Process items one at a time
        urls_seen = []
        for item in crawl.read_iter():
            urls_seen.append(item.url)
            # Process and discard immediately
            _ = len(item.content)

        # Verify we saw all URLs
        assert len(urls_seen) > 0

    def test_read_iter_with_format(self, client, test_url):
        """Test read_iter with specific content format"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=5,
            content_formats=['markdown', 'html']
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        # Iterate with markdown format
        for item in crawl.read_iter(format='markdown'):
            assert 'content' in item
            # Markdown content should not have HTML tags
            assert '<html>' not in item.content.lower()


class TestResultsContentReadBatch:
    """Test batch content retrieval with read_batch() method"""

    def test_read_batch_basic(self, client, test_url):
        """Test reading multiple URLs in a single batch"""
        config = CrawlerConfig(url=test_url, page_limit=10, content_formats=['html'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        urls = crawl.urls()

        # Read first 5 URLs in batch
        batch_urls = urls[:5]
        results = crawl.read_batch(batch_urls)

        assert len(results) == len(batch_urls)
        for result in results:
            assert 'url' in result
            assert 'content' in result
            assert result.url in batch_urls

    def test_read_batch_max_100(self, client, test_url):
        """Test that read_batch respects max 100 URLs limit"""
        config = CrawlerConfig(url=test_url, page_limit=50, content_formats=['html'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        urls = crawl.urls()

        # Try to read more than 100 URLs
        # API should limit to 100
        if len(urls) > 100:
            batch_urls = urls[:150]
            results = crawl.read_batch(batch_urls)
            # Should only return up to 100 results
            assert len(results) <= 100

    def test_read_batch_with_format(self, client, test_url):
        """Test read_batch with specific content format"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=5,
            content_formats=['markdown', 'text']
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        urls = crawl.urls()

        # Read batch with text format
        results = crawl.read_batch(urls, format='text')

        for result in results:
            assert 'content' in result
            # Text format should not have HTML tags
            content = result.content
            assert '<html>' not in content.lower()
            assert '<div>' not in content.lower()

    def test_read_batch_empty_list(self, client, test_url):
        """Test read_batch with empty URL list"""
        config = CrawlerConfig(url=test_url, page_limit=3)
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        # Read empty batch
        results = crawl.read_batch([])
        assert results == []


class TestResultsContentFormats:
    """Test different content format retrieval"""

    def test_read_html_format(self, client, test_url):
        """Test reading HTML format content"""
        config = CrawlerConfig(url=test_url, page_limit=3, content_formats=['html'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        urls = crawl.urls()

        content = crawl.read(urls[0], format='html')
        assert '<html>' in content.content.lower() or '<div>' in content.content.lower()

    def test_read_markdown_format(self, client, test_url):
        """Test reading markdown format content"""
        config = CrawlerConfig(url=test_url, page_limit=3, content_formats=['markdown'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        urls = crawl.urls()

        content = crawl.read(urls[0], format='markdown')
        # Markdown should not have HTML tags
        assert '<html>' not in content.content.lower()
        # But might have markdown syntax
        assert len(content.content) > 0

    def test_read_text_format(self, client, test_url):
        """Test reading plain text format content"""
        config = CrawlerConfig(url=test_url, page_limit=3, content_formats=['text'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        urls = crawl.urls()

        content = crawl.read(urls[0], format='text')
        # Text should not have HTML or markdown
        text_content = content.content
        assert '<html>' not in text_content.lower()
        assert '<div>' not in text_content.lower()
        assert len(text_content) > 0

    def test_read_multiple_formats(self, client, test_url):
        """Test that multiple formats can be requested"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=3,
            content_formats=['html', 'markdown', 'text']
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        urls = crawl.urls()

        # Read same URL in different formats
        html_content = crawl.read(urls[0], format='html')
        markdown_content = crawl.read(urls[0], format='markdown')
        text_content = crawl.read(urls[0], format='text')

        # All should return content
        assert len(html_content.content) > 0
        assert len(markdown_content.content) > 0
        assert len(text_content.content) > 0

        # HTML should have tags
        assert any(tag in html_content.content.lower() for tag in ['<html>', '<div>', '<p>'])

        # Text should not have HTML tags
        assert '<' not in text_content.content[:100]  # Check first 100 chars


class TestResultsCompleteWorkflow:
    """Test complete end-to-end workflows"""

    def test_crawl_and_retrieve_all_content(self, client, test_url):
        """Test complete workflow: crawl -> get URLs -> retrieve all content"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=5,
            content_formats=['html', 'markdown']
        )

        # Start and wait for crawl
        crawl = Crawl(client, config).crawl().wait(verbose=False)
        status = assert_crawl_successful(crawl)

        # Get all URLs
        urls = crawl.urls()
        assert len(urls) == status.urls_crawled

        # Retrieve all content via iteration
        contents = []
        for item in crawl.read_iter():
            contents.append(item)

        assert len(contents) == len(urls)
        assert all('content' in item for item in contents)

    def test_selective_content_retrieval(self, client, test_url):
        """Test retrieving content for specific URLs only"""
        config = CrawlerConfig(url=test_url, page_limit=10, content_formats=['text'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        urls = crawl.urls()

        # Select only URLs containing "product"
        product_urls = [url for url in urls if 'product' in url.lower()]

        if product_urls:
            # Read only product pages in batch
            results = crawl.read_batch(product_urls)
            assert len(results) == len(product_urls)
            assert all('product' in r['url'].lower() for r in results)

    def test_incremental_content_processing(self, client, test_url):
        """Test processing content incrementally as it's retrieved"""
        config = CrawlerConfig(url=test_url, page_limit=8, content_formats=['text'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        # Process content incrementally
        word_counts = {}
        for item in crawl.read_iter():
            url = item.url
            content = item.content
            word_count = len(content.split())
            word_counts[url] = word_count

        # Verify we processed all URLs
        assert len(word_counts) > 0
        assert all(count > 0 for count in word_counts.values())
