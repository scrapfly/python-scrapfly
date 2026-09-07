# Scrapfly Python SDK Tests

Two kinds of test live here, and the difference matters.

## `e2e` — end-to-end against the live product

Marked `e2e` (and `integration`). These drive a real Scrapfly environment: real
crawls, real scrapes, real proxies. This is deliberate — the SDK is the supported
client, so exercising the platform through it is what customers actually
experience. Server-side product changes are expected to show up here.

```bash
SCRAPFLY_KEY=scp-live-... pytest -m e2e
```

`SCRAPFLY_API_HOST` overrides the endpoint if you need to point the suite at a
non-default stack; it defaults to the public API.

Without `SCRAPFLY_KEY` they skip (`tests/conftest.py`), so a green run with no
credentials proves nothing about the platform.

They also need real **quota** and **crawler capacity** on the target environment:
a quota-exhausted account fails every crawl at its seed URL
(`ERR::SCRAPE::QUOTA_LIMIT_REACHED`), and a saturated crawler backend returns 503
`no capacity available` from the gateway. Neither is an SDK regression.

## Everything else — offline

No credentials, no network, instant. This is where SDK-owned behaviour belongs:
request building, response parsing, error mapping, signature verification.

```bash
pytest -m "not e2e"
```

## When an e2e test turns red

Confirm the **current behaviour is correct** before touching the expectation. A
test updated to match a bug is worse than a failing one. Two real examples from
this suite: the API began rejecting `session_sticky_proxy=false` with `asp=true`
(a deliberate 400, not a regression), and `extraction_template` is sent as
`persistent:<slug>` (a bare slug is only a legacy fallback).

---

This directory also contains tests for the Scrapfly Crawler API functionality.

## Test Structure

### `test_crawler.py`
Comprehensive test suite for the Crawler API covering:

- **Basic Workflow**: Start, monitor, and retrieve crawl results
- **Status Monitoring**: Polling, caching, and status checking
- **WARC Artifacts**: Download, parse, iterate through records
- **HAR Artifacts**: Download, parse HAR format with timing info
- **Content Formats**: HTML, markdown, text, JSON, extracted data
- **Content Retrieval**: `read()`, `read_iter()`, `read_batch()`
- **Configuration**: Page limits, depth, path filtering
- **Statistics**: Crawl stats and metrics
- **Error Handling**: Edge cases and error scenarios
- **Async Methods**: Async crawler operations
- **Web-scraping.dev Tests**: Tests using the web-scraping.dev test site

## Running Tests

### Prerequisites

Install test dependencies:
```bash
pip install pytest pytest-asyncio
```

Set environment variables (optional):
```bash
export SCRAPFLY_KEY="your-api-key"
export SCRAPFLY_API_HOST="https://api.scrapfly.io"
```

### Run All Tests

```bash
# Run all crawler tests
pytest tests/test_crawler.py -v

# Run with output
pytest tests/test_crawler.py -v -s

# Run specific test class
pytest tests/test_crawler.py::TestCrawlerBasicWorkflow -v

# Run specific test
pytest tests/test_crawler.py::TestCrawlerBasicWorkflow::test_basic_crawl_workflow -v
```

### Run by Category

```bash
# Basic workflow tests
pytest tests/test_crawler.py::TestCrawlerBasicWorkflow -v

# WARC tests
pytest tests/test_crawler.py::TestCrawlerWARC -v

# HAR tests
pytest tests/test_crawler.py::TestCrawlerHAR -v

# Content format tests
pytest tests/test_crawler.py::TestContentFormats -v

# Async tests
pytest tests/test_crawler.py::TestAsyncCrawler -v

# Error handling tests
pytest tests/test_crawler.py::TestErrorHandling -v
```

### Run with Coverage

```bash
pip install pytest-cov
pytest tests/test_crawler.py --cov=scrapfly --cov-report=html
```

## Test Sites

The tests use the following test sites:

1. **https://web-scraping.dev** - Primary test site designed for web scraping practice
   - `/products` - Product listing with pagination
   - `/product/{id}` - Product detail pages
   - Ideal for testing crawling, pagination, path filtering
   - Specifically created for testing web scraping tools

2. **https://httpbin.dev** - HTTP testing service
   - `/status/{code}` - Returns specific HTTP status codes
   - Used for testing error handling (404, 503, etc.)
   - Homepage has docs about available endpoints

## Test Coverage

The test suite covers:

- ✅ Starting and stopping crawls
- ✅ Status monitoring and polling
- ✅ WARC artifact parsing
- ✅ HAR artifact parsing with timing data
- ✅ Multiple content formats (HTML, markdown, text, JSON)
- ✅ Content retrieval methods (read, read_iter, read_batch)
- ✅ Path filtering (exclude_paths, include_only_paths)
- ✅ Page limits and depth limits
- ✅ Pattern matching for URL filtering
- ✅ Batch content retrieval (up to 100 URLs)
- ✅ Error handling and edge cases
- ✅ Async operations
- ✅ Crawler statistics
- ✅ Failed crawls (503 errors, etc.)
- ✅ Method chaining
- ✅ Caching behavior

## Writing New Tests

When adding new tests:

1. Use the `client` fixture for ScrapflyClient instances
2. Use the `test_url` fixture for the default test URL
3. Keep tests focused and independent
4. Use descriptive test names
5. Add docstrings to explain what's being tested
6. Clean up any resources (though crawls are stateless)

Example:
```python
def test_new_feature(self, client, test_url):
    """Test the new feature XYZ"""
    config = CrawlerConfig(url=test_url, page_limit=3)
    crawl = Crawl(client, config).crawl().wait()

    # Test assertions
    assert crawl.started
    assert crawl.uuid is not None
```

## Troubleshooting

### Tests are slow
- Reduce `page_limit` in test configs
- Use smaller test sites
- Run specific test classes instead of all tests

### Tests failing with API errors
- Check that `SCRAPFLY_KEY` environment variable is set
- Verify `SCRAPFLY_API_HOST` is correct
- Ensure API is accessible from your network

### Async tests not running
- Install `pytest-asyncio`: `pip install pytest-asyncio`
- Tests marked with `@pytest.mark.asyncio` require this plugin

## CI/CD Integration

To run tests in CI/CD pipelines:

```yaml
# Example GitHub Actions
- name: Run Crawler Tests
  env:
    SCRAPFLY_KEY: ${{ secrets.SCRAPFLY_KEY }}
    SCRAPFLY_API_HOST: ${{ secrets.SCRAPFLY_API_HOST }}
  run: |
    pip install pytest pytest-asyncio
    pytest tests/test_crawler.py -v
```
