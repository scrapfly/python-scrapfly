import base64
import json
import logging
from enum import Enum
from typing import Optional, List, Dict, Iterable, Union, Set
from urllib.parse import urlencode
from requests.structures import CaseInsensitiveDict
from .api_config import BaseApiConfig

class ScreenshotFlag(Enum):
    """
    Attributes:
        LOAD_IMAGES: Enable image rendering with the request, add extra usage for the bandwidth consumed.
        DARK_MODE: Enable dark mode display.
        BLOCK_BANNERS: Block cookies banners and overlay that cover the screen.
        HIGH_QUALITY: No compression on the output image.
        PRINT_MEDIA_FORMAT: Render the page in the print mode.
    """

    LOAD_IMAGES = "load_images"
    DARK_MODE = "dark_mode"
    BLOCK_BANNERS = "block_banners"
    HIGH_QUALITY = "high_quality"
    PRINT_MEDIA_FORMAT = "print_media_format"


class Format(Enum):
    """
    Attributes:
        JSON: JSON format.
        TEXT: Text format.
        MARKDOWN: Markdown format.
        CLEAN_HTML: Clean HTML format.
    """

    JSON = "json"
    TEXT = "text"
    MARKDOWN = "markdown"
    CLEAN_HTML = "clean_html"


class FormatOption(Enum):
    """
    Attributes:
        NO_IMAGES: exlude images from `markdown` format
        NO_LINKS: exlude links from `markdown` format
    """

    NO_IMAGES = "no_images"
    NO_LINKS = "no_links"



class ScrapeConfigError(Exception):
    pass


