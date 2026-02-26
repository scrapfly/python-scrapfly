"""
Concurrent Crawler Tests

Tests running multiple crawler jobs in parallel:
- Starting multiple crawls simultaneously
- Status checking across multiple crawls
- Concurrent result retrieval
- Race conditions and synchronization
"""
import pytest
import time
from scrapfly import Crawl, CrawlerConfig
from .conftest import assert_crawl_successful


@pytest.mark.integration
@pytest.mark.slow
class TestConcurrentCrawls:
    """Test running multiple crawler jobs in parallel"""

    def test_start_multiple_crawls_parallel(self, client, test_url):
        """Test starting 5 crawls simultaneously"""
        # Create 5 different crawler configs
        crawl_configs = [
            CrawlerConfig(url=test_url, page_limit=3),
            CrawlerConfig(url=test_url, page_limit=5),
            CrawlerConfig(url=test_url, page_limit=3, max_depth=1),
            CrawlerConfig(url='https://httpbin.dev/html', page_limit=1),
            CrawlerConfig(url=test_url, page_limit=3, exclude_paths=['/product.*']),
        ]

        # Start all crawls
        crawls = []
        start_time = time.time()

        for config in crawl_configs:
            crawl = Crawl(client, config).crawl()
            crawls.append(crawl)

        end_time = time.time()
        startup_time = end_time - start_time

        # Should start quickly (no waiting)
        assert startup_time < 10, f"Starting 5 crawls took {startup_time:.1f}s"

        # All should have UUIDs
        assert len(crawls) == 5
        for crawl in crawls:
            assert crawl.started
            assert crawl.uuid is not None

        # All UUIDs should be unique
        uuids = [c.uuid for c in crawls]
        assert len(set(uuids)) == 5, "All crawl UUIDs should be unique"

    def test_monitor_multiple_crawls_status(self, client, test_url):
        """Test polling status of multiple concurrent crawls"""
        # Start 3 crawls
        crawls = [
            Crawl(client, CrawlerConfig(url=test_url, page_limit=5)).crawl(),
            Crawl(client, CrawlerConfig(url=test_url, page_limit=3)).crawl(),
            Crawl(client, CrawlerConfig(url=test_url, page_limit=5, max_depth=1)).crawl(),
        ]

        # Monitor until all complete
        max_polls = 60
        poll_count = 0
        completed = set()

        while len(completed) < len(crawls) and poll_count < max_polls:
            for i, crawl in enumerate(crawls):
                if i in completed:
                    continue

                status = crawl.status()
                print(f"Crawl {i} ({crawl.uuid}): {status.status}, crawled {status.urls_crawled}")

                if status.is_complete:
                    completed.add(i)

            poll_count += 1
            if len(completed) < len(crawls):
                time.sleep(2)

        # All should complete
        assert len(completed) == len(crawls), "All crawls should complete"

        # Verify final status
        for crawl in crawls:
            status = assert_crawl_successful(crawl)
            assert status.urls_crawled > 0

    def test_wait_for_multiple_crawls_sequentially(self, client, test_url):
        """Test waiting for multiple crawls one by one"""
        # Start 3 crawls
        crawls = [
            Crawl(client, CrawlerConfig(url=test_url, page_limit=3)).crawl(),
            Crawl(client, CrawlerConfig(url=test_url, page_limit=3)).crawl(),
            Crawl(client, CrawlerConfig(url=test_url, page_limit=3)).crawl(),
        ]

        # Wait for each to complete
        for crawl in crawls:
            crawl.wait(verbose=False)
            status = assert_crawl_successful(crawl)
            assert status.urls_crawled > 0

    def test_retrieve_artifacts_from_multiple_crawls(self, client, test_url):
        """Test downloading artifacts from multiple completed crawls"""
        # Start and wait for 3 crawls
        crawls = [
            Crawl(client, CrawlerConfig(url=test_url, page_limit=3)).crawl().wait(verbose=False),
            Crawl(client, CrawlerConfig(url=test_url, page_limit=3)).crawl().wait(verbose=False),
            Crawl(client, CrawlerConfig(url=test_url, page_limit=3)).crawl().wait(verbose=False),
        ]

        # Download artifacts from all
        artifacts = []
        for crawl in crawls:
            assert_crawl_successful(crawl)
            artifact = crawl.warc()
            artifacts.append(artifact)

        # Verify all artifacts are valid
        assert len(artifacts) == 3
        for artifact in artifacts:
            assert artifact is not None
            assert len(artifact.warc_data) > 0
            pages = artifact.get_pages()
            assert len(pages) > 0

    def test_concurrent_same_url_crawls(self, client, test_url):
        """Test crawling the same URL with different configurations concurrently"""
        # Start 3 crawls of the same URL but different configs
        crawls = [
            Crawl(client, CrawlerConfig(url=test_url, page_limit=3)).crawl(),
            Crawl(client, CrawlerConfig(url=test_url, page_limit=5, max_depth=1)).crawl(),
            Crawl(client, CrawlerConfig(url=test_url, page_limit=3, cache=True)).crawl(),
        ]

        # Wait for all
        for crawl in crawls:
            crawl.wait(verbose=False)

        # All should complete successfully
        for crawl in crawls:
            status = assert_crawl_successful(crawl)
            assert status.urls_crawled > 0

        # Each should have different results based on config
        pages_counts = [len(c.warc().get_pages()) for c in crawls]
        # At least verify they all got some pages
        assert all(count > 0 for count in pages_counts)


