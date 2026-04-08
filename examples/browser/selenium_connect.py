"""
Connect to Scrapfly Cloud Browser for Selenium users.

Selenium does not natively support remote CDP WebSocket connections.
This example uses the /json/version discovery endpoint + Playwright as the CDP transport.

For direct Playwright usage (recommended), see playwright_connect.py
"""
import requests
from playwright.sync_api import sync_playwright

API_KEY = 'scp-live-d8ac176c2f9d48b993b58675bdf71615'

# Discover WebSocket URL via standard Chrome DevTools HTTP endpoint
version_info = requests.get(
    'https://browser.scrapfly.home/json/version',
    params={
        'key': API_KEY,
        'proxy_pool': 'datacenter',
        'os': 'linux',
        'country': 'us',
    },
    verify=False,
).json()

ws_url = version_info['webSocketDebuggerUrl']
print(f"Browser: {version_info['Browser']}")
print(f"WebSocket URL: {ws_url[:80]}...")

# Connect via Playwright CDP
with sync_playwright() as p:
    browser = p.chromium.connect_over_cdp(ws_url)
    context = browser.contexts[0]
    page = context.pages[0] if context.pages else context.new_page()

    page.goto('https://web-scraping.dev/products')
    print(f"Page title: {page.title()}")

    # Extract products (Selenium-style)
    products = page.locator('.product-thumb').all()
    for product in products[:3]:
        title = product.locator('h3').inner_text()
        print(f"  Product: {title}")

    page.screenshot(path='screenshot.png')
    print("Screenshot saved")

    browser.close()
