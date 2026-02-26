# Crawler API Tests

This directory contains pytest tests for the Scrapfly Crawler API SDK.

## Test Structure

### Pytest Test Files (8 files)

All test files follow pytest conventions with proper test classes and functions:

- **test_artifacts.py** - WARC/HAR artifact download and parsing tests
- **test_async.py** - Asynchronous crawler operation tests  
- **test_basic_workflow.py** - Basic crawler workflow tests
- **test_concurrent.py** - Concurrent crawler tests
- **test_configuration.py** - CrawlerConfig parameter tests
- **test_content_formats.py** - Content format extraction tests (HTML, markdown, etc.)
- **test_errors.py** - Error handling and edge case tests
- **test_results.py** - Result processing and validation tests

### Pytest Markers

Tests are organized with markers for selective test running:

- `@pytest.mark.unit` - Unit tests (no API calls required)
- `@pytest.mark.integration` - Integration tests (requires API access)
- `@pytest.mark.slow` - Tests that take longer to complete
- `@pytest.mark.artifacts` - Tests for artifact parsing (WARC/HAR)
- `@pytest.mark.async` - Async functionality tests
- `@pytest.mark.config` - Configuration tests
- `@pytest.mark.workflow` - Workflow tests
- `@pytest.mark.errors` - Error handling tests

## Running Tests

### Run all tests:
```bash
pytest
```

### Run specific marker groups:
```bash
# Run only unit tests (fast, no API needed)
pytest -m unit

# Run only integration tests
pytest -m integration

# Run only artifact tests
pytest -m artifacts

# Run only async tests  
pytest -m async

# Run only config tests (fast)
pytest -m config

# Combine markers
pytest -m "integration and not slow"
```

### Run specific test file:
```bash
pytest test_artifacts.py
pytest test_basic_workflow.py -v
```

### Run specific test:
```bash
pytest test_artifacts.py::TestWARCArtifacts::test_warc_download
```

## Test Configuration

Tests use fixtures defined in `conftest.py`:
- `client` - ScrapflyClient instance
- `test_url` - Test URL for crawling

## Script Files

The `_scripts_to_convert/` directory contains old script-style test files that are not in pytest format. These are kept for reference but should eventually be:
1. Converted to proper pytest tests if needed
2. Deleted if functionality is already covered by existing pytest tests

## Test Coverage

The current pytest test suite covers:
- ✅ Basic crawler workflows (start, monitor, retrieve)
- ✅ Async/await operations
- ✅ WARC artifact parsing
- ✅ HAR artifact parsing  
- ✅ Content format extraction (HTML, markdown, text)
- ✅ Configuration validation
- ✅ Error handling and edge cases
- ✅ Concurrent crawler operations
- ✅ Result processing and iteration
