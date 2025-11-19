# Scrapfly Crawler API Examples

This directory contains examples demonstrating the Scrapfly Crawler API integration.

## Setup

### Get Your API Key

Get your API key from [https://scrapfly.io/dashboard](https://scrapfly.io/dashboard)

### Configure Your API Key

You have **two options** to provide your API key:

#### Option A: Environment Variable (Recommended)

Export the API key in your terminal:

```bash
export SCRAPFLY_API_KEY='scp-live-your-key-here'
```

Then run any example:

```bash
python3 sync_crawl.py
```

#### Option B: .env File

1. Copy the example .env file:

```bash
cp .env.example .env
```

2. Edit `.env` and replace the placeholder with your actual API key:

```
SCRAPFLY_API_KEY=scp-live-your-actual-key-here
```

3. Run any example (the .env file will be loaded automatically):

```bash
python3 sync_crawl.py
```

> **Note:** Install `python-dotenv` for automatic .env file loading: `pip install python-dotenv`
>
> If you don't install it, the examples will still work with environment variables exported in your shell.

## Quick Start

The easiest way to use the Crawler API is with the high-level `Crawl` object (see [quickstart.py](quickstart.py)):

```python
from scrapfly import ScrapflyClient, CrawlerConfig, Crawl

client = ScrapflyClient(key='your-key')

# Method chaining for concise usage
crawl = Crawl(
    client,
    CrawlerConfig(
        url='https://web-scraping.dev/products',
        page_limit=5
    )
).crawl().wait()

# Get results
pages = crawl.warc().get_pages()
for page in pages:
    print(f"{page['url']} ({page['status_code']})")
```

## Examples

- **[quickstart.py](quickstart.py)** - Simplest example using high-level `Crawl` API with method chaining
- **[sync_crawl.py](sync_crawl.py)** - Low-level API example showing start, poll, and download workflow
- **[demo_markdown.py](demo_markdown.py)** - Build LLM.txt files from crawled documentation with batch content retrieval
- **[webhook_example.py](webhook_example.py)** - Handle Crawler API webhooks for real-time event notifications

## Crawl Object Features

The `Crawl` object provides a stateful, high-level interface:

### Methods

- **`crawl()`** - Start the crawler job
- **`wait(poll_interval=5, max_wait=None, verbose=False)`** - Wait for completion
- **`status(refresh=True)`** - Get current status
- **`warc(artifact_type='warc')`** - Download WARC artifact
- **`har()`** - Download HAR (HTTP Archive) artifact with timing data
- **`read(url, format='html')`** - Get content for specific URL
- **`read_batch(urls, formats=['html'])`** - Get content for multiple URLs efficiently (up to 100 per request)
- **`read_iter(pattern, format='html')`** - Iterate through URLs matching wildcard pattern
- **`stats()`** - Get comprehensive statistics

### Properties

- **`uuid`** - Crawler job UUID
- **`started`** - Whether crawler has been started

### Usage Patterns

#### 1. Method Chaining (Most Concise)

```python
crawl = Crawl(client, config).crawl().wait()
pages = crawl.warc().get_pages()
```

#### 2. Step-by-Step (More Control)

```python
crawl = Crawl(client, config)
crawl.crawl()
crawl.wait(verbose=True, max_wait=300)

# Check status
status = crawl.status()
print(f"Crawled {status.urls_crawled} URLs")

# Get results
artifact = crawl.warc()
pages = artifact.get_pages()
```

#### 3. Read Specific URLs

```python
# Get content for a specific URL
html = crawl.read('https://example.com/page1')
if html:
    print(html.decode('utf-8'))
```

#### 4. Statistics

```python
stats = crawl.stats()
print(f"URLs discovered: {stats['urls_discovered']}")
print(f"URLs crawled: {stats['urls_crawled']}")
print(f"Crawl rate: {stats['crawl_rate']:.1f}%")
print(f"Total size: {stats['total_size_kb']:.2f} KB")
```

## Configuration Options

The `CrawlerConfig` class supports all crawler parameters:

```python
config = CrawlerConfig(
    url='https://example.com',
    page_limit=100,
    max_depth=3,
    exclude_paths=['/admin/*', '/api/*'],
    include_paths=['/products/*'],
    content_formats=['html', 'markdown'],
    # ... and many more options
)
```

See `CrawlerConfig` class documentation for all available parameters.

## Artifact Formats

### WARC Format

The crawler returns results in WARC (Web ARChive) format by default, which is automatically parsed:

```python
artifact = crawl.warc()

# Easy way: Get all pages as dictionaries
pages = artifact.get_pages()
for page in pages:
    url = page['url']
    status_code = page['status_code']
    headers = page['headers']
    content = page['content']  # bytes

# Memory-efficient: Iterate one record at a time
for record in artifact.iter_responses():
    print(f"{record.url}: {len(record.content)} bytes")

# Save to file
artifact.save('results.warc.gz')
```

### HAR Format

HAR (HTTP Archive) format includes detailed timing information for performance analysis:

```python
artifact = crawl.har()

# Access timing data
for entry in artifact.iter_responses():
    print(f"{entry.url}")
    print(f"  Status: {entry.status_code}")
    print(f"  Total time: {entry.time}ms")
    print(f"  Content type: {entry.content_type}")

    # Detailed timing breakdown
    timings = entry.timings
    print(f"  DNS: {timings.get('dns', 0)}ms")
    print(f"  Connect: {timings.get('connect', 0)}ms")
    print(f"  Wait: {timings.get('wait', 0)}ms")
    print(f"  Receive: {timings.get('receive', 0)}ms")

# Same easy interface as WARC
pages = artifact.get_pages()
```

## Error Handling

```python
from scrapfly import Crawl, CrawlerConfig

try:
    crawl = Crawl(client, config)
    crawl.crawl().wait(max_wait=300)

    if crawl.status().is_complete:
        pages = crawl.warc().get_pages()
        print(f"Success! Got {len(pages)} pages")
    elif crawl.status().is_failed:
        print("Crawler failed")

except RuntimeError as e:
    print(f"Error: {e}")
```

## Troubleshooting

### "SCRAPFLY_API_KEY environment variable not set"

Make sure you've either:
1. Exported the environment variable: `export SCRAPFLY_API_KEY='your-key'`
2. Created a `.env` file with your API key

### "Invalid API key" error

Double-check that:
1. Your API key is correct and starts with `scp-live-`
2. You have an active Scrapfly subscription
3. You're using the correct API key from your dashboard

### Import errors for dotenv

The `python-dotenv` package is optional. If you see import warnings, you can either:
1. Install it: `pip install python-dotenv`
2. Ignore them - environment variables will still work

## Learn More

- [Scrapfly Crawler API Documentation](https://scrapfly.io/docs/crawler-api)
- [Python SDK Documentation](https://scrapfly.io/docs/sdk/python)