class TestConcurrentEdgeCases:
    """Test edge cases with concurrent crawling"""

    def test_rapid_status_checks(self, client, test_url):
        """Test rapidly checking status doesn't cause issues"""
        crawl = Crawl(client, CrawlerConfig(url=test_url, page_limit=5)).crawl()

        # Check status 10 times rapidly
        statuses = []
        for i in range(10):
            status = crawl.status()
            statuses.append(status)
            time.sleep(0.1)  # 100ms between checks

        # Should not error and should get valid statuses
        assert len(statuses) == 10
        for status in statuses:
            assert status.uuid == crawl.uuid

    def test_mixed_crawl_and_scrape_operations(self, client, test_url):
        """Test running crawler and regular scrape operations concurrently"""
        from scrapfly import ScrapeConfig

        # Start a crawler
        crawl = Crawl(client, CrawlerConfig(url=test_url, page_limit=5)).crawl()

        # Do some scrape operations while crawler runs
        scrape_results = []
        for i in range(3):
            result = client.scrape(ScrapeConfig(url=f'{test_url}'))
            scrape_results.append(result)

        # Wait for crawler
        crawl.wait(verbose=False)

        # Both should succeed
        assert_crawl_successful(crawl)
        assert len(scrape_results) == 3
        for result in scrape_results:
            assert result.success

    def test_early_status_check_doesnt_break_crawl(self, client, test_url):
        """Test that checking status immediately after start doesn't break crawl"""
        crawl = Crawl(client, CrawlerConfig(url=test_url, page_limit=5)).crawl()

        # Check status immediately
        status1 = crawl.status()
        assert status1 is not None

        # Wait for completion
        crawl.wait(verbose=False)

        # Final status should be complete
        status2 = crawl.status()
        assert status2.is_complete


class TestConcurrentResourceManagement:
    """Test resource management with concurrent crawls"""

    def test_max_concurrent_crawls_limit(self, client, test_url):
        """Test starting many crawls (system should handle gracefully)"""
        # Start 10 crawls
        crawls = []
        for i in range(10):
            config = CrawlerConfig(url=test_url, page_limit=2)
            crawl = Crawl(client, config).crawl()
            crawls.append(crawl)

        # All should start successfully
        assert len(crawls) == 10
        assert all(c.started for c in crawls)

        # Don't wait for all - just verify they started
        # (Waiting for 10 would take too long)

        # Check first 3 complete successfully
        for i in range(3):
            crawls[i].wait(verbose=False)
            assert_crawl_successful(crawls[i])

    def test_crawl_status_after_completion(self, client, test_url):
        """Test that status remains accessible after crawl completes"""
        crawl = Crawl(client, CrawlerConfig(url=test_url, page_limit=3)).crawl().wait(verbose=False)

        status1 = assert_crawl_successful(crawl)

        # Check status again multiple times
        time.sleep(1)
        status2 = crawl.status()
        time.sleep(1)
        status3 = crawl.status()

        # All should show complete
        assert status1.is_complete
        assert status2.is_complete
        assert status3.is_complete

        # URLs crawled should be consistent
        assert status1.urls_crawled == status2.urls_crawled == status3.urls_crawled
