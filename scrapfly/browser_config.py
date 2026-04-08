"""
Cloud Browser Configuration

Provides ``BrowserConfig`` — the high-level configuration object for the
Scrapfly Cloud Browser API. The actual session is allocated when you connect
your CDP client (Playwright, Puppeteer, Selenium, etc.) to the WebSocket URL
returned by :py:meth:`ScrapflyClient.cloud_browser`.

Example:

    >>> from scrapfly import ScrapflyClient, BrowserConfig
    >>> from playwright.sync_api import sync_playwright
    >>>
    >>> client = ScrapflyClient(key="YOUR_API_KEY")
    >>> config = BrowserConfig(
    ...     proxy_pool="public_datacenter_pool",
    ...     os="linux",
    ...     country="us",
    ... )
    >>> with sync_playwright() as p:
    ...     browser = p.chromium.connect_over_cdp(client.cloud_browser(config))
    ...     # ... use the browser ...
    ...     browser.close()

The fields mirror the Cloud Browser API query parameters documented at
https://scrapfly.io/docs/cloud-browser-api/getting-started — see the public
docs for the exact behavior of each option.
"""

from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urlencode

# Valid values for the cloud-browser pool selector. The engine accepts only
# these two literals (per pkg/browser/config.go in scrapfly-api); any other
# value is silently dropped and the default is applied.
PROXY_POOL_DATACENTER = "public_datacenter_pool"
PROXY_POOL_RESIDENTIAL = "public_residential_pool"

# Valid OS values per the engine validation.
OS_LINUX = "linux"
OS_WINDOWS = "windows"
OS_MAC = "mac"


@dataclass
class BrowserConfig:
    """
    Configuration for a Cloud Browser session.

    All fields are optional. When omitted, the server applies its own
    documented defaults (proxy_pool=public_datacenter_pool, OS=random,
    country=random from the proxy pool, auto_close=True, timeout=900s).

    Attributes:
        proxy_pool: Either ``"public_datacenter_pool"`` (cheaper, faster) or
            ``"public_residential_pool"`` (residential IPs for tougher targets).
            Use the :data:`PROXY_POOL_DATACENTER` / :data:`PROXY_POOL_RESIDENTIAL`
            constants for type safety. Default: server picks ``public_datacenter_pool``.
        os: Browser operating system fingerprint. One of ``"linux"``, ``"windows"``,
            ``"mac"``. Default: server picks randomly.
        country: ISO 3166-1 alpha-2 country code (e.g. ``"us"``, ``"gb"``,
            ``"de"``) for the proxy exit IP. Default: server picks from the
            proxy pool's preferred countries.
        session: Stable user-supplied session ID. Two sessions with the same
            ID share the same underlying browser instance (browser persistence
            across reconnects). Useful for multi-step workflows.
        auto_close: When True (default), the browser is released as soon as
            your CDP client disconnects. Set False to keep the browser alive
            after disconnect — combine with a stable ``session`` ID to resume
            the session later.
        timeout: Maximum session duration in seconds. Default 900 (15 min),
            max 1800 (30 min) per documented limits.
        block_images: Block image loading at the network layer to save bandwidth.
        block_styles: Block stylesheet loading. Implies a non-visual rendering
            mode — pages may render incorrectly.
        block_fonts: Block font file loading.
        block_media: Block video/audio loading.
        screenshot: Enable screenshot mode (disables blocking of styles/fonts
            so the rendered page looks correct in screenshots).
        cache: Enable static-asset caching across sessions.
        blacklist: Apply Scrapfly's domain blacklist to block known
            tracker/ad/malware domains at the proxy layer.
        extensions: List of Chrome extension IDs to install in the browser
            (must be uploaded via the Cloud Browser dashboard first).
        byop_proxy: Bring Your Own Proxy URL. Format:
            ``{protocol}://{user}:{pass}@{host}:{port}``. Supported protocols:
            http, https, socks5, socks5h, socks5+udp, socks5h+udp.
            When set, ``proxy_pool`` is ignored — your proxy is used instead.
    """

    proxy_pool: Optional[str] = None
    os: Optional[str] = None
    country: Optional[str] = None
    session: Optional[str] = None
    auto_close: Optional[bool] = None
    timeout: Optional[int] = None

    # Resource blocking
    block_images: Optional[bool] = None
    block_styles: Optional[bool] = None
    block_fonts: Optional[bool] = None
    block_media: Optional[bool] = None
    screenshot: Optional[bool] = None

    # Scrapium features
    cache: Optional[bool] = None
    blacklist: Optional[bool] = None

    # Browser customization
    extensions: List[str] = field(default_factory=list)
    byop_proxy: Optional[str] = None

    def to_query_params(self) -> dict:
        """
        Serialize this config to a flat dict suitable for URL query encoding.

        Drops unset (``None``) fields so the server applies its own defaults
        for anything the caller didn't explicitly set. Validates the small
        number of fields where the engine accepts only specific literal values
        — invalid values raise ``ValueError`` immediately rather than failing
        silently on the server side (which is the historical footgun).
        """
        # Strict validation of enum-like fields. The engine silently drops
        # invalid values, so we validate locally to give immediate feedback.
        if self.proxy_pool is not None and self.proxy_pool not in (
            PROXY_POOL_DATACENTER,
            PROXY_POOL_RESIDENTIAL,
        ):
            raise ValueError(
                f"BrowserConfig.proxy_pool must be {PROXY_POOL_DATACENTER!r} or "
                f"{PROXY_POOL_RESIDENTIAL!r}, got {self.proxy_pool!r}"
            )
        if self.os is not None and self.os not in (OS_LINUX, OS_WINDOWS, OS_MAC):
            raise ValueError(
                f"BrowserConfig.os must be one of 'linux'/'windows'/'mac', got {self.os!r}"
            )

        params: dict = {}
        # Bool fields are sent as lowercase strings ('true'/'false') because
        # the engine parses them with a case-insensitive string comparison.
        bool_fields = (
            "auto_close",
            "block_images",
            "block_styles",
            "block_fonts",
            "block_media",
            "screenshot",
            "cache",
            "blacklist",
        )
        for field_name in (
            "proxy_pool",
            "os",
            "country",
            "session",
            "timeout",
            "byop_proxy",
        ):
            value = getattr(self, field_name)
            if value is not None:
                params[field_name] = value
        for field_name in bool_fields:
            value = getattr(self, field_name)
            if value is not None:
                params[field_name] = "true" if value else "false"
        if self.extensions:
            # Engine expects extensions as a comma-separated list (per
            # pkg/browser/config.go::query.Get("extensions")).
            params["extensions"] = ",".join(self.extensions)
        return params

    def to_query_string(self) -> str:
        """Serialize to a URL-ready query string (without leading ``?``)."""
        return urlencode(self.to_query_params())
