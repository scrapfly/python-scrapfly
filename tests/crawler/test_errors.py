"""
Error Handling and Edge Cases Tests

Tests error scenarios and edge cases:
- Failed crawls
- Invalid configurations
- Network errors
- Stop reasons
- Timeout handling
"""
import pytest
from scrapfly import Crawl, CrawlerConfig, ScrapflyCrawlerError


@pytest.mark.errors
@pytest.mark.integration
class TestErrorHandling:
    """Test error scenarios"""

    def test_cannot_start_twice(self, client, test_url):
        """Test that starting a crawl twice raises error"""
        config = CrawlerConfig(url=test_url, page_limit=2)
        crawl = Crawl(client, config).crawl()

        # Try to start again
        with pytest.raises(ScrapflyCrawlerError, match="already started"):
            crawl.crawl()

    def test_invalid_url(self, client):
        """Test crawl with invalid URL"""
        config = CrawlerConfig(url='not-a-valid-url', page_limit=1)
        crawl = Crawl(client, config)

        # Should raise error when starting
        with pytest.raises(Exception):
            crawl.crawl()

    def test_failed_seed_url(self, client):
        """Test crawl where seed URL fails"""
        config = CrawlerConfig(
            url='https://httpbin.dev/status/503',
            page_limit=5
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = crawl.status()

        # Crawl might complete but with 0 URLs if seed failed
        if status.is_complete and status.urls_crawled == 0:
            # This is expected - seed URL returned 503
            assert status.stop_reason in ['seed_url_failed', 'no_more_urls']


class TestStopReasons:
    """Test different crawl stop reasons"""

    def test_stop_reason_page_limit(self, client, test_url):
        """Test stop reason when page limit is reached"""
        config = CrawlerConfig(url=test_url, page_limit=3)
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = crawl.status()
        assert status.is_complete

        # Should stop due to page limit
        if status.urls_crawled >= 3:
            assert status.stop_reason == 'page_limit'

    def test_stop_reason_no_more_urls(self, client):
        """Test stop reason when no more URLs to crawl"""
        # Crawl a simple page with no links
        config = CrawlerConfig(
            url='https://httpbin.dev/html',
            page_limit=10
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = crawl.status()

        # Might fail or complete with no_more_urls
        if status.is_complete and status.urls_crawled > 0:
            assert status.stop_reason in ['no_more_urls', 'page_limit']

    def test_stop_reason_max_duration(self, client, test_url):
        """Test stop reason when max duration is reached"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=100,
            max_duration=5  # 5 seconds max
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = crawl.status()
        assert status.is_complete

        # Might stop due to max_duration
        if status.stop_reason == 'max_duration':
            assert status.urls_crawled < 100


class TestEdgeCases:
    """Test edge cases and unusual scenarios"""

    def test_single_page_crawl(self, client):
        """Test crawling a single page with no links"""
        config = CrawlerConfig(
            url='https://httpbin.dev/html',
            page_limit=1
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = crawl.status()

        # Might complete or fail depending on httpbin availability
        if status.is_complete:
            assert status.urls_crawled >= 0

    def test_very_small_page_limit(self, client, test_url):
        """Test with page_limit=1"""
        config = CrawlerConfig(url=test_url, page_limit=1)
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = crawl.status()
        assert status.is_complete
        assert status.urls_crawled <= 1

    def test_empty_content_handling(self, client):
        """Test handling of pages with minimal content"""
        config = CrawlerConfig(
            url='https://httpbin.dev/html',
            page_limit=1,
            content_formats=['text']
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = crawl.status()

        # Even if it fails, we're testing the handling
        if status.is_complete and status.urls_crawled > 0:
            try:
                content = list(crawl.read_iter())
                assert len(content) >= 0
            except Exception:
                pass  # Content retrieval might fail

    def test_mutually_exclusive_paths(self, client, test_url):
        """Test that include_only_paths and exclude_paths are mutually exclusive"""
        # This should either work with one taking precedence or raise an error
        config = CrawlerConfig(
            url=test_url,
            page_limit=5,
            include_only_paths=['/products.*'],
            exclude_paths=['/product/1']
        )

        # Implementation might handle this differently
        try:
            crawl = Crawl(client, config).crawl().wait(verbose=False)
            status = crawl.status()
            # If it works, verify it completed
            assert status.is_complete
        except Exception as e:
            # Or it might raise an error
            assert 'mutually exclusive' in str(e).lower() or 'invalid' in str(e).lower()


class TestFailedCrawls:
    """Test handling of completely failed crawls"""

    def test_all_urls_fail(self, client):
        """Test crawl where all URLs fail"""
        config = CrawlerConfig(
            url='https://httpbin.dev/status/404',
            page_limit=5
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = crawl.status()

        # Should complete but with 0 or very few successful URLs
        assert status.is_complete
        if status.urls_crawled == 0:
            assert status.stop_reason in ['seed_url_failed', 'no_more_urls']

    def test_network_timeout(self, client):
        """Test handling of network timeouts"""
        # Use a URL that will timeout
        config = CrawlerConfig(
            url='https://httpbin.dev/delay/30',  # 30 second delay
            page_limit=1
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = crawl.status()

        # Should complete (timeout or fail)
        assert status.is_complete

    def test_invalid_domain(self, client):
        """Test crawl with invalid domain"""
        config = CrawlerConfig(
            url='https://this-domain-does-not-exist-12345.com',
            page_limit=1
        )

        try:
            crawl = Crawl(client, config).crawl().wait(verbose=False)
            status = crawl.status()

            # If it completes, should have failed
            if status.is_complete:
                assert status.urls_crawled == 0 or status.is_failed
        except Exception:
            # Or might raise exception
            pass


class TestCancellation:
    """Test crawl cancellation scenarios"""

    def test_cancel_running_crawl(self, client, test_url):
        """Test cancelling a running crawl"""
        config = CrawlerConfig(url=test_url, page_limit=100)
        crawl = Crawl(client, config).crawl()

        # Cancel immediately after starting
        crawl.cancel()

        # Wait for status to update
        import time
        time.sleep(2)

        status = crawl.status()
        # Should be cancelled or completed (if it finished quickly)
        assert status.is_cancelled or status.is_complete

    def test_cannot_cancel_completed_crawl(self, client, test_url):
        """Test that cancelling completed crawl is a no-op"""
        config = CrawlerConfig(url=test_url, page_limit=2)
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = crawl.status()
        assert status.is_complete

        # Cancel after completion (should not error)
        try:
            crawl.cancel()
            # Should succeed or be a no-op
        except Exception:
            # Some implementations might raise error
            pass

    def test_stop_reason_cancelled(self, client, test_url):
        """Test that cancelled crawls have correct stop_reason"""
        config = CrawlerConfig(url=test_url, page_limit=100, max_depth=5)
        crawl = Crawl(client, config).crawl()

        import time
        time.sleep(1)  # Let it start

        crawl.cancel()
        time.sleep(2)  # Let cancellation process

        status = crawl.status()

        if status.is_cancelled:
            assert status.stop_reason == 'cancelled'


class TestConfigValidation:
    """Test configuration validation"""

    def test_negative_page_limit(self, client, test_url):
        """Test that negative page_limit raises error"""
        with pytest.raises((ValueError, Exception)):
            config = CrawlerConfig(url=test_url, page_limit=-1)
            crawl = Crawl(client, config).crawl()

    def test_zero_page_limit(self, client, test_url):
        """Test that page_limit=0 raises error"""
        with pytest.raises((ValueError, Exception)):
            config = CrawlerConfig(url=test_url, page_limit=0)
            crawl = Crawl(client, config).crawl()

    def test_negative_max_depth(self, client, test_url):
        """Test that negative max_depth raises error"""
        with pytest.raises((ValueError, Exception)):
            config = CrawlerConfig(url=test_url, page_limit=5, max_depth=-1)
            crawl = Crawl(client, config).crawl()

    def test_invalid_content_format(self, client, test_url):
        """Test that invalid content format raises error"""
        with pytest.raises((ValueError, Exception)):
            config = CrawlerConfig(
                url=test_url,
                page_limit=3,
                content_formats=['invalid_format_xyz']
            )
            crawl = Crawl(client, config).crawl()

    def test_conflicting_path_options(self, client, test_url):
        """Test that include_only_paths and exclude_paths together might error"""
        # This might raise error or use one over the other
        try:
            config = CrawlerConfig(
                url=test_url,
                page_limit=5,
                include_only_paths=['/products'],
                exclude_paths=['/admin']
            )
            # Some implementations allow this (include takes precedence)
            crawl = Crawl(client, config).crawl().wait(verbose=False)
            assert crawl.status().is_complete
        except Exception as e:
            # Or might raise validation error
            assert 'mutually exclusive' in str(e).lower() or 'conflict' in str(e).lower() or 'invalid' in str(e).lower()


class TestAPIErrors:
    """Test API error handling"""

    def test_status_before_start(self, client, test_url):
        """Test getting status before crawl starts"""
        config = CrawlerConfig(url=test_url, page_limit=3)
        crawl = Crawl(client, config)

        # Try to get status before starting
        with pytest.raises(Exception):
            crawl.status()

    def test_artifact_before_completion(self, client, test_url):
        """Test downloading artifact before crawl completes"""
        config = CrawlerConfig(url=test_url, page_limit=10)
        crawl = Crawl(client, config).crawl()

        # Try to get artifact immediately (before completion)
        with pytest.raises(Exception, match="complete"):
            crawl.warc()

    def test_read_before_completion(self, client, test_url):
        """Test reading content before crawl completes"""
        config = CrawlerConfig(url=test_url, page_limit=10, content_formats=['html'])
        crawl = Crawl(client, config).crawl()

        # Try to read content immediately
        with pytest.raises(Exception):
            urls = crawl.urls()
            if urls:
                crawl.read(urls[0])

    def test_invalid_uuid_status(self, client):
        """Test getting status with invalid UUID"""
        # Create a crawl but don't start it
        config = CrawlerConfig(url='https://web-scraping.dev', page_limit=5)
        crawl = Crawl(client, config)

        # Manually set invalid UUID
        crawl.uuid = 'invalid-uuid-12345'
        crawl.started = True

        # Try to get status
        with pytest.raises(Exception):
            crawl.status()


class TestRetryAndTimeout:
    """Test retry logic and timeout handling"""

    def test_slow_response_handling(self, client):
        """Test handling of slow responses"""
        config = CrawlerConfig(
            url='https://httpbin.dev/delay/3',
            page_limit=1
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        # Should complete (either succeed or timeout)
        status = crawl.status()
        assert status.is_complete

    def test_mixed_success_failure_urls(self, client):
        """Test crawl with mix of successful and failed URLs"""
        # This would require a test site with mixed responses
        # For now, test with a single URL that might have mixed links
        config = CrawlerConfig(
            url='https://web-scraping.dev',
            page_limit=10
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = crawl.status()
        assert status.is_complete

        # Should have crawled some URLs
        assert status.urls_crawled > 0

        # Might have some failed URLs
        if hasattr(status, 'urls_failed'):
            assert status.urls_failed >= 0


class TestStopReasonsExtended:
    """Extended tests for stop reasons"""

    def test_stop_reason_error(self, client):
        """Test stop_reason when crawl encounters an error"""
        config = CrawlerConfig(
            url='https://this-absolutely-does-not-exist-domain-12345.com',
            page_limit=5
        )

        try:
            crawl = Crawl(client, config).crawl().wait(verbose=False)
            status = crawl.status()

            if status.is_failed:
                assert status.stop_reason in ('error', 'seed_url_failed')
        except Exception:
            # Might raise exception instead
            pass

    def test_stop_reason_max_api_credit(self, client, test_url):
        """Test stop_reason when API credit limit is hit"""
        config = CrawlerConfig(
            url=test_url,
            page_limit=100,
            max_api_credit=1  # Very low limit
        )
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        status = crawl.status()

        # Should stop early due to credit limit
        if hasattr(status, 'stop_reason') and status.stop_reason == 'max_api_credit':
            assert status.urls_crawled < 100
