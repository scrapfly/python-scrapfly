import http
import platform
import re
import shutil
from functools import partial
from io import BytesIO
from typing import TextIO, Union
import requests
import urllib3

from loguru import logger

from .retry import retry
from .errors import *
from .api_response import ResponseBodyHandler
from .scrape_config import ScrapeConfig
from . import __version__ as version, ScrapeApiResponse


class ScrapflyClient:

    HOST = 'https://api.scrapfly.io'
    DEFAULT_CONNECT_TIMEOUT = 30
    DEFAULT_READ_TIMEOUT = 300

    def __init__(
        self,
        key: str,
        host: Optional[str] = HOST,
        verify=True,
        debug: bool = False,
        distributed_mode = False,
        connect_timeout:int = DEFAULT_CONNECT_TIMEOUT,
        read_timeout:int = DEFAULT_READ_TIMEOUT
    ):
        if host[-1] == '/':  # remove last '/' if exists
            host = host[:-1]

        self.host = host
        self.key = key
        self.verify = verify
        self.debug = debug
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.distributed_mode = distributed_mode
        self.body_handler = ResponseBodyHandler()
        self.http_session = None
        self.ua = 'ScrapflySDK/%s (Python %s, %s, %s)' % (
            version,
            platform.python_version(),
            platform.uname().system,
            platform.uname().machine
        )

        if not self.verify and not self.HOST.endswith('.local'):
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        if self.debug is True:
            http.client.HTTPConnection.debuglevel = 5

    def _scrape_request(self, scrape_config:ScrapeConfig):

        if not scrape_config.graphql:
            url = self.host + '/scrape'
            method = scrape_config.method
        else:
            url = self.host + '/graphql'
            method = 'POST'

        if self.distributed_mode is True and scrape_config.correlation_id is None:
            scrape_config.generate_distributed_correlation_id()

        http_handler = partial(self.http_session.request if self.http_session else requests.request)

        r = http_handler(
            method=method,
            url=url,
            data=scrape_config.body,
            verify=self.verify,
            timeout=(self.connect_timeout, self.read_timeout),
            headers={
                'content-type': scrape_config.headers['content-type'] if method in ['POST', 'PUT', 'PATCH'] else self.body_handler.content_type,
                'accept-encoding': self.body_handler.content_encoding,
                'accept': self.body_handler.accept,
                'user-agent': self.ua
            },
            params=scrape_config.to_api_params(key=self.key)
        )

        return r

    def account(self) -> Dict:
        http_handler = partial(self.http_session.request if self.http_session else requests.request)
        return http_handler('GET', self.host + '/account', params={'key': self.key}).json()

    def resilient_scrape(
        self,
        scrape_config:ScrapeConfig,
        retry_on_errors:Union[Exception, Tuple[Exception, ...]]=None,
        tries: int = 5,
        delay: int = 20,
    ) -> ScrapeApiResponse:
        if retry_on_errors is None:
            retry_on_errors = [ScrapflyError]  # Retry on all retryable error from Scrapfly

        @retry(retry_on_errors, tries=tries, delay=delay)
        def inner() -> ScrapeApiResponse:
            return self.scrape(scrape_config=scrape_config)

        return inner()

    def __enter__(self) -> 'ScrapflyClient':
        if self.http_session is None:
            self.http_session = requests.session()
            self.http_session.params['key'] = self.key

            self.http_session.headers['accept-encoding'] = self.body_handler.content_encoding
            self.http_session.headers['accept'] = self.body_handler.accept
            self.http_session.headers['user-agent'] = self.ua

        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.http_session.close()
        self.http_session = None

    @retry((ConnectionError,), tries=5, delay=2)
    def scrape(self, scrape_config:ScrapeConfig) -> ScrapeApiResponse:
        logger.info('--> %s Scrapping %s' % (scrape_config.method, scrape_config.url))

        response = self._scrape_request(scrape_config=scrape_config)

        try:
            api_response = self._handle_api_response(response=response, scrape_config=scrape_config, raise_on_upstream_error=scrape_config.raise_on_upstream_error)
            logger.info('<-- [%s %s] %s | %ss' % (
                api_response.result['result']['status_code'],
                api_response.result['result']['reason'],
                api_response.result['config']['url'],
                api_response.result['result']['duration'])
            )

            return api_response
        except ApiHttpServerError as e:
            logger.critical('<-- %s - %s' % (e.response.status_code, str(e)))
            raise
        except UpstreamHttpServerError as e:
            logger.warning('<-- %s - %s | %s' % (e.code, str(e), e.api_response.result['result']['url']))
            raise
        except ScrapflyError as e:
            logger.critical('<-- %s - %s' % (e.code, str(e)))
            raise

    def screenshot(self, url:str, path:Optional[str]=None, name:Optional[str]=None):
        # for advance configuration, take screenshots via scrape method with ScrapeConfig
        api_response = self.scrape(scrape_config=ScrapeConfig(
            url=url,
            render_js=True,
            screenshots={'main': 'fullpage'}
        ))

        name = name or 'main.jpg'

        if not name.endswith('.jpg'):
            name += '.jpg'

        with self as client:
            response = client.http_session.request(
                method='GET',
                url=api_response.scrape_result['screenshots']['main']['url']
            )

            response.raise_for_status()

            screenshot = response.content

        self.sink(api_response, path=path, name=name, content=screenshot)

    def sink(self, api_response:ScrapeApiResponse, content:Optional[Union[str, bytes]]=None, path: Optional[str] = None, name: Optional[str] = None, file: Optional[Union[TextIO, BytesIO]] = None):
        scrape_result = api_response.result['result']
        scrape_config = api_response.result['config']

        file_content = content or scrape_result['content']
        file_path = None
        file_extension = None

        if name:
            name_parts = name.split('.')
            if len(name_parts) > 1:
                file_extension = name_parts[-1]

        if not file:
            if file_extension is None:
                try:
                    mime_type = scrape_result['response_headers']['content-type']
                except KeyError:
                    mime_type = 'application/octet-stream'

                if ';' in mime_type:
                    mime_type = mime_type.split(';')[0]

                file_extension = '.' + mime_type.split('/')[1]

            if not name:
                name = scrape_config['url'].split('/')[-1]

            if name.find(file_extension) == -1:
                name += file_extension

            file_path = path + '/' + name if path else name

            if file_path == file_extension:
                url = re.sub(r'(https|http)?://', '', api_response.config['url']).replace('/', '-')

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

    def _handle_api_response(
        self,
        response: requests.Response,
        scrape_config:ScrapeConfig,
        raise_on_upstream_error: Optional[bool] = True
    ) -> ScrapeApiResponse:
        try:
            result = self.body_handler(response.content)
        except ValueError:
            raise ErrorFactory.create(api_response=ScrapeApiResponse(response=response, request=response.request, scrape_config=scrape_config))

        api_response:ScrapeApiResponse = ScrapeApiResponse(response=response, request=response.request, api_result=result, scrape_config=scrape_config)
        api_response.raise_for_result(raise_on_upstream_error=raise_on_upstream_error)

        return api_response
