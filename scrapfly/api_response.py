import base64
import binascii
import hashlib
import hmac
import re
import logging as logger
import shutil

from base64 import b64decode
from contextlib import suppress
from datetime import datetime
from functools import partial

try:
    from functools import cached_property
except ImportError:
    from .polyfill.cached_property import cached_property

from http.cookiejar import Cookie
from http.cookies import SimpleCookie
from io import BytesIO
from json import JSONDecoder, loads

from dateutil.parser import parse
from requests import Request, Response, HTTPError
from typing import List, Dict, Optional, Iterable, Union, TextIO, Tuple

from requests.structures import CaseInsensitiveDict

from .scrape_config import ScrapeConfig
from .screenshot_config import ScreenshotConfig
from .extraction_config import ExtractionConfig
from .errors import ErrorFactory, ScreenshotAPIError, ExtractionAPIError, EncoderError, ApiHttpClientError, ApiHttpServerError, UpstreamHttpError, HttpError, \
    ExtraUsageForbidden, WebhookSignatureMissMatch
from .frozen_dict import FrozenDict

logger.getLogger(__name__)

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

    # brotli under perform at same gzip level and upper level destroy the cpu so
    # the trade off do not worth it for most of usage
    def __init__(self, use_brotli: bool = False, signing_secrets: Optional[Tuple[str]] = None):
        if use_brotli is True and 'br' not in self.SUPPORTED_COMPRESSION:
            try:
                try:
                    import brotlicffi as brotli
                    self.SUPPORTED_COMPRESSION.insert(0, 'br')
                except ImportError:
                    import brotli
                    self.SUPPORTED_COMPRESSION.insert(0, 'br')
            except ImportError:
                pass

        try:
            import zstd
            self.SUPPORTED_COMPRESSION.append('zstd')
        except ImportError:
            pass

        self.content_encoding: str = ', '.join(self.SUPPORTED_COMPRESSION)
        self._signing_secret: Optional[Tuple[str]] = None

        if signing_secrets:
            _secrets = set()

            for signing_secret in signing_secrets:
                _secrets.add(binascii.unhexlify(signing_secret))

            self._signing_secret = tuple(_secrets)

        try:  # automatically use msgpack if available https://msgpack.org/
            import msgpack
            self.accept = 'application/msgpack;charset=utf-8'
            self.content_type = 'application/msgpack;charset=utf-8'
            self.content_loader = partial(msgpack.loads, object_hook=_date_parser, strict_map_key=False)
        except ImportError:
            self.accept = 'application/json;charset=utf-8'
            self.content_type = 'application/json;charset=utf-8'
            self.content_loader = partial(loads, cls=self.JSONDateTimeDecoder)

    def support(self, headers: Dict) -> bool:
        if 'content-type' not in headers:
            return False

        for content_type in self.SUPPORTED_CONTENT_TYPES:
            if headers['content-type'].find(content_type) != -1:
                return True

        return False

    def verify(self, message: bytes, signature: str) -> bool:
        for signing_secret in self._signing_secret:
            if hmac.new(signing_secret, message, hashlib.sha256).hexdigest().upper() == signature:
                return True

        return False

    def read(self, content: bytes, content_encoding: str, content_type: str, signature: Optional[str]) -> Dict:
        if content_encoding == 'gzip' or content_encoding == 'gz':
            import gzip
            content = gzip.decompress(content)
        elif content_encoding == 'deflate':
            import zlib
            content = zlib.decompress(content)
        elif content_encoding == 'brotli' or content_encoding == 'br':
            import brotli
            content = brotli.decompress(content)
        elif content_encoding == 'zstd':
            import zstd
            content = zstd.decompress(content)

        if self._signing_secret is not None and signature is not None:
            if not self.verify(content, signature):
                raise WebhookSignatureMissMatch()

        if content_type.startswith('application/json'):
            content = loads(content, cls=self.JSONDateTimeDecoder)
        elif content_type.startswith('application/msgpack'):
            import msgpack
            content = msgpack.loads(content, object_hook=_date_parser, strict_map_key=False)

        return content

    def __call__(self, content: bytes, content_type: str) -> Union[str, Dict]:
        content_loader = None

        if content_type.find('application/json') != -1:
            content_loader = partial(loads, cls=self.JSONDateTimeDecoder)
        elif content_type.find('application/msgpack') != -1:
            import msgpack
            content_loader = partial(msgpack.loads, object_hook=_date_parser, strict_map_key=False)

        if content_loader is None:
            raise Exception('Unsupported content type')

        try:
            return content_loader(content)
        except Exception as e:
            try:
                raise EncoderError(content=content.decode('utf-8')) from e
            except UnicodeError:
                raise EncoderError(content=base64.b64encode(content).decode('utf-8')) from e


