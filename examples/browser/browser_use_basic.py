"""
Basic Browser Use connection test with Scrapfly Cloud Browser.

Browser Use connects to Cloud Browser via CDP. The first connection may trigger
a reconnection (this is normal - the Cloud Browser allocates the browser instance
during the initial WebSocket handshake).

Requires: Python 3.11+, browser-use, scrapfly-sdk
"""
import asyncio
from scrapfly import ScrapflyClient, BrowserConfig
from browser_use import Browser, BrowserProfile

scrapfly = ScrapflyClient(
    key='scp-live-d8ac176c2f9d48b993b58675bdf71615',
    cloud_browser_host='wss://browser.scrapfly.home',
    verify=False,
)

config = BrowserConfig(
    proxy_pool='datacenter',
    os='linux',
)

cdp_url = scrapfly.cloud_browser(config)
print(f"CDP URL: {cdp_url[:80]}...")


async def test_connection():
    browser = Browser(
        browser_profile=BrowserProfile(
            cdp_url=cdp_url,
        )
    )

    # Start the browser session (may reconnect once during allocation)
    await browser.start()
    print("Connected to Cloud Browser")

    # Get a page and navigate
    page = await browser.get_current_page()
    await page.goto('https://web-scraping.dev/products')

    title = await page.title()
    url = page.url
    print(f"Page title: {title}")
    print(f"Page URL: {url}")

    await browser.close()
    print("Browser closed successfully")


asyncio.run(test_connection())
