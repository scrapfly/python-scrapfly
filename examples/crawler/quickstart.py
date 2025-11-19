#!/usr/bin/env python3
"""
Crawler API Quick Start

The simplest possible example showing how to crawl a website
and get the results.
"""

import os
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

from scrapfly import ScrapflyClient, CrawlerConfig, Crawl

# 1. Setup client - looks for SCRAPFLY_API_KEY environment variable
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

# 2. Create and run crawler
crawl = Crawl(
    client,
    CrawlerConfig(url='https://web-scraping.dev/products', page_limit=5)
).crawl().wait()

# 3. Get results
pages = crawl.warc().get_pages()

# 4. Process results
print(f"Crawled {len(pages)} pages:")
for page in pages:
    print(f"  • {page['url']} ({page['status_code']})")

# 5. Access specific URLs
html = crawl.read('https://web-scraping.dev/products')
if html:
    print(f"\nMain page is {len(html):,} bytes")