class ApiResponse:
    def __init__(self, request: Request, response: Response):
        self.request = request
        self.response = response

    @property
    def headers(self) -> CaseInsensitiveDict:
        return self.response.headers

    @property
    def status_code(self) -> int:
        """
            /!\ This is the status code of our API, not the upstream website
        """
        return self.response.status_code

    @property
    def remaining_quota(self) -> Optional[int]:
        remaining_scrape = self.response.headers.get('X-Scrapfly-Remaining-Scrape')

        if remaining_scrape:
            remaining_scrape = int(remaining_scrape)

        return remaining_scrape

    @property
    def cost(self) -> Optional[int]:
        cost = self.response.headers.get('X-Scrapfly-Api-Cost')

        if cost:
            cost = int(cost)

        return cost

    @property
    def duration_ms(self) -> Optional[float]:
        duration = self.response.headers.get('X-Scrapfly-Response-Time')

        if duration:
            duration = float(duration)

        return duration

    @property
    def error_message(self):
        if self.error is not None:
            message = "<-- %s | %s - %s." % (self.response.status_code, self.error['code'], self.error['message'])

            if self.error['links']:
                message += " Checkout the related doc: %s" % list(self.error['links'].values())[0]

            return message

        message = "<-- %s | %s." % (self.response.status_code, self.result['message'])

        if self.result.get('links'):
            message += " Checkout the related doc: %s" % ", ".join(self.result['links'])

        return message

    def prevent_extra_usage(self):
        if self.remaining_quota == 0:
            raise ExtraUsageForbidden(
                message='All Pre Paid Quota Used',
                code='ERR::ACCOUNT::PREVENT_EXTRA_USAGE',
                http_status_code=429,
                is_retryable=False
            )

    def raise_for_result(
        self, raise_on_upstream_error: bool, error_class: Union[ApiHttpClientError, ScreenshotAPIError, ExtractionAPIError]
    ):
        try:
            self.response.raise_for_status()
        except HTTPError as e:
            if 'error_id' in self.result:
                if e.response.status_code >= 500:
                    raise ApiHttpServerError(
                        request=e.request,
                        response=e.response,
                        message=self.result['message'],
                        code='',
                        resource='',
                        http_status_code=e.response.status_code,
                        documentation_url=self.result.get('links'),
                        api_response=self,
                    ) from e
                # respect raise_on_upstream_error with screenshot and extraction only
                elif error_class in (ScreenshotAPIError, ExtractionAPIError):
                    if raise_on_upstream_error:
                        raise error_class(
                            request=e.request,
                            response=e.response,
                            message=self.result['message'],
                            code='',
                            resource='API',
                            http_status_code=self.result['http_code'],
                            documentation_url=self.result.get('links'),
                            api_response=self,
                        ) from e
                else:
                    raise error_class(
                        request=e.request,
                        response=e.response,
                        message=self.result['message'],
                        code='',
                        resource='API',
                        http_status_code=self.result['http_code'],
                        documentation_url=self.result.get('links'),
                        api_response=self,
                    ) from e


