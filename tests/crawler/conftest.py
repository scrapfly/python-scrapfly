"""
Shared pytest fixtures for crawler tests
"""
import os
import pytest
from pathlib import Path
from scrapfly import ScrapflyClient
from dotenv import load_dotenv

# Load .env file if it exists
env_path = Path(__file__).resolve().parents[2] / '.env'
if env_path.exists():
    load_dotenv(dotenv_path=env_path, override=False)

# Test configuration
API_KEY = os.environ.get('SCRAPFLY_KEY')
API_HOST = os.environ.get('SCRAPFLY_API_HOST')

assert API_KEY is not None, "SCRAPFLY_KEY environment variable is not set"
assert API_HOST is not None, "SCRAPFLY_API_HOST environment variable is not set"

@pytest.fixture(scope="function")
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


@pytest.fixture
def httpbin_url():
    """HTTPBin URL for HTTP-specific testing"""
    return 'https://httpbin.dev'


def assert_crawl_successful(crawl):
    """
    Helper to verify a crawl completed successfully.

    Checks that:
    - Crawl is complete
    - Crawl did not fail
    - At least one URL was crawled

    Returns the status for further assertions.
    """
    status = crawl.status()
    assert status.is_complete, f"Crawl {crawl.uuid} should be complete but status is: {status.status}"
    assert not status.is_failed, f"Crawl {crawl.uuid} failed with status: {status.status}"
    assert status.urls_crawled > 0, f"Crawl {crawl.uuid} should have crawled at least one URL"
    return status


def parse_httpbin_headers(content: str) -> dict:
    """
    Parse plain text HTTP headers from httpbin /dump/request endpoint.

    Args:
        content: Plain text HTTP request dump from httpbin

    Returns:
        Dictionary of header names to values

    Example:
        >>> headers = parse_httpbin_headers(crawl_content.content)
        >>> assert headers['User-Agent'] == 'Test-Crawler'
        >>> assert headers['X-Custom-Header'] == 'custom-value'
    """
    headers = {}
    for line in content.split('\n'):
        # Skip request line and empty lines
        if ':' not in line:
            continue
        # Parse "Header-Name: value" format
        key, value = line.split(':', 1)
        headers[key.strip()] = value.strip()
    return headers
