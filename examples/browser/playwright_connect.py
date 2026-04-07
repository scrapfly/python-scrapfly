"""Connect to Scrapfly Cloud Browser using Playwright (Python)"""
from scrapfly import ScrapflyClient, BrowserConfig
from playwright.sync_api import sync_playwright

scrapfly = ScrapflyClient(key='__API_KEY__')

# Configure Cloud Browser connection
browser_config = BrowserConfig(
    proxy_pool='datacenter',
    os='linux',
)

# Get the CDP WebSocket URL
cdp_url = scrapfly.cloud_browser(browser_config)

def run():
    with sync_playwright() as p:
        browser = None
        try:
            # Connect to Cloud Browser
            browser = p.chromium.connect_over_cdp(cdp_url)

            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()

            # Navigate and interact
            page.goto('https://web-scraping.dev')
            print('Page title:', page.title())

            # Take a screenshot
            page.screenshot(path='screenshot.png')
        finally:
            if browser:
                browser.close()

run()
