#!/usr/bin/env python3
"""
Synchronous Crawler API Example

This example demonstrates the complete end-to-end workflow:
1. Start a crawler job
2. Poll for status until completion
3. Download WARC artifact
4. Parse and process crawled pages
"""

import os
import time
from pathlib import Path

# Load environment variables from .env file if present
try:
    from dotenv import load_dotenv
    # Look for .env in current directory or parent directories
    env_path = Path(__file__).parent / '.env'
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()  # Try to find .env in parent directories
except ImportError:
    # python-dotenv not installed, will use system environment variables
    pass

from scrapfly import ScrapflyClient, CrawlerConfig

# Initialize client - looks for SCRAPFLY_API_KEY environment variable
api_key = os.environ.get('SCRAPFLY_API_KEY')
if not api_key:
    print("❌ Error: SCRAPFLY_API_KEY environment variable not set")
    print("\nPlease set your API key using one of these methods:")
    print("  1. Export as environment variable:")
    print("     export SCRAPFLY_API_KEY='scp-live-your-key-here'")
    print("  2. Create a .env file with:")
    print("     SCRAPFLY_API_KEY=scp-live-your-key-here")
    exit(1)

client = ScrapflyClient(key=api_key)

# Configure the crawler
config = CrawlerConfig(
    url='https://web-scraping.dev/products',
    page_limit=10,
    max_depth=2,
    content_formats=['html', 'markdown']
)

print("Starting crawler...")
start_response = client.start_crawl(config)
print(f"✓ Crawler started with UUID: {start_response.uuid}")
print(f"  Initial status: {start_response.status}")

# Poll for status
print("\nMonitoring progress...")
while True:
    status = client.get_crawl_status(start_response.uuid)
    print(f"  Status: {status.status}")
    print(f"  Progress: {status.progress_pct:.1f}%")
    print(f"  Crawled: {status.urls_crawled}/{status.urls_discovered} pages")

    if status.is_complete:
        print("\n✓ Crawl completed!")
        break
    elif status.is_failed:
        print("\n✗ Crawl failed!")
        break
    elif status.is_cancelled:
        print("\n✗ Crawl cancelled!")
        break

    time.sleep(5)

# Download results
if status.is_complete:
    print("\nDownloading results...")
    artifact = client.get_crawl_artifact(start_response.uuid)

    # Easy mode: get all pages
    pages = artifact.get_pages()
    print(f"✓ Downloaded {len(pages)} pages")

    # Display results
    print("\nCrawled pages:")
    for page in pages:
        url = page['url']
        status_code = page['status_code']
        content_size = len(page['content'])
        print(f"  - {url}: {status_code} ({content_size} bytes)")

    # Alternative: Memory-efficient iteration for large crawls
    print("\nIterating through WARC records:")
    for i, record in enumerate(artifact.iter_responses(), 1):
        if i > 3:  # Show first 3 only
            break
        print(f"  {i}. {record.url}")
        print(f"     Status: {record.status_code}")
        print(f"     Content-Type: {record.headers.get('Content-Type', 'N/A')}")

    # Save to file
    artifact.save('crawl_results.warc.gz')
    print(f"\n✓ Saved results to crawl_results.warc.gz")
