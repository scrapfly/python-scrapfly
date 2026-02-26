"""
Basic Crawler Workflow Tests

Tests fundamental crawler operations:
- Starting and stopping crawls
- Status monitoring and polling
- Method chaining
- Basic workflow validation
"""
import pytest
from scrapfly import Crawl, CrawlerConfig, ScrapflyCrawlerError
from .conftest import assert_crawl_successful


@pytest.mark.workflow
@pytest.mark.integration
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

        # Verify crawl succeeded
        status = assert_crawl_successful(crawl)
        assert status.urls_crawled > 0
        assert status.urls_discovered > 0

    def test_crawl_method_chaining(self, client, test_url):
        """Test that crawl methods support chaining"""
        config = CrawlerConfig(url=test_url, page_limit=3)

        # All methods should return self for chaining
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert crawl.started
        status = assert_crawl_successful(crawl)
        assert status.is_complete

    def test_cannot_start_twice(self, client, test_url):
        """Test that starting a crawl twice raises an error"""
        config = CrawlerConfig(url=test_url, page_limit=2)
        crawl = Crawl(client, config).crawl()

        # Try to start again - should raise error
        with pytest.raises(ScrapflyCrawlerError, match="already started"):
            crawl.crawl()

    def test_crawl_repr(self, client, test_url):
        """Test __repr__ output at different stages"""
        config = CrawlerConfig(url=test_url, page_limit=2)
        crawl = Crawl(client, config)

        # Before starting
        repr_before = repr(crawl)
        assert 'not started' in repr_before.lower()

        # After starting
        crawl.crawl().wait(verbose=False)
        repr_after = repr(crawl)
        assert crawl.uuid in repr_after
        assert 'not started' not in repr_after.lower()


class TestCrawlerStatus:
    """Test status monitoring and polling"""

    def test_status_polling(self, client, test_url):
        """Test status changes during crawl"""
        config = CrawlerConfig(url=test_url, page_limit=5)
        crawl = Crawl(client, config).crawl()

        # Poll status until complete
        max_polls = 30
        poll_count = 0
        while poll_count < max_polls:
            status = crawl.status()
            print(f"Poll {poll_count}: {status.status}, {status.urls_crawled}/{status.urls_discovered} URLs")

            if status.is_complete:
                break

            poll_count += 1
            import time
            time.sleep(2)

        # Verify crawl succeeded
        assert_crawl_successful(crawl)
        assert poll_count < max_polls, "Crawl took too long"

    def test_status_caching(self, client, test_url):
        """Test that status responses are cached appropriately"""
        config = CrawlerConfig(url=test_url, page_limit=3)
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        # Get status multiple times
        status1 = crawl.status()
        status2 = crawl.status()

        # Should have same values
        assert status1.status == status2.status
        assert status1.urls_crawled == status2.urls_crawled
        assert status1.urls_discovered == status2.urls_discovered


class TestCrawlerRepr:
    """Test string representations"""

    def test_not_started_repr(self, client, test_url):
        """Test repr before crawl starts"""
        config = CrawlerConfig(url=test_url, page_limit=2)
        crawl = Crawl(client, config)

        repr_str = repr(crawl)
        assert 'not started' in repr_str.lower()
        assert test_url in repr_str

    def test_completed_repr(self, client, test_url):
        """Test repr after crawl completes"""
        config = CrawlerConfig(url=test_url, page_limit=2)
        crawl = Crawl(client, config).crawl().wait(verbose=False)

        assert_crawl_successful(crawl)
        repr_str = repr(crawl)
        assert crawl.uuid in repr_str
        assert 'Not started' not in repr_str
