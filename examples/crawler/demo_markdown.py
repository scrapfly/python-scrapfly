#!/usr/bin/env python3
"""
LLM.txt Builder Demo

Demonstrates:
- Crawling Scrapfly documentation with path restrictions
- Using sitemaps and respecting robots.txt
- Extracting markdown content from all pages using the Contents API
- Building an llms-full.txt file following the llmstxt.org specification

llms.txt format specification (from https://llmstxt.org):
- H1 heading with project/site name (required)
- Blockquote with short summary
- Descriptive sections
- H2-delimited resource lists
- Optional section for secondary resources

This demo creates an llms-full.txt with all content inline.

Key implementation details:
- Uses crawl.read_batch() to retrieve markdown content efficiently
- Batches up to 100 URLs per API request (multipart/related response)
- Minimal API calls - significantly faster than per-URL requests
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

print("="*80)
print("LLM.txt Builder for Scrapfly Documentation")
print("="*80)

# Configure crawler for documentation
print("\n📋 Crawler Configuration:")
print("  • Target: https://scrapfly.io/docs")
print("  • Path restriction: /docs/* only")
print("  • Using sitemaps: Yes")
print("  • Respecting robots.txt: Yes")
print("  • Content format: Markdown")

config = CrawlerConfig(
    url='https://scrapfly.io/docs',

    # Path restrictions - only crawl documentation content
    include_only_paths=['/docs/*'],
    page_limit=50,

    # Respect site guidelines
    use_sitemaps=True,
    respect_robots_txt=True,
    # Don't follow external links
    follow_external_links=False,
    # Extract markdown content
    content_formats=['markdown'],
    # Crawl depth
    max_depth=5,
)

print("\n🚀 Starting crawler...")
crawl = Crawl(client, config).crawl()

# Monitor progress using proper Crawl API
print("\n📊 Crawling progress:")
crawl.wait(poll_interval=5, verbose=True)

print("\n✅ Crawl completed!")
final_status = crawl.status()
print(f"  Total pages crawled: {final_status.urls_crawled}")
print(f"  Failed: {final_status.urls_failed}")

# Get all URLs from WARC to retrieve in batch
print("\n📥 Getting URLs from WARC...")
warc_artifact = crawl.warc()
all_urls = []
for record in warc_artifact.iter_responses():
    if record.status_code == 200:
        all_urls.append(record.url)

print(f"  ✓ Found {len(all_urls)} URLs to retrieve")

# Retrieve content using efficient batch API (max 100 URLs per request)
print("\n📥 Retrieving markdown content in batches...")
batch_size = 100
all_contents = {}

for i in range(0, len(all_urls), batch_size):
    batch_urls = all_urls[i:i + batch_size]
    print(f"  Batch {i//batch_size + 1}: Retrieving {len(batch_urls)} URLs...")
    batch_contents = crawl.read_batch(batch_urls, formats=['markdown'])
    all_contents.update(batch_contents)
    print(f"    ✓ Retrieved {len(batch_contents)} URLs with content")

print(f"\n✅ Total URLs with markdown content: {len(all_contents)}")

# Build llms-full.txt file following specification
print("\n📝 Building llms-full.txt file...")

llm_content = []

# === REQUIRED: H1 heading with project name ===
llm_content.append("# Scrapfly Documentation")
llm_content.append("")

# === OPTIONAL: Blockquote summary ===
llm_content.append("> Scrapfly documentation contains comprehensive guides, API references, and best practices")
llm_content.append("> for web scraping, data extraction, and browser automation using Scrapfly's")
llm_content.append("> powerful scraping infrastructure.")
llm_content.append("")

# === OPTIONAL: Descriptive content ===
llm_content.append("## About")
llm_content.append("")
llm_content.append("This document contains the complete content from the ")
llm_content.append("Scrapfly documentation (https://scrapfly.io/docs), crawled using the Scrapfly Crawler API.")
llm_content.append("")
llm_content.append("The content includes:")
llm_content.append("- API documentation and references")
llm_content.append("- SDK usage guides for Python, Node.js, and other languages")
llm_content.append("- Web scraping tutorials and best practices")
llm_content.append("- Anti-bot bypass techniques (ASP)")
llm_content.append("- Extraction and screenshot API guides")
llm_content.append("")

# === MAIN CONTENT: All documentation pages ===
llm_content.append("## Documentation Pages")
llm_content.append("")

# Process each URL - content already retrieved via batch API
successful_pages = 0
total_chars = 0

for url, formats_dict in all_contents.items():
    markdown_content = formats_dict.get('markdown', '')

    if not markdown_content or not markdown_content.strip():
        print(f"  ⚠️  No markdown content for {url}")
        continue

    successful_pages += 1
    total_chars += len(markdown_content)

    # Add page section with clear separators
    llm_content.append("---")
    llm_content.append("")
    llm_content.append(f"### {url}")
    llm_content.append("")
    llm_content.append(markdown_content.strip())
    llm_content.append("")

    print(f"  ✓ [{successful_pages}] Added: {url} ({len(markdown_content):,} chars)")

# === FOOTER ===
llm_content.append("---")
llm_content.append("")
llm_content.append("## End of Documentation")
llm_content.append("")
llm_content.append(f"Total pages: {successful_pages}")
llm_content.append(f"Source: https://scrapfly.io/docs")
llm_content.append(f"Format: llms-full.txt (per https://llmstxt.org)")

# Join all content
llm_txt = "\n".join(llm_content)

# Save to file
output_file = "scrapfly_docs_llms-full.txt"
with open(output_file, 'w', encoding='utf-8') as f:
    f.write(llm_txt)

print(f"\n💾 Saved to: {output_file}")
print(f"  Total size: {len(llm_txt):,} characters ({len(llm_txt.encode('utf-8')):,} bytes)")
print(f"  Pages included: {successful_pages}")
print(f"  Total content: {total_chars:,} characters")

# Show sample
print("\n📄 Sample output (first 1000 chars):")
print("-" * 80)
print(llm_txt[:1000])
print("...")
print("-" * 80)

# Show statistics
stats = crawl.stats()
print("\n📊 Crawl Statistics:")
print(f"  URLs discovered: {stats['urls_discovered']}")
print(f"  URLs crawled: {stats['urls_crawled']}")
print(f"  URLs failed: {stats['urls_failed']}")
print(f"  Progress: {stats['progress_pct']:.1f}%")

print("\n" + "="*80)
print("✅ Demo Complete!")
print("="*80)
print(f"\nYour llms-full.txt file is ready at: {output_file}")
print("This file follows the llmstxt.org specification and can be used to provide")
print("comprehensive Scrapfly documentation to LLMs for question answering, analysis,")
print("or training purposes.")
