import json
from base64 import b64encode
from os import getpid
from socket import gethostname
from threading import currentThread
from typing import Optional, List, Dict
from urllib.parse import urlencode

from requests.structures import CaseInsensitiveDict


class ScrapeConfigError(Exception):
    pass


class ScrapeConfig:

    def __init__(
            self,
            url: str,
            retry: bool = True,
            method: str = 'GET',
            country: Optional[str] = 'DE',
            render_js: bool = False,
            cache: bool = False,
            cache_clear:bool = False,
            ssl:bool = False,
            dns:bool = False,
            asp:bool = False,
            cache_ttl:Optional[int] = None,
            session: Optional[str] = None,
            debug: Optional[bool] = False,
            tags: Optional[List[str]] = None,
            correlation_id: Optional[str] = None,
            cookies: Optional[Dict] = None,
            body: Optional[str] = None,
            data: Optional[Dict] = None,
            headers: Optional[Dict[str, str]] = None,
            graphql: Optional[str] = None,
            js: str = None,
            rendering_wait: int = None,
            screenshots:Optional[Dict]=None,
            raise_on_upstream_error:bool=True
    ):
        assert(type(url) is str)

        self.cookies = CaseInsensitiveDict(cookies or {})
        self.headers = CaseInsensitiveDict(headers or {})
        self.url = url
        self.retry = retry
        self.method = method
        self.country = country
        self.render_js = render_js
        self.cache = cache
        self.cache_clear = cache_clear
        self.asp = asp
        self.session = session
        self.debug = debug
        self.cache_ttl = cache_ttl
        self.tags = tags
        self.correlation_id = correlation_id
        self.body = body
        self.data = data
        self.graphql = graphql
        self.js = js
        self.rendering_wait = rendering_wait
        self.raise_on_upstream_error = raise_on_upstream_error
        self.screenshots = screenshots
        self.key = None
        self.dns = dns
        self.ssl = ssl

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

        if method in ['POST', 'PUT', 'PATCH'] and self.body is None and self.data is not None:
            print(self.headers)
            if 'content-type' not in self.headers:
                self.headers['content-type'] = 'application/x-www-form-urlencoded'
                self.body = urlencode(data)
            else:
                if self.headers['content-type'] == 'application/json':
                    self.body = json.dumps(data)
                elif 'application/x-www-form-urlencoded' == self.headers['content-type']:
                    self.body = urlencode(data)
                else:
                    raise ScrapeConfigError('Content Type %s not support, use body parameter to pass pre encoded body according to your content type' % self.headers['content-type'])

    def _bool_to_http(self, _bool:bool) -> str:
        return 'true' if _bool is True else 'false'

    def generate_distributed_correlation_id(self):
        self.correlation_id = abs(hash('-'.join([gethostname(), str(getpid()), str(currentThread().ident)])))

    def to_api_params(self, key:str) -> Dict:
        params = {
            'key': self.key if self.key is not None else key,
            'url': self.url,
            'country': self.country,
        }

        for name, value in self.headers.items():
            params['headers[%s]' % name] = value

        if self.render_js is True:
            params['render_js'] = self._bool_to_http(self.render_js)

        if self.asp is True:
            params['asp'] = self._bool_to_http(self.asp)

        if self.retry is False:
            params['retry'] = self._bool_to_http(self.retry)

        if self.cache is True:
            params['cache'] = self._bool_to_http(self.cache)

        if self.dns is True:
            params['dns'] = self._bool_to_http(self.dns)

        if self.ssl is True:
            params['ssl'] = self._bool_to_http(self.ssl)

        if self.tags:
            params['tags'] = ','.join(self.tags)

        if self.correlation_id:
            params['correlation_id'] = self.correlation_id

        if self.screenshots is not None:
            for name, element in self.screenshots.items():
                params['screenshots[%s]' % name] = element

        if self.session:
            params['session'] = self.session

        if self.debug is True:
            params['debug'] = self._bool_to_http(self.debug)

        if self.cache_clear is True:
            params['cache_clear'] = self._bool_to_http(self.cache_clear)

        if self.cache_ttl is not None:
            params['cache_ttl'] = self.cache_ttl

        if self.graphql:
            params['graphql'] = self.graphql

        if self.js:
            params['js'] = b64encode(self.js.encode('utf-8')).decode('utf-8')

        if self.rendering_wait:
            params['rendering_wait'] = self.rendering_wait

        return params
