import base64
import logging
from enum import Enum
from typing import Optional, List, Dict
from .api_config import BaseApiConfig

class Options(Enum):
    """
    Options to customize the screenshot behavior

    Attributes:
        LOAD_IMAGES: Enable image rendering with the request, add extra usage for the bandwidth consumed.
        DARK_MODE: Enable dark mode display.
        BLOCK_BANNERS: Block cookies banners and overlay that cover the screen.
        PRINT_MEDIA_FORMAT: Render the page in the print mode.
    """

    LOAD_IMAGES = "load_images"
    DARK_MODE = "dark_mode"
    BLOCK_BANNERS = "block_banners"
    PRINT_MEDIA_FORMAT = "print_media_format"


class Format(Enum):
    """
    Format of the screenshot image.

    Attributes:
        JPG: JPG format.
        PNG: PNG format.
        WEBP: WEBP format.
        GIF: GIF format.
    """

    JPG = "jpg"
    PNG = "png"
    WEBP = "webp"
    GIF = "gif"


class ScreenshotConfig(BaseApiConfig):
    url: str
    format: Optional[Format] = None
    capture: Optional[str] = None
    resolution: Optional[str] = None
    country: Optional[str] = None
    timeout: Optional[int] = None # in milliseconds
    rendering_wait: Optional[int] = None # in milliseconds
    wait_for_selector: Optional[str] = None
    options: Optional[List[Options]] = None
    auto_scroll: Optional[bool] = None
    js: Optional[str] = None
    cache: Optional[bool] = None
    cache_ttl: Optional[bool] = None
    cache_clear: Optional[bool] = None
    webhook: Optional[str] = None
    raise_on_upstream_error: bool = True

    def __init__(
        self,
        url: str,
        format: Optional[Format] = None,
        capture: Optional[str] = None,
        resolution: Optional[str] = None,
        country: Optional[str] = None,
        timeout: Optional[int] = None, # in milliseconds
        rendering_wait: Optional[int] = None, # in milliseconds
        wait_for_selector: Optional[str] = None,
        options: Optional[List[Options]] = None,
        auto_scroll: Optional[bool] = None,
        js: Optional[str] = None,
        cache: Optional[bool] = None,
        cache_ttl: Optional[bool] = None,
        cache_clear: Optional[bool] = None,
        webhook: Optional[str] = None,
        raise_on_upstream_error: bool = True
    ):
        assert(type(url) is str)

        self.url = url
        self.key = None
        self.format = format
        self.capture = capture
        self.resolution = resolution
        self.country = country
        self.timeout = timeout
        self.rendering_wait = rendering_wait
        self.wait_for_selector = wait_for_selector
        self.options = [Options(flag) for flag in options] if options else None
        self.auto_scroll = auto_scroll
        self.js = js
        self.cache = cache
        self.cache_ttl = cache_ttl
        self.cache_clear = cache_clear
        self.webhook = webhook
        self.raise_on_upstream_error = raise_on_upstream_error

    def to_api_params(self, key:str) -> Dict:
        params = {
            'key': self.key or key,
            'url': self.url
        }

        if self.format:
            params['format'] = Format(self.format).value

        if self.capture:
            params['capture'] = self.capture

        if self.resolution:
            params['resolution'] = self.resolution

        if self.country is not None:
            params['country'] = self.country

        if self.timeout is not None:
            params['timeout'] = self.timeout

        if self.rendering_wait is not None:
            params['rendering_wait'] = self.rendering_wait

        if self.wait_for_selector is not None:
            params['wait_for_selector'] = self.wait_for_selector            

        if self.options is not None:
            params["options"] = ",".join(flag.value for flag in self.options)

        if self.auto_scroll is not None:
            params['auto_scroll'] = self._bool_to_http(self.auto_scroll)

        if self.js:
            params['js'] = base64.urlsafe_b64encode(self.js.encode('utf-8')).decode('utf-8')

        if self.cache is not None:
            params['cache'] = self._bool_to_http(self.cache)
            
            if self.cache_ttl is not None:
                params['cache_ttl'] = self._bool_to_http(self.cache_ttl)

            if self.cache_clear is not None:
                params['cache_clear'] = self._bool_to_http(self.cache_clear)

        else:
            if self.cache_ttl is not None:
                logging.warning('Params "cache_ttl" is ignored. Works only if cache is enabled')

            if self.cache_clear is not None:
                logging.warning('Params "cache_clear" is ignored. Works only if cache is enabled')

        if self.webhook is not None:
            params['webhook_name'] = self.webhook

        return params

    def to_dict(self) -> Dict:
        """
        Export the ScreenshotConfig instance to a plain dictionary.
        """
        return {
            'url': self.url,
            'format': self.format.value if isinstance(self.format, Enum) else self.format,
            'capture': self.capture,
            'resolution': self.resolution,
            'country': self.country,
            'timeout': self.timeout,
            'rendering_wait': self.rendering_wait,
            'wait_for_selector': self.wait_for_selector,
            'options': [Options(option).value for option in self.options] if self.options else None,
            'auto_scroll': self.auto_scroll,
            'js': self.js,
            'cache': self.cache,
            'cache_ttl': self.cache_ttl,
            'cache_clear': self.cache_clear,
            'webhook': self.webhook,
            'raise_on_upstream_error': self.raise_on_upstream_error
        }
    
    @staticmethod
    def from_dict(screenshot_config_dict: Dict) -> 'ScreenshotConfig':
        """Create a ScreenshotConfig instance from a dictionary."""
        url = screenshot_config_dict.get('url', None)

        format = screenshot_config_dict.get('format', None)
        format = Format(format) if format else None

        capture = screenshot_config_dict.get('capture', None)
        resolution = screenshot_config_dict.get('resolution', None)
        country = screenshot_config_dict.get('country', None)
        timeout = screenshot_config_dict.get('timeout', None)
        rendering_wait = screenshot_config_dict.get('rendering_wait', None)
        wait_for_selector = screenshot_config_dict.get('wait_for_selector', None)

        options = screenshot_config_dict.get('options', None)
        options = [Options(option) for option in options] if options else None

        auto_scroll = screenshot_config_dict.get('auto_scroll', None)
        js = screenshot_config_dict.get('js', None)
        cache = screenshot_config_dict.get('cache', None)
        cache_ttl = screenshot_config_dict.get('cache_ttl', None)
        cache_clear = screenshot_config_dict.get('cache_clear', None)
        webhook = screenshot_config_dict.get('webhook', None)
        raise_on_upstream_error = screenshot_config_dict.get('raise_on_upstream_error', True)

        return ScreenshotConfig(
            url=url,
            format=format,
            capture=capture,
            resolution=resolution,
            country=country,
            timeout=timeout,
            rendering_wait=rendering_wait,
            wait_for_selector=wait_for_selector,
            options=options,
            auto_scroll=auto_scroll,
            js=js,
            cache=cache,
            cache_ttl=cache_ttl,
            cache_clear=cache_clear,
            webhook=webhook,
            raise_on_upstream_error=raise_on_upstream_error
        )