class ScrapeApiResponse(ApiResponse):
    def __init__(self, request: Request, response: Response, scrape_config: ScrapeConfig, api_result: Optional[Dict] = None):
        super().__init__(request, response)
        self.scrape_config = scrape_config

        if self.scrape_config.method == 'HEAD':
            api_result = {
                'result': {
                    'request_headers': {},
                    'status': 'DONE',
                    'success': 200 >= self.response.status_code < 300,
                    'response_headers': self.response.headers,
                    'status_code': self.response.status_code,
                    'reason': self.response.reason,
                    'format': 'text',
                    'content': ''
                },
                'context': {},
                'config': self.scrape_config.__dict__
            }

            if 'X-Scrapfly-Reject-Code' in self.response.headers:
                api_result['result']['error'] = {
                    'code': self.response.headers['X-Scrapfly-Reject-Code'],
                    'http_code': int(self.response.headers['X-Scrapfly-Reject-Http-Code']),
                    'message': self.response.headers['X-Scrapfly-Reject-Description'],
                    'error_id': self.response.headers['X-Scrapfly-Reject-ID'],
                    'retryable': True if self.response.headers['X-Scrapfly-Reject-Retryable'] == 'yes' else False,
                    'doc_url': '',
                    'links': {}
                }

                if 'X-Scrapfly-Reject-Doc' in self.response.headers:
                    api_result['result']['error']['doc_url'] = self.response.headers['X-Scrapfly-Reject-Doc']
                    api_result['result']['error']['links']['Related Docs'] = self.response.headers['X-Scrapfly-Reject-Doc']

        if isinstance(api_result, str):
            raise HttpError(
                request=request,
                response=response,
                message='Bad gateway',
                code=502,
                http_status_code=502,
                is_retryable=True
            )

        self.result = self.handle_api_result(api_result=api_result)

    @property
    def scrape_result(self) -> Optional[Dict]:
        return self.result.get('result', None)

    @property
    def scrape_result(self) -> Optional[Dict]:
        return self.result.get('result', None)

    @property
    def config(self) -> Optional[Dict]:
        if self.scrape_result is None:
            return None

        return self.result['config']

    @property
    def context(self) -> Optional[Dict]:
        if self.scrape_result is None:
            return None

        return self.result['context']

    @property
    def content(self) -> str:
        if self.scrape_result is None:
            return ''

        return self.scrape_result['content']

    @property
    def success(self) -> bool:
        """
            /!\ Success means Scrapfly api reply correctly to the call, but the scrape can be unsuccessful if the upstream reply with error status code
        """
        return 200 >= self.response.status_code <= 299

    @property
    def scrape_success(self) -> bool:
        scrape_result = self.scrape_result

        if not scrape_result:
            return False

        return self.scrape_result['success']

    @property
    def error(self) -> Optional[Dict]:
        if self.scrape_result is None:
            return None

        if self.scrape_success is False:
            return self.scrape_result['error']

    @property
    def upstream_status_code(self) -> Optional[int]:
        if self.scrape_result is None:
            return None

        if 'status_code' in self.scrape_result:
            return self.scrape_result['status_code']

        return None

    @cached_property
    def soup(self) -> 'BeautifulSoup':
        try:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(self.content, "lxml")
            return soup
        except ImportError as e:
            logger.error('You must install scrapfly[parser] to enable this feature')

    @cached_property
    def selector(self) -> 'Selector':
        try:
            from parsel import Selector
            return Selector(text=self.content)
        except ImportError as e:
            logger.error('You must install parsel or scrapy package to enable this feature')
            raise e

    def handle_api_result(self, api_result: Dict) -> Optional[FrozenDict]:
        if self._is_api_error(api_result=api_result) is True:
            return FrozenDict(api_result)

        try:
            if isinstance(api_result['config']['headers'], list):
                api_result['config']['headers'] = {}
        except TypeError:
            logger.info(api_result)
            raise

        with suppress(KeyError):
            api_result['result']['request_headers'] = CaseInsensitiveDict(api_result['result']['request_headers'])
            api_result['result']['response_headers'] = CaseInsensitiveDict(api_result['result']['response_headers'])

        if api_result['result']['format'] == 'binary' and api_result['result']['content']:
            api_result['result']['content'] = BytesIO(b64decode(api_result['result']['content']))

        return FrozenDict(api_result)

    def _is_api_error(self, api_result: Dict) -> bool:
        if self.scrape_config.method == 'HEAD':
            if 'X-Reject-Reason' in self.response.headers:
                return True
            return False

        if api_result is None:
            return True

        return 'error_id' in api_result

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

        if self.scrape_result['content']:
            if isinstance(self.scrape_result['content'], BytesIO):
                response._content = self.scrape_result['content'].getvalue()
            elif isinstance(self.scrape_result['content'], bytes):
                response._content = self.scrape_result['content']
            elif isinstance(self.scrape_result['content'], str):
                response._content = self.scrape_result['content'].encode('utf-8')
        else:
            response._content = None

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

    def sink(self, path: Optional[str] = None, name: Optional[str] = None, file: Optional[Union[TextIO, BytesIO]] = None, content: Optional[Union[str, bytes]] = None):
        file_content = content or self.scrape_result['content']
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

            file_path = path + '/' + name if path is not None else name

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

    def raise_for_result(self, raise_on_upstream_error=True, error_class=ApiHttpClientError):
        super().raise_for_result(raise_on_upstream_error=raise_on_upstream_error, error_class=error_class)
        if self.result['result']['status'] == 'DONE' and self.scrape_success is False:
            error = ErrorFactory.create(api_response=self)
            if error:
                if isinstance(error, UpstreamHttpError):
                    if raise_on_upstream_error is True:
                        raise error
                else:
                    raise error


