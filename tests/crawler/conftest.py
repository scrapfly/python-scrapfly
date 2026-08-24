"""
Shared pytest fixtures for crawler tests
"""
import os
import pytest
from pathlib import Path
from scrapfly import ScrapflyClient

# python-dotenv is a convenience for local runs, not a requirement.
try:
    from dotenv import load_dotenv

    env_path = Path(__file__).resolve().parents[2] / '.env'
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
except ImportError:
    pass

# Test configuration
API_KEY = os.environ.get('SCRAPFLY_KEY')
API_HOST = os.environ.get('SCRAPFLY_API_HOST')

# These suites drive the live Scrapfly product end-to-end through the SDK.
# Skip rather than fail collection: an absent environment is not a failing SDK.
if not API_KEY or not API_HOST:
    pytest.skip(
        'live API test: set SCRAPFLY_KEY and SCRAPFLY_API_HOST to run',
        allow_module_level=True,
    )

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
    assert status.state.urls_visited > 0, f"Crawl {crawl.uuid} should have crawled at least one URL"
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


def pytest_collection_modifyitems(items):
    """
    Everything under tests/crawler/ is end-to-end against the live product.

    Collection hooks receive the whole session's items regardless of which
    conftest defines them, so this filters by path rather than marking
    everything.
    """
    here = Path(__file__).parent

    for item in items:
        if here in Path(str(item.fspath)).parents:
            item.add_marker(pytest.mark.integration)
            item.add_marker(pytest.mark.e2e)
