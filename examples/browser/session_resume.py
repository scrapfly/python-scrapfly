"""Session Resume: reconnect to an existing Cloud Browser session"""
import time
from scrapfly import ScrapflyClient, BrowserConfig
from playwright.sync_api import sync_playwright

scrapfly = ScrapflyClient(key='__API_KEY__')

SESSION_ID = 'my-persistent-session'

# Configure with session + auto_close=False for persistence
browser_config = BrowserConfig(
    proxy_pool='datacenter',
    session=SESSION_ID,
    auto_close=False,
)

cdp_url = scrapfly.cloud_browser(browser_config)


def first_connection():
    """First connection: navigate and set cookies"""
    print('=== First Connection ===')
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        page = context.new_page()
        page.goto('https://web-scraping.dev')

        # Set a cookie
        context.add_cookies([{
            'name': 'session_token',
            'value': 'abc123',
            'domain': 'web-scraping.dev',
            'path': '/'
        }])

        print('Cookies set, disconnecting...')
        browser.close()  # Disconnects CDP - browser stays alive (auto_close=false)


def second_connection():
    """Second connection: cookies are still there"""
    print('=== Second Connection (Resume) ===')
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(cdp_url)
        context = browser.contexts[0]
        page = context.pages[0] if context.pages else context.new_page()

        # Cookies are still there!
        cookies = context.cookies('https://web-scraping.dev')
        print('Cookies from previous session:', cookies)

        browser.close()  # Disconnects CDP


first_connection()
time.sleep(2)  # Wait a bit, then reconnect
second_connection()

# Terminate the session when fully done
scrapfly.cloud_browser_session_stop(SESSION_ID)
print(f'Session {SESSION_ID} terminated')
