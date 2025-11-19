#!/usr/bin/env python3
"""
Custom LLM.txt Generator Example

This shows how to customize the llm.txt generator for your own website.
Simply modify the parameters below to crawl your content.
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

from generate_llm_txt import generate_llm_txt


def main():
    """
    Customize these parameters for your website
    """

    # ============================================================
    # CONFIGURATION - Modify these for your website
    # ============================================================

    # Your website's starting URL
    BASE_URL = "https://scrapfly.io/docs"

    # Name of your project/site (used as H1 heading)
    SITE_NAME = "Scrapfly Documentation"

    # Short description (used in blockquote)
    DESCRIPTION = (
        "Comprehensive guides and API references for web scraping, "
        "data extraction, and browser automation using Scrapfly."
    )

    # Output filename
    OUTPUT_FILE = "llms-full.txt"

    # Maximum pages to crawl (None = unlimited)
    # Start with a small number for testing!
    PAGE_LIMIT = 50

    # Maximum crawl depth (how many clicks away from start URL)
    MAX_DEPTH = 5

    # Path filter - only crawl URLs matching this pattern
    # Examples:
    #   "/docs/*"           - Only /docs pages
    #   None                - Crawl everything
    PATH_FILTER = "/docs/*"

    # ============================================================
    # ADVANCED OPTIONS (optional)
    # ============================================================

    # You can also pass these options to CrawlerConfig:
    #
    # exclude_paths=["/api/*", "/admin/*"]  # Don't crawl these
    # follow_external_links=True            # Follow links to other domains
    # use_sitemaps=False                    # Don't use sitemap.xml
    # respect_robots_txt=False              # Ignore robots.txt
    # max_duration=3600                     # Max crawl time in seconds
    # max_concurrency=5                     # Parallel requests

    # ============================================================
    # RUN THE GENERATOR
    # ============================================================

    print("="*70)
    print("Custom LLM.txt Generator")
    print("="*70)
    print()
    print(f"Target: {BASE_URL}")
    print(f"Output: {OUTPUT_FILE}")
    print()

    generate_llm_txt(
        base_url=BASE_URL,
        site_name=SITE_NAME,
        description=DESCRIPTION,
        output_file=OUTPUT_FILE,
        page_limit=PAGE_LIMIT,
        max_depth=MAX_DEPTH,
        path_filter=PATH_FILTER,
    )


if __name__ == "__main__":
    # Check for API key
    if not os.environ.get('SCRAPFLY_API_KEY'):
        print("❌ Error: SCRAPFLY_API_KEY environment variable not set")
        print("\nPlease set your API key using one of these methods:")
        print("  1. Export as environment variable:")
        print("     export SCRAPFLY_API_KEY='scp-live-your-key-here'")
        print("  2. Create a .env file with:")
        print("     SCRAPFLY_API_KEY=scp-live-your-key-here")
        print("\nGet your API key at: https://scrapfly.io/dashboard")
        exit(1)

    main()
