import json
from base64 import b64decode
from contextlib import suppress
from datetime import datetime
from functools import partial
from http.cookiejar import Cookie
from http.cookies import SimpleCookie
from io import BytesIO
from json import JSONDecoder

from dateutil.parser import parse
from requests import Request, Response
from typing import Dict, Optional, Iterable

from requests.structures import CaseInsensitiveDict

from .scrape_config import ScrapeConfig
from .errors import ErrorFactory, UpstreamHttpClientError
from .frozen_dict import FrozenDict

_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'


def _date_parser(value):
    if isinstance(value, Dict):
        over = value.items()
    else:
        over = enumerate(value)

    for k, v in over:
        if isinstance(v, str):
            if len(v) <= 26:
                try:
                    value[k] = datetime.strptime(v, _DATE_FORMAT)
                except ValueError:
                    value[k] = v
            else:
                value[k] = v
        elif isinstance(v, Iterable):
            value[k] = _date_parser(v)
        else:
            value[k] = v

    return value


class ResponseBodyHandler:

    SUPPORTED_COMPRESSION = ['gzip', 'deflate']

    class JSONDateTimeDecoder(JSONDecoder):
        def __init__(self, *args, **kargs):
            JSONDecoder.__init__(self, *args, object_hook=_date_parser, **kargs)

    def __init__(self):
        try:
            import brotli
            #  insert brotli as preferred choice. Be aware brotli is cpu bursting. Not always best choice regarding your hardware
            self.SUPPORTED_COMPRESSION.insert(0, 'br')
        except BaseException:
            pass

        self.content_encoding = ', '.join(self.SUPPORTED_COMPRESSION)

        try:  # automatically use msgpack if available https://msgpack.org/
            import msgpack
            self.accept = 'application/msgpack'
            self.content_type = 'application/msgpack'
            self.content_loader = partial(msgpack.loads, object_hook=_date_parser, strict_map_key=False)
        except ImportError:
            self.accept = 'application/json;charset=utf-8'
            self.content_type = 'application/json;charset=utf-8'
            self.content_loader = partial(json.loads, cls=self.JSONDateTimeDecoder)

    def __call__(self, content:bytes) -> str:
        return self.content_loader(content)


class ScrapeApiResponse:

    def __init__(self, request:Request, response:Response, scrape_config:ScrapeConfig, api_result:Optional[Dict]=None):
        self.request = request
        self.response = response
        self.scrape_config = scrape_config
        self.result = self.handle_api_result(api_result=api_result)

    @property
    def scrape_result(self):
        return self.result['result']

    @property
    def config(self) -> Dict:
        return self.result['config']

    @property
    def context(self) -> Dict:
        return self.result['context']

    def content(self) -> Dict:
        return self.result

    def handle_api_result(self, api_result:Optional[Dict]) -> Optional[FrozenDict]:
        if api_result is None:
            return None

        if self._is_api_error(api_result=api_result) is True:
            return FrozenDict(api_result)

        if isinstance(api_result['config']['headers'], list):
            api_result['config']['headers'] = {}

        with suppress(KeyError):
            api_result['result']['request_headers'] = CaseInsensitiveDict(api_result['result']['request_headers'])
            api_result['result']['response_headers'] = CaseInsensitiveDict(api_result['result']['response_headers'])

        if api_result['result']['format'] == 'binary' and api_result['result']['content']:
            api_result['result']['content'] = BytesIO(b64decode(api_result['result']['content']))

        return FrozenDict(api_result)

    def _is_scrape_engine_error(self, api_result:Optional[Dict]=None) -> bool:
        if api_result is None:
            return False

        if 'result' not in api_result:
            return False

        try:
            return api_result['result']['error'] is not None
        except KeyError:
            return False

    @property
    def is_scrape_engine_error(self) -> bool:
        return self._is_scrape_engine_error(self.result)

    def _is_api_error(self, api_result:Dict) -> bool:
        if api_result is None:
            return True

        return 'error_id' in api_result

    @property
    def is_api_error(self) -> bool:
        return self._is_api_error(self.result)

    def raise_for_result(self, raise_on_upstream_error:bool=True):
        if self.is_api_error is True:
            raise ErrorFactory.create(api_response=self)

        if self.is_scrape_engine_error is True:
            error = ErrorFactory.create(api_response=self)

            if isinstance(error, UpstreamHttpClientError) is True:
                if raise_on_upstream_error is True:
                    raise error
            else:
                raise error

    # /!\ Success means scrapfly api reply correctly to the call, but the scrape can be unsuccessful if the upstream reply with error status code
    @property
    def success(self) -> bool:
        return self.is_scrape_engine_error is False and self.is_api_error is False

    @property
    def status_code(self) -> bool:
        return self.response.status_code

    @property
    def headers(self) -> CaseInsensitiveDict:
        return self.response.headers

    def upstream_result_into_response(self, _class=Response) -> Optional[Response]:
        if _class != Response:
            raise RuntimeError('only Response from requests package is supported at the moment')
        if self.result is None:
            return None

        if self.is_scrape_engine_error is True: # Upstream website must have reply
            return None

        response = Response()

        response.status_code = self.result['result']['status_code']
        response.reason = self.result['result']['reason']
        response._content = self.result['result']['content'].encode('utf-8') if self.result['result']['content'] else None
        response.headers.update(self.result['result']['response_headers'])
        response.url = self.result['result']['url']

        response.request = Request(
            method=self.result['config']['method'],
            url=self.result['config']['url'],
            headers=self.result['result']['request_headers'],
            data=self.result['config']['body'] if self.result['config']['body'] else None
        )

        if 'set-cookie' in response.headers:
            for raw_cookie in response.headers['set-cookie']:
                for name, cookie in SimpleCookie(raw_cookie).items():
                    expires = cookie.get('expires')

                    if expires == '':
                        expires = None

                    if expires:
                        try:
                            expires = parse(expires).timestamp()
                        except ValueError:
                            expires = None

                    if type(expires) == str:
                        if '.' in expires:
                            expires = float(expires)
                        else:
                            expires = int(expires)

                    response.cookies.set_cookie(Cookie(
                        version=cookie.get('version') if cookie.get('version') else None,
                        name=name,
                        value=cookie.value,
                        path=cookie.get('path', ''),
                        expires=expires,
                        comment=cookie.get('comment'),
                        domain=cookie.get('domain', ''),
                        secure=cookie.get('secure'),
                        port=None,
                        port_specified=False,
                        domain_specified=cookie.get('domain') is not None and cookie.get('domain') != '',
                        domain_initial_dot=bool(cookie.get('domain').startswith('.')) if cookie.get('domain') is not None else False,
                        path_specified=cookie.get('path') != '' and cookie.get('path') is not None,
                        discard=False,
                        comment_url=None,
                        rest={
                            'httponly': cookie.get('httponly'),
                            'samesite': cookie.get('samesite'),
                            'max-age': cookie.get('max-age')
                        }
                    ))

        return response
