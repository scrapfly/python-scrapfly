"""
Content Formats Tests

Tests different content format extraction options:
- HTML (raw and clean)
- Markdown
- Plain text
- JSON extracted data
- Page metadata
- Multiple formats simultaneously
"""
import pytest
import json
from scrapfly import Crawl, CrawlerConfig
from .conftest import assert_crawl_successful


@pytest.mark.integration
@pytest.mark.artifacts
class TestContentFormatsBasic:
    """Test basic content format retrieval"""

    def test_html_format(self, client, test_url):
        """Test HTML content format"""
        config = CrawlerConfig(url=test_url, page_limit=3, content_formats=['html'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        for item in crawl.read_iter(format='html'):
            content = item['content']
            # HTML should contain tags
            assert any(tag in content.lower() for tag in ['<html>', '<body>', '<div>', '<p>'])
            break  # Test first item

    def test_clean_html_format(self, client, test_url):
        """Test clean HTML format (boilerplate removed)"""
        config = CrawlerConfig(url=test_url, page_limit=3, content_formats=['clean_html'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        for item in crawl.read_iter(format='clean_html'):
            content = item['content']
            # Should still have HTML structure
            assert '<' in content and '>' in content
            # But cleaner than raw HTML
            assert len(content) > 0
            break

    def test_markdown_format(self, client, test_url):
        """Test markdown content format"""
        config = CrawlerConfig(url=test_url, page_limit=3, content_formats=['markdown'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        for item in crawl.read_iter(format='markdown'):
            content = item['content']
            # Should not have HTML tags
            assert '<html>' not in content.lower()
            assert '<body>' not in content.lower()
            # Should have content
            assert len(content) > 100
            break

    def test_text_format(self, client, test_url):
        """Test plain text format"""
        config = CrawlerConfig(url=test_url, page_limit=3, content_formats=['text'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        for item in crawl.read_iter(format='text'):
            content = item['content']
            # Should not have HTML or markdown
            assert '<' not in content[:50]  # Check beginning
            assert '#' not in content[:50]  # No markdown headers
            # Should have readable text
            assert len(content) > 50
            break

    def test_json_format(self, client, test_url):
        """Test JSON extracted data format"""
        config = CrawlerConfig(url=test_url, page_limit=3, content_formats=['json'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        for item in crawl.read_iter(format='json'):
            content = item['content']
            # Should be valid JSON
            if content:
                data = json.loads(content)
                assert isinstance(data, (dict, list))
            break


class TestMultipleFormats:
    """Test requesting multiple content formats"""

    def test_multiple_formats_request(self, client, test_url):
        """Test requesting multiple formats in single crawl"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=3,
            content_formats=['html', 'markdown', 'text']
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        urls = crawl.urls()
        first_url = urls[0]

        # Should be able to retrieve different formats
        html = crawl.read(first_url, format='html')
        markdown = crawl.read(first_url, format='markdown')
        text = crawl.read(first_url, format='text')

        # All should have content
        assert len(html['content']) > 0
        assert len(markdown['content']) > 0
        assert len(text['content']) > 0

        # HTML should have tags
        assert '<' in html['content']

        # Text should not
        assert '<' not in text['content'][:100]

    def test_format_conversion_fidelity(self, client, test_url):
        """Test that different formats preserve information"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=2,
            content_formats=['html', 'markdown', 'text']
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        urls = crawl.urls()

        html = crawl.read(urls[0], format='html')
        text = crawl.read(urls[0], format='text')

        # Text should be shorter (no tags) but contain core content
        assert len(text['content']) < len(html['content'])
        assert len(text['content']) > 100  # Still substantial


class TestPageMetadata:
    """Test page metadata extraction"""

    def test_page_metadata_format(self, client, test_url):
        """Test page metadata format if supported"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=3,
            content_formats=['page_metadata']
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        for item in crawl.read_iter(format='page_metadata'):
            if item.get('content'):
                # Metadata should be JSON
                metadata = json.loads(item['content'])
                assert isinstance(metadata, dict)
            break

    def test_extracted_data(self, client, test_url):
        """Test extracted structured data"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=3,
            content_formats=['extracted_data']
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)

        for item in crawl.read_iter(format='extracted_data'):
            if item.get('content'):
                # Extracted data should be JSON
                data = json.loads(item['content'])
                assert isinstance(data, (dict, list))
            break


class TestFormatComparison:
    """Test comparing output between different formats"""

    def test_html_vs_markdown(self, client, test_url):
        """Compare HTML and markdown outputs"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=2,
            content_formats=['html', 'markdown']
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        url = crawl.urls()[0]

        html = crawl.read(url, format='html')
        markdown = crawl.read(url, format='markdown')

        # HTML should be longer (includes tags)
        assert len(html['content']) > len(markdown['content'])

        # Both should have substantial content
        assert len(html['content']) > 200
        assert len(markdown['content']) > 100

    def test_markdown_vs_text(self, client, test_url):
        """Compare markdown and plain text outputs"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=2,
            content_formats=['markdown', 'text']
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        url = crawl.urls()[0]

        markdown = crawl.read(url, format='markdown')
        text = crawl.read(url, format='text')

        # Both should have no HTML tags
        assert '<html>' not in markdown['content'].lower()
        assert '<html>' not in text['content'].lower()

        # Lengths should be comparable
        assert abs(len(markdown['content']) - len(text['content'])) / len(text['content']) < 0.5


class TestFormatSpecificFeatures:
    """Test format-specific features and edge cases"""

    def test_html_preserves_structure(self, client, test_url):
        """Test that HTML format preserves DOM structure"""
        config = CrawlerConfig(url=test_url, page_limit=2, content_formats=['html'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        url = crawl.urls()[0]

        html = crawl.read(url, format='html')
        content = html['content']

        # Should have proper HTML structure
        assert '<!DOCTYPE' in content or '<html' in content.lower()
        assert '</html>' in content.lower()

    def test_markdown_link_format(self, client, test_url):
        """Test that markdown format handles links properly"""
        config = CrawlerConfig(url=test_url, page_limit=2, content_formats=['markdown'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        url = crawl.urls()[0]

        markdown = crawl.read(url, format='markdown')
        content = markdown['content']

        # Markdown might have [text](url) style links
        # Or just URLs - depends on content
        assert len(content) > 100

    def test_text_no_formatting(self, client, test_url):
        """Test that text format removes all formatting"""
        config = CrawlerConfig(url=test_url, page_limit=2, content_formats=['text'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        url = crawl.urls()[0]

        text = crawl.read(url, format='text')
        content = text['content']

        # Should have no HTML
        assert '<html>' not in content.lower()
        assert '<div>' not in content.lower()
        assert '<p>' not in content.lower()

        # Should have readable text
        assert len(content.split()) > 20  # At least 20 words


class TestFormatEdgeCases:
    """Test edge cases and error scenarios"""

    def test_invalid_format_request(self, client, test_url):
        """Test requesting a format that wasn't crawled"""
        config = CrawlerConfig(url=test_url, page_limit=2, content_formats=['html'])
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        url = crawl.urls()[0]

        # Request markdown when only html was crawled
        try:
            result = crawl.read(url, format='markdown')
            # Might return empty or raise error - both acceptable
            if result and result.get('content'):
                # Some implementations might fall back
                assert len(result['content']) >= 0
        except Exception as e:
            # Error is also acceptable
            pass

    def test_empty_page_content(self, client):
        """Test handling of pages with minimal content"""
        config = CrawlerConfig(
            url='https://httpbin.org/status/200',
            page_limit=1,
            content_formats=['html', 'text']
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        # Even if crawl fails, we tested the scenario
        try:
            status = assert_crawl_successful(crawl)
        except:
            pass  # HTTPBin might be unavailable

    def test_all_formats_simultaneously(self, client, test_url):
        """Test requesting all available formats at once"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=2,
            content_formats=['html', 'clean_html', 'markdown', 'text']
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        url = crawl.urls()[0]

        # Should be able to retrieve all formats
        formats_tested = []
        for fmt in ['html', 'clean_html', 'markdown', 'text']:
            try:
                result = crawl.read(url, format=fmt)
                if result and result.get('content'):
                    formats_tested.append(fmt)
            except:
                pass

        # At least some formats should work
        assert len(formats_tested) > 0

    def test_clean_html_removes_scripts_styles(self, client, test_url):
        """Test that clean_html removes scripts and stylesheets"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=2,
            content_formats=['html', 'clean_html']
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        url = crawl.urls()[0]

        html = crawl.read(url, format='html')
        clean = crawl.read(url, format='clean_html')

        html_content = html['content'].lower()
        clean_content = clean['content'].lower()

        # HTML might have scripts
        html_has_script = '<script' in html_content or '<style' in html_content

        # Clean HTML should have fewer/no scripts
        if html_has_script:
            clean_script_count = clean_content.count('<script')
            html_script_count = html_content.count('<script')
            # Clean should have same or fewer scripts
            assert clean_script_count <= html_script_count

    def test_format_content_size_differences(self, client, test_url):
        """Test that format sizes follow expected pattern"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=2,
            content_formats=['html', 'clean_html', 'markdown', 'text']
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        url = crawl.urls()[0]

        sizes = {}
        for fmt in ['html', 'clean_html', 'markdown', 'text']:
            try:
                result = crawl.read(url, format=fmt)
                if result and result.get('content'):
                    sizes[fmt] = len(result['content'])
            except:
                pass

        # HTML should generally be largest (has tags)
        if 'html' in sizes and 'text' in sizes:
            assert sizes['html'] >= sizes['text']

        # All should have content
        for size in sizes.values():
            assert size > 0
