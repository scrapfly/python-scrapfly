#!/usr/bin/env python3
"""
LLM.txt Generator using Scrapfly Crawler API

This script demonstrates how to use Scrapfly's Crawler API to automatically
generate an llms.txt file from any website's documentation or content.

The llms.txt format (https://llmstxt.org) is a markdown-based standard for
providing website content to Large Language Models in an optimized format.

Learn more about llms.txt at: https://llmstxt.org
"""

import os
import sys
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


def generate_llm_txt(
    base_url: str,
    site_name: str,
    description: str,
    output_file: str = "llms-full.txt",
    page_limit: int = None,
    max_depth: int = 5,
    path_filter: str = None,
):
    """
    Generate an llms.txt file by crawling a website.

    Args:
        base_url: The starting URL to crawl (e.g., "https://example.com/docs")
        site_name: Name of the site/project for the H1 heading
        description: Short description for the blockquote summary
        output_file: Name of the output file (default: "llms-full.txt")
        page_limit: Maximum number of pages to crawl (default: unlimited)
        max_depth: Maximum crawl depth (default: 5)
        path_filter: Path pattern to restrict crawling (e.g., "/docs/*")

    Returns:
        Path to the generated llms.txt file
    """

    # Initialize Scrapfly client
    print("🔧 Initializing Scrapfly client...")

    client = ScrapflyClient(key=os.environ.get('SCRAPFLY_API_KEY'))

    # Configure the crawler
    print(f"\n📋 Crawler Configuration:")
    print(f"  • Target URL: {base_url}")
    if path_filter:
        print(f"  • Path filter: {path_filter}")
    if page_limit:
        print(f"  • Page limit: {page_limit}")
    print(f"  • Max depth: {max_depth}")
    print(f"  • Using sitemaps: Yes")
    print(f"  • Respecting robots.txt: Yes")

    crawler_config = CrawlerConfig(
        url=base_url,

        # Path restrictions (optional)
        include_only_paths=[path_filter] if path_filter else None,

        # Crawl limits
        page_limit=page_limit,
        max_depth=max_depth,

        # Respect site guidelines
        use_sitemaps=True,
        respect_robots_txt=True,

        # Don't follow external links
        follow_external_links=False,

        # Extract markdown content
        content_formats=['markdown'],
    )

    # Start the crawl
    print("\n🚀 Starting crawler...")
    crawl = Crawl(client, crawler_config).crawl()

    # Wait for crawl to complete
    print("\n📊 Crawling in progress...")
    crawl.wait(poll_interval=5, verbose=True)

    # Get final status
    status = crawl.status()
    print(f"\n✅ Crawl completed!")
    print(f"  Pages crawled: {status.urls_crawled}")
    print(f"  Pages failed: {status.urls_failed}")
    print(f"  Total discovered: {status.urls_discovered}")

    # Get URLs from WARC artifact
    print("\n📥 Retrieving crawled URLs from WARC...")
    warc_artifact = crawl.warc()
    urls_to_fetch = []

    for record in warc_artifact.iter_responses():
        if record.status_code == 200:
            urls_to_fetch.append(record.url)

    print(f"  ✓ Found {len(urls_to_fetch)} successful pages")

    # Retrieve markdown content using batch API
    print("\n📥 Fetching markdown content (batch API)...")
    all_contents = {}
    batch_size = 100  # API limit: 100 URLs per request

    for i in range(0, len(urls_to_fetch), batch_size):
        batch_urls = urls_to_fetch[i:i + batch_size]
        batch_num = (i // batch_size) + 1
        total_batches = (len(urls_to_fetch) + batch_size - 1) // batch_size

        print(f"  Batch {batch_num}/{total_batches}: Fetching {len(batch_urls)} URLs...")
        batch_contents = crawl.read_batch(batch_urls, formats=['markdown'])
        all_contents.update(batch_contents)
        print(f"    ✓ Retrieved {len(batch_contents)} pages with content")

    print(f"\n✅ Retrieved markdown for {len(all_contents)} pages")

    # Build llms.txt file
    print("\n📝 Building llms.txt file...")
    llm_lines = []

    # === REQUIRED: H1 heading ===
    llm_lines.append(f"# {site_name}")
    llm_lines.append("")

    # === OPTIONAL: Blockquote summary ===
    llm_lines.append(f"> {description}")
    llm_lines.append("")

    # === OPTIONAL: About section ===
    llm_lines.append("## About")
    llm_lines.append("")
    llm_lines.append(f"This document contains content crawled from {base_url}")
    llm_lines.append(f"using the Scrapfly Crawler API.")
    llm_lines.append("")
    llm_lines.append("The llms.txt format follows the specification at https://llmstxt.org")
    llm_lines.append("")

    # === MAIN CONTENT: Documentation pages ===
    llm_lines.append("## Content")
    llm_lines.append("")

    pages_added = 0
    total_content_chars = 0

    for url, formats_dict in all_contents.items():
        markdown = formats_dict.get('markdown', '')

        if not markdown or not markdown.strip():
            print(f"  ⚠️  Skipping {url} (no content)")
            continue

        pages_added += 1
        total_content_chars += len(markdown)

        # Add page section
        llm_lines.append("---")
        llm_lines.append("")
        llm_lines.append(f"### {url}")
        llm_lines.append("")
        llm_lines.append(markdown.strip())
        llm_lines.append("")

        if pages_added <= 10:  # Show first 10
            print(f"  ✓ [{pages_added}] {url} ({len(markdown):,} chars)")

    if pages_added > 10:
        print(f"  ... and {pages_added - 10} more pages")

    # === FOOTER ===
    llm_lines.append("---")
    llm_lines.append("")
    llm_lines.append("## Metadata")
    llm_lines.append("")
    llm_lines.append(f"- **Total pages**: {pages_added}")
    llm_lines.append(f"- **Source**: {base_url}")
    llm_lines.append(f"- **Format**: llms.txt (https://llmstxt.org)")
    llm_lines.append(f"- **Generated with**: Scrapfly Crawler API")

    # Write to file
    llm_txt_content = "\n".join(llm_lines)

    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(llm_txt_content)

    # Summary
    file_size_kb = len(llm_txt_content.encode('utf-8')) / 1024

    print(f"\n💾 Successfully saved to: {output_file}")
    print(f"  File size: {file_size_kb:.1f} KB")
    print(f"  Pages included: {pages_added}")
    print(f"  Total content: {total_content_chars:,} characters")

    print("\n" + "="*70)
    print("✅ LLM.txt generation complete!")
    print("="*70)
    print(f"\nYour {output_file} file is ready to use with LLMs!")
    print("You can now provide this file to ChatGPT, Claude, or other LLMs")
    print("to help them answer questions about your content.")

    return output_file


def main():
    """Example usage: Generate llms.txt for Scrapfly documentation"""

    # Check for API key
    if not os.environ.get('SCRAPFLY_API_KEY'):
        print("❌ Error: SCRAPFLY_API_KEY environment variable not set")
        print("\nPlease set your API key using one of these methods:")
        print("  1. Export as environment variable:")
        print("     export SCRAPFLY_API_KEY='scp-live-your-key-here'")
        print("  2. Create a .env file with:")
        print("     SCRAPFLY_API_KEY=scp-live-your-key-here")
        print("\nGet your API key at: https://scrapfly.io/dashboard")
        sys.exit(1)

    print("="*70)
    print("LLM.txt Generator - Scrapfly Crawler API Demo")
    print("="*70)

    # Generate llms.txt for Scrapfly documentation
    generate_llm_txt(
        base_url="https://scrapfly.io/docs",
        site_name="Scrapfly Documentation",
        description=(
            "Comprehensive guides and API references for web scraping, "
            "data extraction, and browser automation using Scrapfly."
        ),
        output_file="scrapfly_docs_llms-full.txt",
        page_limit=50,  # Limit for demo purposes
        max_depth=5,
        path_filter="/docs/*",  # Only crawl /docs/* pages
    )


if __name__ == "__main__":
    main()