class ScrapeConfig(BaseApiConfig):

    PUBLIC_DATACENTER_POOL = 'public_datacenter_pool'
    PUBLIC_RESIDENTIAL_POOL = 'public_residential_pool'

    url: str
    retry: bool = True
    method: str = 'GET'
    country: Optional[str] = None
    render_js: bool = False
    cache: bool = False
    cache_clear:bool = False
    ssl:bool = False
    dns:bool = False
    asp:bool = False
    debug: bool = False
    raise_on_upstream_error:bool = True
    cache_ttl:Optional[int] = None
    proxy_pool:Optional[str] = None
    session: Optional[str] = None
    tags: Optional[List[str]] = None
    format: Optional[Format] = None, # raw(unchanged)
    correlation_id: Optional[str] = None
    cookies: Optional[CaseInsensitiveDict] = None
    body: Optional[str] = None
    data: Optional[Dict] = None
    headers: Optional[CaseInsensitiveDict] = None
    js: str = None
    rendering_wait: int = None
    wait_for_selector: Optional[str] = None
    session_sticky_proxy:bool = True
    screenshots:Optional[Dict]=None
    screenshot_flags: Optional[List[ScreenshotFlag]] = None,
    webhook:Optional[str]=None
    timeout:Optional[int]=None # in milliseconds
    js_scenario: Dict = None
    extract: Dict = None
    lang:Optional[List[str]] = None
    os:Optional[str] = None
    auto_scroll:Optional[bool] = None
    cost_budget:Optional[int] = None

    def __init__(
        self,
        url: str,
        retry: bool = True,
        method: str = 'GET',
        country: Optional[str] = None,
        render_js: bool = False,
        cache: bool = False,
        cache_clear:bool = False,
        ssl:bool = False,
        dns:bool = False,
        asp:bool = False,
        debug: bool = False,
        raise_on_upstream_error:bool = True,
        cache_ttl:Optional[int] = None,
        proxy_pool:Optional[str] = None,
        session: Optional[str] = None,
        tags: Optional[Union[List[str], Set[str]]] = None,
        format: Optional[Format] = None, # raw(unchanged)
        format_options: Optional[List[FormatOption]] = None, # raw(unchanged)
        correlation_id: Optional[str] = None,
        cookies: Optional[CaseInsensitiveDict] = None,
        body: Optional[str] = None,
        data: Optional[Dict] = None,
        headers: Optional[Union[CaseInsensitiveDict, Dict[str, str]]] = None,
        js: str = None,
        rendering_wait: int = None,
        wait_for_selector: Optional[str] = None,
        screenshots:Optional[Dict]=None,
        screenshot_flags: Optional[List[ScreenshotFlag]] = None,
        session_sticky_proxy:Optional[bool] = None,
        webhook:Optional[str] = None,
        timeout:Optional[int] = None, # in milliseconds
        js_scenario:Optional[List] = None,
        extract:Optional[Dict] = None,
        os:Optional[str] = None,
        lang:Optional[List[str]] = None,
        auto_scroll:Optional[bool] = None,
        cost_budget:Optional[int] = None
    ):
        assert(type(url) is str)

        if isinstance(tags, List):
            tags = set(tags)

        cookies = cookies or {}
        headers = headers or {}

        self.cookies = CaseInsensitiveDict(cookies)
        self.headers = CaseInsensitiveDict(headers)
        self.url = url
        self.retry = retry
        self.method = method
        self.country = country
        self.session_sticky_proxy = session_sticky_proxy
        self.render_js = render_js
        self.cache = cache
        self.cache_clear = cache_clear
        self.asp = asp
        self.webhook = webhook
        self.session = session
        self.debug = debug
        self.cache_ttl = cache_ttl
        self.proxy_pool = proxy_pool
        self.tags = tags or set()
        self.format = format
        self.format_options = format_options
        self.correlation_id = correlation_id
        self.wait_for_selector = wait_for_selector
        self.body = body
        self.data = data
        self.js = js
        self.rendering_wait = rendering_wait
        self.raise_on_upstream_error = raise_on_upstream_error
        self.screenshots = screenshots
        self.screenshot_flags = screenshot_flags
        self.key = None
        self.dns = dns
        self.ssl = ssl
        self.js_scenario = js_scenario
        self.timeout = timeout
        self.extract = extract
        self.lang = lang
        self.os = os
        self.auto_scroll = auto_scroll
        self.cost_budget = cost_budget

        if cookies:
            _cookies = []

            for name, value in cookies.items():
                _cookies.append(name + '=' + value)

            if 'cookie' in self.headers:
                if self.headers['cookie'][-1] != ';':
                    self.headers['cookie'] += ';'
            else:
                self.headers['cookie'] = ''

            self.headers['cookie'] += '; '.join(_cookies)

        if self.body and self.data:
            raise ScrapeConfigError('You cannot pass both parameters body and data. You must choose')

        if method in ['POST', 'PUT', 'PATCH']:
            if self.body is None and self.data is not None:
                if 'content-type' not in self.headers:
                    self.headers['content-type'] = 'application/x-www-form-urlencoded'
                    self.body = urlencode(data)
                else:
                    if self.headers['content-type'].find('application/json') != -1:
                        self.body = json.dumps(data)
                    elif self.headers['content-type'].find('application/x-www-form-urlencoded') != -1:
                        self.body = urlencode(data)
                    else:
                        raise ScrapeConfigError('Content-Type "%s" not supported, use body parameter to pass pre encoded body according to your content type' % self.headers['content-type'])
            elif self.body is None and self.data is None:
                self.headers['content-type'] = 'text/plain'

    def to_api_params(self, key:str) -> Dict:
        params = {
            'key': self.key or key,
            'url': self.url
        }

        if self.country is not None:
            params['country'] = self.country

        for name, value in self.headers.items():
            params['headers[%s]' % name] = value

        if self.webhook is not None:
            params['webhook_name'] = self.webhook

        if self.timeout is not None:
            params['timeout'] = self.timeout

        if self.extract is not None:
            params['extract'] = base64.urlsafe_b64encode(json.dumps(self.extract).encode('utf-8')).decode('utf-8')

        if self.cost_budget is not None:
            params['cost_budget'] = self.cost_budget

        if self.render_js is True:
            params['render_js'] = self._bool_to_http(self.render_js)

            if self.wait_for_selector is not None:
                params['wait_for_selector'] = self.wait_for_selector

            if self.js:
                params['js'] = base64.urlsafe_b64encode(self.js.encode('utf-8')).decode('utf-8')

            if self.js_scenario:
                params['js_scenario'] = base64.urlsafe_b64encode(json.dumps(self.js_scenario).encode('utf-8')).decode('utf-8')

            if self.rendering_wait:
                params['rendering_wait'] = self.rendering_wait

            if self.screenshots is not None:
                for name, element in self.screenshots.items():
                    params['screenshots[%s]' % name] = element

            if self.screenshot_flags is not None:
                self.screenshot_flags = [ScreenshotFlag(flag) for flag in self.screenshot_flags]
                params["screenshot_flags"] = ",".join(flag.value for flag in self.screenshot_flags)
            else:
                if self.screenshot_flags is not None:
                    logging.warning('Params "screenshot_flags" is ignored. Works only if screenshots is enabled')

            if self.auto_scroll is True:
                params['auto_scroll'] = self._bool_to_http(self.auto_scroll)
        else:
            if self.wait_for_selector is not None:
                logging.warning('Params "wait_for_selector" is ignored. Works only if render_js is enabled')

            if self.screenshots:
                logging.warning('Params "screenshots" is ignored. Works only if render_js is enabled')

            if self.js_scenario:
                logging.warning('Params "js_scenario" is ignored. Works only if render_js is enabled')

            if self.js:
                logging.warning('Params "js" is ignored. Works only if render_js is enabled')

            if self.rendering_wait:
                logging.warning('Params "rendering_wait" is ignored. Works only if render_js is enabled')

        if self.asp is True:
            params['asp'] = self._bool_to_http(self.asp)

        if self.retry is False:
            params['retry'] = self._bool_to_http(self.retry)

        if self.cache is True:
            params['cache'] = self._bool_to_http(self.cache)

            if self.cache_clear is True:
                params['cache_clear'] = self._bool_to_http(self.cache_clear)

            if self.cache_ttl is not None:
                params['cache_ttl'] = self.cache_ttl
        else:
            if self.cache_clear is True:
                logging.warning('Params "cache_clear" is ignored. Works only if cache is enabled')

            if self.cache_ttl is not None:
                logging.warning('Params "cache_ttl" is ignored. Works only if cache is enabled')

        if self.dns is True:
            params['dns'] = self._bool_to_http(self.dns)

        if self.ssl is True:
            params['ssl'] = self._bool_to_http(self.ssl)

        if self.tags:
            params['tags'] = ','.join(self.tags)

        if self.format:
            params['format'] = Format(self.format).value
            if self.format_options:
                params['format'] += ':' + ','.join(FormatOption(option).value for option in self.format_options)

        if self.correlation_id:
            params['correlation_id'] = self.correlation_id

        if self.session:
            params['session'] = self.session

            if self.session_sticky_proxy is True: # false by default
                params['session_sticky_proxy'] = self._bool_to_http(self.session_sticky_proxy)
        else:
            if self.session_sticky_proxy:
                logging.warning('Params "session_sticky_proxy" is ignored. Works only if session is enabled')

        if self.debug is True:
            params['debug'] = self._bool_to_http(self.debug)

        if self.proxy_pool is not None:
            params['proxy_pool'] = self.proxy_pool

        if self.lang is not None:
            params['lang'] = ','.join(self.lang)

        if self.os is not None:
            params['os'] = self.os

        return params

    @staticmethod
    def from_exported_config(config:str) -> 'ScrapeConfig':
        try:
            from msgpack import loads as msgpack_loads
        except ImportError as e:
            print('You must install msgpack package - run: pip install "scrapfly-sdk[seepdup] or pip install msgpack')
            raise

        data = msgpack_loads(base64.b64decode(config))

        headers = {}

        for name, value in data['headers'].items():
            if isinstance(value, Iterable):
                headers[name] = '; '.join(value)
            else:
                headers[name] = value

        return ScrapeConfig(
            url=data['url'],
            retry=data['retry'],
            headers=headers,
            session=data['session'],
            session_sticky_proxy=data['session_sticky_proxy'],
            cache=data['cache'],
            cache_ttl=data['cache_ttl'],
            cache_clear=data['cache_clear'],
            render_js=data['render_js'],
            method=data['method'],
            asp=data['asp'],
            body=data['body'],
            ssl=data['ssl'],
            dns=data['dns'],
            country=data['country'],
            debug=data['debug'],
            correlation_id=data['correlation_id'],
            tags=data['tags'],
            format=data['format'],
            js=data['js'],
            rendering_wait=data['rendering_wait'],
            screenshots=data['screenshots'] or {},
            screenshot_flags=data['screenshot_flags'],
            proxy_pool=data['proxy_pool'],
            auto_scroll=data['auto_scroll'],
            cost_budget=data['cost_budget']
        )
