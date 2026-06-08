"""End-to-end integration test for Cloud Browser → Web Scraping API
session handoff.

Scenario (per docs/cloud-browser-wsa-handoff/ in the monorepo):

  1. Drive a Cloud Browser session against https://web-scraping.dev/login.
     Submit the login form (user123 / password). The server sets
     `auth=user123-secret-token` as a cookie in the Chrome profile.
  2. Stop the Cloud Browser session. The scrapium-agent flushes the
     cookie to Default/Cookies, writes scrapium.json, zips, uploads to
     GCS.
  3. Call the Web Scraping API with session=cb:<same-id>:
       (a) render_js=False (curlium path) → assert authenticated HTML.
       (b) render_js=True (browser path) → assert authenticated HTML and
           capture a full-page screenshot for visual evidence.

Both scrapes prove the cookie was inherited and the server treats the
WSA call as the same authenticated user the Cloud Browser was.

Run:
    SCRAPFLY_KEY=scp-live-... pytest tests/test_cloud_browser_handoff.py -v -s
"""

import os
import time
import uuid

import pytest
from playwright.sync_api import sync_playwright

from scrapfly import BrowserConfig, ScrapeConfig, ScrapflyClient


API_KEY = os.environ.get("SCRAPFLY_KEY", "scp-live-YOUR_API_KEY_HERE")
API_HOST = os.environ.get("SCRAPFLY_API_HOST", "https://api.scrapfly.local")

LOGIN_FORM_URL = "https://web-scraping.dev/login?prefill=1"
LOGIN_PAGE_URL = "https://web-scraping.dev/login"
LOGGED_IN_MARKER = "Logged in as User123"
AUTH_COOKIE_VALUE = "user123-secret-token"

# How long to give the scrapium-agent after stop() before WSA scrapes.
# Shutdown path is async: flushProfileViaCDP → writeScrapiumJSON →
# ZipUserDataDir → UploadUserDataDirToGCS. 5s comfortable on dev.
POST_STOP_GRACE_SECONDS = 5


@pytest.fixture
def client() -> ScrapflyClient:
    return ScrapflyClient(key=API_KEY, host=API_HOST, verify=False)


@pytest.fixture
def cb_session() -> str:
    # Unique per-run so re-runs don't collide on a frozen Mongo doc.
    return f"handoff-{uuid.uuid4().hex[:8]}"


class TestCloudBrowserHandoff:
    """Cloud Browser → WSA cookie/fingerprint/proxy inheritance."""

    def test_handoff_curlium_then_browser(self, client: ScrapflyClient, cb_session: str, tmp_path):
        """The full scenario: log in via Cloud Browser, stop, then access
        authenticated content via WSA with and without render_js.
        """
        # ── 1. Drive Cloud Browser, log in, capture the auth cookie. ──
        browser_cfg = BrowserConfig(
            session=cb_session,
            proxy_pool="public_datacenter_pool",
            country="us",
            os="linux",
            browser_brand="chrome",
            auto_close=False,
        )
        cdp_url = client.cloud_browser(browser_cfg)

        with sync_playwright() as p:
            browser = p.chromium.connect_over_cdp(cdp_url)
            ctx = browser.contexts[0]
            page = ctx.new_page()
            page.goto(LOGIN_FORM_URL, wait_until="domcontentloaded")
            page.fill('input[name="username"]', "user123")
            page.fill('input[name="password"]', "password")
            page.click('button[type="submit"]')
            page.wait_for_load_state("domcontentloaded")

            assert LOGGED_IN_MARKER in page.content(), (
                "Cloud Browser login form did not authenticate. Aborting "
                "before stop() — handoff has nothing to inherit."
            )

            cookies = ctx.cookies("https://web-scraping.dev/")
            auth = next((c for c in cookies if c.get("name") == "auth"), None)
            assert auth is not None and auth.get("value") == AUTH_COOKIE_VALUE, (
                f"Cloud Browser captured cookies {cookies!r} but no "
                f"auth={AUTH_COOKIE_VALUE!r} present"
            )
            browser.close()

        # ── 2. Stop the Cloud Browser session — agent uploads zip. ──
        client.cloud_browser_session_stop(cb_session)
        time.sleep(POST_STOP_GRACE_SECONDS)

        cb_session_param = f"cb:{cb_session}"

        # ── 3a. WSA scrape with render_js=False (curlium) ──
        curlium_result = client.scrape(ScrapeConfig(
            url=LOGIN_PAGE_URL,
            session=cb_session_param,
            render_js=False,
            country="us",
        ))
        assert LOGGED_IN_MARKER in curlium_result.content, (
            "curlium did not inherit the auth cookie — response HTML lacks "
            f"{LOGGED_IN_MARKER!r}. First 500 chars:\n{curlium_result.content[:500]}"
        )

        # ── 3b. WSA scrape with render_js=True (browser) + screenshot ──
        browser_result = client.scrape(ScrapeConfig(
            url=LOGIN_PAGE_URL,
            session=cb_session_param,
            render_js=True,
            country="us",
            screenshots={"page": "fullpage"},
        ))
        assert LOGGED_IN_MARKER in browser_result.content, (
            "browser-mode scrape did not inherit the auth cookie — "
            f"response HTML lacks {LOGGED_IN_MARKER!r}."
        )

        # Persist the screenshot for visual evidence. The SDK's
        # save_scrape_screenshot helper downloads the JPG from the URL
        # the engine returned and writes it to disk.
        scrape_result = browser_result.scrape_result or {}
        screenshots = scrape_result.get("screenshots") or {}
        assert "page" in screenshots, (
            f"render_js=True scrape did not return the requested screenshot; "
            f"got {list(screenshots.keys())!r}"
        )
        client.save_scrape_screenshot(
            api_response=browser_result,
            name="page",
            path=str(tmp_path),
        )
        out_path = tmp_path / "page.jpg"
        assert out_path.exists() and out_path.stat().st_size > 0, (
            f"Screenshot at {out_path} is empty"
        )
        print(f"\n  [evidence] authenticated screenshot saved at {out_path}")


class TestCloudBrowserHandoffErrors:
    """Negative-path behavior — handoff failures return a typed error."""

    def test_handoff_unknown_session_returns_400(self, client: ScrapflyClient):
        """A cb:<id> for a session that was never created should surface
        ERR::SESSION::CLOUD_BROWSER_NOT_FOUND, not a generic config error.
        """
        bogus_session = f"cb:does-not-exist-{uuid.uuid4().hex[:8]}"
        result = client.scrape(ScrapeConfig(
            url=LOGIN_PAGE_URL,
            session=bogus_session,
            render_js=False,
            country="us",
        ), no_raise=True)
        assert result.error is not None, "Expected an error for unknown cb: session"
        assert result.error.get("code") == "ERR::SESSION::CLOUD_BROWSER_NOT_FOUND", (
            f"Expected ERR::SESSION::CLOUD_BROWSER_NOT_FOUND, got {result.error!r}"
        )
