from enum import Enum
from typing import Optional, Union, Dict, List
from urllib.parse import urlencode

from .api_config import BaseApiConfig


class ProxyPool(Enum):
    DATACENTER = "datacenter"
    RESIDENTIAL = "residential"


class OperatingSystem(Enum):
    LINUX = "linux"
    WINDOWS = "windows"
    MACOS = "macos"


class BrowserConfig(BaseApiConfig):

    CLOUD_BROWSER_HOST = 'wss://browser.scrapfly.io'

    def __init__(
        self,
        proxy_pool: Optional[Union[str, ProxyPool]] = None,
        os: Optional[Union[str, OperatingSystem]] = None,
        session: Optional[str] = None,
        country: Optional[str] = None,
        auto_close: Optional[bool] = None,
        timeout: Optional[int] = None,
        debug: Optional[bool] = None,
        extensions: Optional[List[str]] = None,
        block_images: Optional[bool] = None,
        block_styles: Optional[bool] = None,
        block_fonts: Optional[bool] = None,
        block_media: Optional[bool] = None,
        screenshot: Optional[bool] = None,
        resolution: Optional[str] = None,
        target_url: Optional[str] = None,
        cache: Optional[bool] = None,
        blacklist: Optional[bool] = None,
        unblock: Optional[bool] = None,
        unblock_timeout: Optional[int] = None,
        browser_brand: Optional[str] = None,
        byop_proxy: Optional[str] = None,
        enable_mcp: Optional[bool] = None,
        solve_captcha: Optional[bool] = None,
    ):
        if timeout is not None and timeout > 1800:
            raise ValueError('timeout cannot exceed 1800 seconds (30 minutes)')

        if proxy_pool is not None and isinstance(proxy_pool, str):
            proxy_pool = ProxyPool(proxy_pool)

        if os is not None and isinstance(os, str):
            os = OperatingSystem(os)

        self.proxy_pool = proxy_pool
        self.os = os
        self.session = session
        self.country = country
        self.auto_close = auto_close
        self.timeout = timeout
        self.debug = debug
        self.extensions = extensions
        self.block_images = block_images
        self.block_styles = block_styles
        self.block_fonts = block_fonts
        self.block_media = block_media
        self.screenshot = screenshot
        self.resolution = resolution
        self.target_url = target_url
        self.cache = cache
        self.blacklist = blacklist
        self.unblock = unblock
        self.unblock_timeout = unblock_timeout
        self.browser_brand = browser_brand
        # BYOP (Bring Your Own Proxy): full proxy URL
        # Format: {protocol}://{user}:{pass}@{host}:{port}
        # Supported protocols: http, https, socks5, socks5h, socks5+udp, socks5h+udp
        # The +udp variants enable HTTP/3 (QUIC) via SOCKS5 UDP ASSOCIATE — only
        # works with proxy providers that implement RFC 1928 UDP ASSOCIATE.
        # Requires a Custom plan subscription. See:
        # https://scrapfly.io/docs/cloud-browser-api/byop
        self.byop_proxy = byop_proxy
        self.enable_mcp = enable_mcp
        # SolveCaptcha: arm Scrapium's built-in captcha detector + solver on
        # the first page attach. Turnstile, DataDome slider, reCAPTCHA,
        # GeeTest, PerimeterX hold, and puzzle captchas are handled
        # automatically. Billed per solve; failures cost nothing.
        # https://scrapfly.io/docs/cloud-browser-api/captcha-solver
        self.solve_captcha = solve_captcha

    def websocket_url(self, api_key: str, host: Optional[str] = None) -> str:
        params = {'api_key': api_key}

        if self.proxy_pool is not None:
            params['proxy_pool'] = self.proxy_pool.value if isinstance(self.proxy_pool, ProxyPool) else self.proxy_pool

        if self.os is not None:
            params['os'] = self.os.value if isinstance(self.os, OperatingSystem) else self.os

        if self.session is not None:
            params['session'] = self.session

        if self.country is not None:
            params['country'] = self.country

        if self.auto_close is not None:
            params['auto_close'] = self._bool_to_http(self.auto_close)

        if self.timeout is not None:
            params['timeout'] = self.timeout

        if self.debug is not None:
            params['debug'] = self._bool_to_http(self.debug)

        if self.extensions:
            params['extensions'] = ','.join(self.extensions)

        if self.block_images is not None:
            params['block_images'] = self._bool_to_http(self.block_images)

        if self.block_styles is not None:
            params['block_styles'] = self._bool_to_http(self.block_styles)

        if self.block_fonts is not None:
            params['block_fonts'] = self._bool_to_http(self.block_fonts)

        if self.block_media is not None:
            params['block_media'] = self._bool_to_http(self.block_media)

        if self.screenshot is not None:
            params['screenshot'] = self._bool_to_http(self.screenshot)

        if self.resolution is not None:
            params['resolution'] = self.resolution

        if self.target_url is not None:
            params['target_url'] = self.target_url

        if self.cache is not None:
            params['cache'] = self._bool_to_http(self.cache)

        if self.blacklist is not None:
            params['blacklist'] = self._bool_to_http(self.blacklist)

        if self.unblock is not None:
            params['unblock'] = self._bool_to_http(self.unblock)

        if self.unblock_timeout is not None:
            params['unblock_timeout'] = self.unblock_timeout

        if self.browser_brand is not None:
            params['browser_brand'] = self.browser_brand

        if self.byop_proxy is not None:
            params['byop_proxy'] = self.byop_proxy

        if self.enable_mcp is not None:
            params['enable_mcp'] = self._bool_to_http(self.enable_mcp)

        if self.solve_captcha is not None:
            params['solve_captcha'] = self._bool_to_http(self.solve_captcha)

        base_host = host or self.CLOUD_BROWSER_HOST
        return base_host + '?' + urlencode(params)

    def to_dict(self) -> Dict:
        return {
            'proxy_pool': self.proxy_pool.value if isinstance(self.proxy_pool, ProxyPool) else self.proxy_pool,
            'os': self.os.value if isinstance(self.os, OperatingSystem) else self.os,
            'session': self.session,
            'country': self.country,
            'auto_close': self.auto_close,
            'timeout': self.timeout,
            'debug': self.debug,
            'extensions': self.extensions,
            'block_images': self.block_images,
            'block_styles': self.block_styles,
            'block_fonts': self.block_fonts,
            'block_media': self.block_media,
            'screenshot': self.screenshot,
            'resolution': self.resolution,
            'target_url': self.target_url,
            'cache': self.cache,
            'blacklist': self.blacklist,
            'unblock': self.unblock,
            'unblock_timeout': self.unblock_timeout,
            'browser_brand': self.browser_brand,
            'byop_proxy': self.byop_proxy,
            'enable_mcp': self.enable_mcp,
            'solve_captcha': self.solve_captcha,
        }

    @staticmethod
    def from_dict(browser_config_dict: Dict) -> 'BrowserConfig':
        proxy_pool = browser_config_dict.get('proxy_pool', None)
        if proxy_pool is not None:
            proxy_pool = ProxyPool(proxy_pool)

        os = browser_config_dict.get('os', None)
        if os is not None:
            os = OperatingSystem(os)

        return BrowserConfig(
            proxy_pool=proxy_pool,
            os=os,
            session=browser_config_dict.get('session', None),
            country=browser_config_dict.get('country', None),
            auto_close=browser_config_dict.get('auto_close', None),
            timeout=browser_config_dict.get('timeout', None),
            debug=browser_config_dict.get('debug', None),
            extensions=browser_config_dict.get('extensions', None),
            block_images=browser_config_dict.get('block_images', None),
            block_styles=browser_config_dict.get('block_styles', None),
            block_fonts=browser_config_dict.get('block_fonts', None),
            block_media=browser_config_dict.get('block_media', None),
            screenshot=browser_config_dict.get('screenshot', None),
            resolution=browser_config_dict.get('resolution', None),
            target_url=browser_config_dict.get('target_url', None),
            cache=browser_config_dict.get('cache', None),
            blacklist=browser_config_dict.get('blacklist', None),
            unblock=browser_config_dict.get('unblock', None),
            unblock_timeout=browser_config_dict.get('unblock_timeout', None),
            browser_brand=browser_config_dict.get('browser_brand', None),
            byop_proxy=browser_config_dict.get('byop_proxy', None),
            enable_mcp=browser_config_dict.get('enable_mcp', None),
            solve_captcha=browser_config_dict.get('solve_captcha', None),
        )
