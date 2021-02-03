import re
import logging as logger
import shutil

from base64 import b64decode
from contextlib import suppress
from datetime import datetime
from functools import partial, cached_property
from http.cookiejar import Cookie
from http.cookies import SimpleCookie
from io import BytesIO
from json import JSONDecoder, loads

from dateutil.parser import parse
from requests import Request, Response
from typing import Dict, Optional, Iterable, Union, TextIO

from requests.structures import CaseInsensitiveDict

from .scrape_config import ScrapeConfig
from .errors import ErrorFactory, UpstreamHttpClientError, EncoderError
from .frozen_dict import FrozenDict

logger.getLogger('scrapfly')

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
    SUPPORTED_CONTENT_TYPES = ['application/msgpack', 'application/json']

    class JSONDateTimeDecoder(JSONDecoder):
        def __init__(self, *args, **kargs):
            JSONDecoder.__init__(self, *args, object_hook=_date_parser, **kargs)

    def __init__(self):
        try:
            import brotli
            self.SUPPORTED_COMPRESSION.insert(0, 'br')
        except ImportError:
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
            self.content_loader = partial(loads, cls=self.JSONDateTimeDecoder)

    def support(self, headers:Dict) -> bool:
        if 'content-type' not in headers:
            return False

        for content_type in self.SUPPORTED_CONTENT_TYPES:
            if headers['content-type'].find(content_type) != -1:
                return True

        return False

    def __call__(self, content: bytes) -> Union[str, Dict]:
        try:
            return self.content_loader(content)
        except Exception as e:
            raise EncoderError(content=content.decode('utf-8')) from e


class ScrapeApiResponse:

    def __init__(self, request: Request, response: Response, scrape_config: ScrapeConfig, api_result: Optional[Dict] = None):
        self.request = request
        self.response = response
        self.scrape_config = scrape_config
        self.result = self.handle_api_result(api_result=api_result)

    @property
    def scrape_result(self) -> Dict:
        return self.result['result']

    @property
    def config(self) -> Dict:
        return self.result['config']

    @property
    def context(self) -> Dict:
        return self.result['context']

    @property
    def content(self) -> str:
        return self.scrape_result['content']

    @property
    def success(self) -> bool:
        """
            /!\ Success means Scrapfly api reply correctly to the call, but the scrape can be unsuccessful if the upstream reply with error status code
        """
        return 200 >= self.response.status_code <= 299

    @property
    def scrape_success(self) -> bool:
        return self.scrape_result['success']

    @property
    def error(self) -> Optional[Dict]:
        if self.scrape_success is False:
            return self.scrape_result['error']

    @property
    def status_code(self) -> int:
        return self.response.status_code

    @property
    def headers(self) -> CaseInsensitiveDict:
        return self.response.headers

    def handle_api_result(self, api_result: Optional[Dict]) -> Optional[FrozenDict]:
        if not api_result and self.scrape_config.method != 'HEAD':
            return None

        if self.scrape_config.method == 'HEAD':
            api_result = {
                'result': {
                    'request_headers': {},
                    'response_headers': self.response.headers,
                    'status_code': self.response.status_code,
                    'reason': self.response.reason,
                    'format': 'text',
                    'content': ''
                },
                'context': {},
                'config': self.scrape_config.__dict__
            }

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

    @cached_property
    def selector(self):
        try:
            from scrapy import Selector
            return Selector(text=self.content)
        except ImportError as e:
            logger.error('You must install scrapfly[scrapy] to enable this feature')
            raise e

    def _is_api_error(self, api_result: Dict) -> bool:
        if self.scrape_config.method == 'HEAD':
            if 'X-Reject-Reason' in self.response.headers:
                return True
            return False

        if api_result is None:
            return True

        return 'error_id' in api_result

    def raise_for_result(self, raise_on_upstream_error: bool = True):
        self.response.raise_for_status()

        if self.scrape_success is False:
            error = ErrorFactory.create(api_response=self)

            if error:
                if isinstance(error, UpstreamHttpClientError):
                    if raise_on_upstream_error is True:
                        raise error
                else:
                    raise error

    def upstream_result_into_response(self, _class=Response) -> Optional[Response]:
        if _class != Response:
            raise RuntimeError('only Response from requests package is supported at the moment')

        if self.result is None:
            return None

        if self.response.status_code != 200:
            return None

        response = Response()
        response.status_code = self.scrape_result['status_code']
        response.reason = self.scrape_result['reason']
        response._content = self.scrape_result['content'].encode('utf-8') if self.scrape_result['content'] else None
        response.headers.update(self.scrape_result['response_headers'])
        response.url = self.scrape_result['url']

        response.request = Request(
            method=self.config['method'],
            url=self.config['url'],
            headers=self.scrape_result['request_headers'],
            data=self.config['body'] if self.config['body'] else None
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

    def sink(self, path: Optional[str] = None, name: Optional[str] = None, file: Optional[Union[TextIO, BytesIO]] = None):
        file_content = self.scrape_result['content']
        file_path = None
        file_extension = None

        if name:
            name_parts = name.split('.')
            if len(name_parts) > 1:
                file_extension = name_parts[-1]

        if not file:
            if file_extension is None:
                try:
                    mime_type = self.scrape_result['response_headers']['content-type']
                except KeyError:
                    mime_type = 'application/octet-stream'

                if ';' in mime_type:
                    mime_type = mime_type.split(';')[0]

                file_extension = '.' + mime_type.split('/')[1]

            if not name:
                name = self.config['url'].split('/')[-1]

            if name.find(file_extension) == -1:
                name += file_extension

            file_path = path + '/' + name if path else name

            if file_path == file_extension:
                url = re.sub(r'(https|http)?://', '', self.config['url']).replace('/', '-')

                if url[-1] == '-':
                    url = url[:-1]

                url += file_extension

                file_path = url

            file = open(file_path, 'wb')

        if isinstance(file_content, str):
            file_content = BytesIO(file_content.encode('utf-8'))
        elif isinstance(file_content, bytes):
            file_content = BytesIO(file_content)

        file_content.seek(0)
        with file as f:
            shutil.copyfileobj(file_content, f, length=131072)

        logger.info('file %s created' % file_path)