class ScreenshotApiResponse(ApiResponse):
    def __init__(self, request: Request, response: Response, screenshot_config: ScreenshotConfig, api_result: Optional[bytes] = None):
        super().__init__(request, response)
        self.screenshot_config = screenshot_config
        self.result = self.handle_api_result(api_result)

    @property
    def image(self) -> Optional[str]:
        binary = self.result.get('result', None)
        if binary is None:
            return ''

        return binary

    @property
    def metadata(self) -> Optional[Dict]:
        if not self.image:
            return {}

        content_type = self.response.headers.get('content-type')
        extension_name = content_type[content_type.find('/') + 1:].split(';')[0]

        return {
            'extension_name': extension_name,
            'upstream-status-code': self.response.headers.get('X-Scrapfly-Upstream-Http-Code'),
            'upstream-url': self.response.headers.get('X-Scrapfly-Upstream-Url')
        }

    @property
    def screenshot_success(self) -> bool:
        if not self.image:
            return False

        return True

    @property
    def error(self) -> Optional[Dict]:
        if self.image:
            return None

        if self.screenshot_success is False:
            return self.result

    def _is_api_error(self, api_result: Dict) -> bool:
        if api_result is None:
            return True

        return 'error_id' in api_result

    def handle_api_result(self, api_result: bytes) -> FrozenDict:
        if self._is_api_error(api_result=api_result) is True:
            return FrozenDict(api_result)

        return api_result

    def raise_for_result(self, raise_on_upstream_error=True, error_class=ScreenshotAPIError):
        super().raise_for_result(raise_on_upstream_error=raise_on_upstream_error, error_class=error_class)


class ExtractionApiResponse(ApiResponse):
    def __init__(self, request: Request, response: Response, extraction_config: ExtractionConfig, api_result: Optional[bytes] = None):
        super().__init__(request, response)
        self.extraction_config = extraction_config
        self.result = self.handle_api_result(api_result)

    @property
    def extraction_result(self) -> Optional[Dict]:
        extraction_result = self.result.get('result', None)
        if not extraction_result:  # handle empty extraction responses
            return {'data': None, 'content_type': None}
        else:
            return extraction_result

    @property
    def data(self) -> Union[Dict, List, str]:  # depends on the LLM prompt
        if self.error is None:
            return self.extraction_result['data']

        return None

    @property
    def content_type(self) -> Optional[str]:
        if self.error is None:
            return self.extraction_result['content_type']

        return None

    @property
    def extraction_success(self) -> bool:
        extraction_result = self.extraction_result
        if extraction_result is None or extraction_result['data'] is None:
            return False

        return True

    @property
    def error(self) -> Optional[Dict]:
        if self.extraction_result is None:
            return self.result

        return None

    def _is_api_error(self, api_result: Dict) -> bool:
        if api_result is None:
            return True

        return 'error_id' in api_result

    def handle_api_result(self, api_result: bytes) -> FrozenDict:
        if self._is_api_error(api_result=api_result) is True:
            return FrozenDict(api_result)

        return FrozenDict({'result': api_result})

    def raise_for_result(self, raise_on_upstream_error=True, error_class=ExtractionAPIError):
        super().raise_for_result(raise_on_upstream_error=raise_on_upstream_error, error_class=error_class)
