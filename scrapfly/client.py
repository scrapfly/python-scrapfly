import os
import datetime
import warnings
from asyncio import AbstractEventLoop, Task
from concurrent.futures.thread import ThreadPoolExecutor

import asyncio
import http
import platform
import re
import shutil
from functools import partial
from io import BytesIO

import backoff
from requests import Session, Response
from requests import exceptions as RequestExceptions
from typing import TextIO, Union, List, Dict, Optional, Set, Callable, Literal
import requests
import urllib3
import logging as logger

from .reporter import Reporter

try:
    from functools import cached_property
except ImportError:
    from .polyfill.cached_property import cached_property

from .errors import *
from .api_response import ResponseBodyHandler
from .scrape_config import ScrapeConfig
from .screenshot_config import ScreenshotConfig
from .extraction_config import ExtractionConfig
from . import __version__, ScrapeApiResponse, ScreenshotApiResponse, ExtractionApiResponse, HttpError, UpstreamHttpError

logger.getLogger(__name__)

NetworkError = (
    ConnectionError,
    RequestExceptions.ConnectionError,
    RequestExceptions.ReadTimeout
)

class ScraperAPI:

    MONITORING_DATA_FORMAT_STRUCTURED = 'structured'
    MONITORING_DATA_FORMAT_PROMETHEUS = 'prometheus'

    MONITORING_PERIOD_SUBSCRIPTION = 'subscription'
    MONITORING_PERIOD_LAST_7D = 'last7d'
    MONITORING_PERIOD_LAST_24H = 'last24h'
    MONITORING_PERIOD_LAST_1H = 'last1h'
    MONITORING_PERIOD_LAST_5m = 'last5m'

    MONITORING_ACCOUNT_AGGREGATION = 'account'
    MONITORING_PROJECT_AGGREGATION = 'project'
    MONITORING_TARGET_AGGREGATION = 'target'


# Create custom type hint for possible values of the period parameter
# in the get_monitoring_target_metrics method
MonitoringTargetPeriod = Literal[
    ScraperAPI.MONITORING_PERIOD_SUBSCRIPTION,
    ScraperAPI.MONITORING_PERIOD_LAST_7D,
    ScraperAPI.MONITORING_PERIOD_LAST_24H,
    ScraperAPI.MONITORING_PERIOD_LAST_1H,
    ScraperAPI.MONITORING_PERIOD_LAST_5m
]

MonitoringAggregation = Literal[
    ScraperAPI.MONITORING_ACCOUNT_AGGREGATION,
    ScraperAPI.MONITORING_PROJECT_AGGREGATION,
    ScraperAPI.MONITORING_TARGET_AGGREGATION
]

class ScrapflyClient:

    HOST = 'https://api.scrapfly.io'
    DEFAULT_CONNECT_TIMEOUT = 30
    DEFAULT_READ_TIMEOUT = 160 # 155 real

    host:str
    key:str
    max_concurrency:int
    verify:bool
    debug:bool
    distributed_mode:bool
    connect_timeout:int
    read_timeout:int
    brotli: bool
    reporter:Reporter
    version:str

    CONCURRENCY_AUTO = 'auto' # retrieve the allowed concurrency from your account
    DATETIME_FORMAT = '%Y-%m-%d %H:%M:%S'

    def __init__(
        self,
        key: str,
        host: Optional[str] = HOST,
        verify=True,
        debug: bool = False,
        max_concurrency:int=1,
        connect_timeout:int = DEFAULT_CONNECT_TIMEOUT,
        read_timeout:int = DEFAULT_READ_TIMEOUT,
        reporter:Optional[Callable]=None,
        **kwargs
    ):
        if host[-1] == '/':  # remove last '/' if exists
            host = host[:-1]

        if 'distributed_mode' in kwargs:
            warnings.warn("distributed mode is deprecated and will be remove the next version -"
              " user should handle themself the session name based on the concurrency",
              DeprecationWarning,
              stacklevel=2
            )

        if 'brotli' in kwargs:
            warnings.warn("brotli arg is deprecated and will be remove the next version - "
                "brotli is disabled by default",
                DeprecationWarning,
                stacklevel=2
            )

        self.version = __version__
        self.host = host
        self.key = key
        self.verify = verify
        self.debug = debug
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout
        self.max_concurrency = max_concurrency
        self.body_handler = ResponseBodyHandler(use_brotli=False)
        self.async_executor = ThreadPoolExecutor()
        self.http_session = None

        if not self.verify and not self.HOST.endswith('.local'):
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

        if self.debug is True:
            http.client.HTTPConnection.debuglevel = 5

        if reporter is None:
            from .reporter import NoopReporter

            reporter = NoopReporter()

        self.reporter = Reporter(reporter)

    @property
    def ua(self) -> str:
        return 'ScrapflySDK/%s (Python %s, %s, %s)' % (
            self.version,
            platform.python_version(),
            platform.uname().system,
            platform.uname().machine
        )

    @cached_property
    def _http_handler(self):
        return partial(self.http_session.request if self.http_session else requests.request)

    @property
    def http(self):
        return self._http_handler

    def _scrape_request(self, scrape_config:ScrapeConfig):
        return {
            'method': scrape_config.method,
            'url': self.host + '/scrape',
            'data': scrape_config.body,
            'verify': self.verify,
            'timeout': (self.connect_timeout, self.read_timeout),
            'headers': {
                'content-type': scrape_config.headers['content-type'] if scrape_config.method in ['POST', 'PUT', 'PATCH'] else self.body_handler.content_type,
                'accept-encoding': self.body_handler.content_encoding,
                'accept': self.body_handler.accept,
                'user-agent': self.ua
            },
            'params': scrape_config.to_api_params(key=self.key)
        }
    
    def _screenshot_request(self, screenshot_config:ScreenshotConfig):
        return {
            'method': 'GET',
            'url': self.host + '/screenshot',
            'timeout': (self.connect_timeout, self.read_timeout),
            'headers': {
                'accept-encoding': self.body_handler.content_encoding,
                'accept': self.body_handler.accept,
                'user-agent': self.ua
            },            
            'params': screenshot_config.to_api_params(key=self.key)
        }        

    def _extraction_request(self, extraction_config:ExtractionConfig):
        headers = {
                'content-type': extraction_config.content_type,
                'accept-encoding': self.body_handler.content_encoding,
                'content-encoding': extraction_config.document_compression_format if extraction_config.document_compression_format else None,
                'accept': self.body_handler.accept,
                'user-agent': self.ua
        }
        if extraction_config.document_compression_format:
            headers['content-encoding'] = extraction_config.document_compression_format.value
        return {
            'method': 'POST',
            'url': self.host + '/extraction',
            'data': extraction_config.body,
            'timeout': (self.connect_timeout, self.read_timeout),
            'headers': headers,
            'params': extraction_config.to_api_params(key=self.key)
        }


    def account(self) -> Union[str, Dict]:
        response = self._http_handler(
            method='GET',
            url=self.host + '/account',
            params={'key': self.key},
            verify=self.verify,
            headers={
                'accept-encoding': self.body_handler.content_encoding,
                'accept': self.body_handler.accept,
                'user-agent': self.ua
            },
        )

        response.raise_for_status()

        if self.body_handler.support(response.headers):
            return self.body_handler(response.content, response.headers['content-type'])

        return response.content.decode('utf-8')

    def get_monitoring_metrics(self, format:str=ScraperAPI.MONITORING_DATA_FORMAT_STRUCTURED, period:Optional[str]=None, aggregation:Optional[List[MonitoringAggregation]]=None):
        params = {'key': self.key, 'format': format}

        if period is not None:
            params['period'] = period

        if aggregation is not None:
            params['aggregation'] = ','.join(aggregation)

        response = self._http_handler(
            method='GET',
            url=self.host + '/scrape/monitoring/metrics',
            params=params,
            verify=self.verify,
            headers={
                'accept-encoding': self.body_handler.content_encoding,
                'accept': self.body_handler.accept,
                'user-agent': self.ua
            },
        )

        response.raise_for_status()

        if self.body_handler.support(response.headers):
            return self.body_handler(response.content, response.headers['content-type'])

        return response.content.decode('utf-8')

    def get_monitoring_target_metrics(
            self,
            domain:str,
            group_subdomain:bool=False,
            period:Optional[MonitoringTargetPeriod]=ScraperAPI.MONITORING_PERIOD_LAST_24H,
            start:Optional[datetime.datetime]=None,
            end:Optional[datetime.datetime]=None,
    ):
        params = {
            'key': self.key,
            'domain': domain,
            'group_subdomain': group_subdomain
        }

        if (start is not None and end is None) or (start is None and end is not None):
            raise ValueError('You must provide both start and end date')

        if start is not None and end is not None:
            params['start'] = start.strftime(self.DATETIME_FORMAT)
            params['end'] = end.strftime(self.DATETIME_FORMAT)
            period = None

        params['period'] = period

        response = self._http_handler(
            method='GET',
            url=self.host + '/scrape/monitoring/metrics/target',
            params=params,
            verify=self.verify,
            headers={
                'accept-encoding': self.body_handler.content_encoding,
                'accept': self.body_handler.accept,
                'user-agent': self.ua
            },
        )

        response.raise_for_status()

        if self.body_handler.support(response.headers):
            return self.body_handler(response.content, response.headers['content-type'])

        return response.content.decode('utf-8')


    def resilient_scrape(
        self,
        scrape_config:ScrapeConfig,
        retry_on_errors:Set[Exception]={ScrapflyError},
        retry_on_status_code:Optional[List[int]]=None,
        tries: int = 5,
        delay: int = 20,
    ) -> ScrapeApiResponse:
        assert retry_on_errors is not None, 'Retry on error is None'
        assert isinstance(retry_on_errors, set), 'retry_on_errors is not a set()'

        @backoff.on_exception(backoff.expo, exception=tuple(retry_on_errors), max_tries=tries, max_time=delay)
        def inner() -> ScrapeApiResponse:

            try:
                return self.scrape(scrape_config=scrape_config)
            except (UpstreamHttpClientError, UpstreamHttpServerError) as e:
                if retry_on_status_code is not None and e.api_response:
                    if e.api_response.upstream_status_code in retry_on_status_code:
                        raise e
                    else:
                        return e.api_response

                raise e

        return inner()

    def open(self):
        if self.http_session is None:
            self.http_session = Session()
            self.http_session.verify = self.verify
            self.http_session.timeout = (self.connect_timeout, self.read_timeout)
            self.http_session.params['key'] = self.key
            self.http_session.headers['accept-encoding'] = self.body_handler.content_encoding
            self.http_session.headers['accept'] = self.body_handler.accept
            self.http_session.headers['user-agent'] = self.ua

    def close(self):
        self.http_session.close()
        self.http_session = None

    def __enter__(self) -> 'ScrapflyClient':
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    async def async_scrape(self, scrape_config:ScrapeConfig, loop:Optional[AbstractEventLoop]=None) -> ScrapeApiResponse:
        if loop is None:
            loop = asyncio.get_running_loop()

        return await loop.run_in_executor(self.async_executor, self.scrape, scrape_config)

    async def concurrent_scrape(self, scrape_configs:List[ScrapeConfig], concurrency:Optional[int]=None):
        if concurrency is None:
            concurrency = self.max_concurrency
        elif concurrency == self.CONCURRENCY_AUTO:
            concurrency = self.account()['subscription']['max_concurrency']

        loop = asyncio.get_running_loop()
        processing_tasks = []
        results = []
        processed_tasks = 0
        expected_tasks = len(scrape_configs)

        def scrape_done_callback(task:Task):
            nonlocal processed_tasks

            try:
                if task.cancelled() is True:
                    return

                error = task.exception()

                if error is not None:
                    results.append(error)
                else:
                    results.append(task.result())
            finally:
                processing_tasks.remove(task)
                processed_tasks += 1

        while scrape_configs or results or processing_tasks:
            logger.info("Scrape %d/%d - %d running" % (processed_tasks, expected_tasks, len(processing_tasks)))

            if scrape_configs:
                if len(processing_tasks) < concurrency:
                    # @todo handle backpressure
                    for _ in range(0, concurrency - len(processing_tasks)):
                        try:
                            scrape_config = scrape_configs.pop()
                        except:
                            break

                        scrape_config.raise_on_upstream_error = False
                        task = loop.create_task(self.async_scrape(scrape_config=scrape_config, loop=loop))
                        processing_tasks.append(task)
                        task.add_done_callback(scrape_done_callback)

            for _ in results:
                result = results.pop()
                yield result

            await asyncio.sleep(.5)

        logger.debug("Scrape %d/%d - %d running" % (processed_tasks, expected_tasks, len(processing_tasks)))

    @backoff.on_exception(backoff.expo, exception=NetworkError, max_tries=5)
    def scrape(self, scrape_config:ScrapeConfig, no_raise:bool=False) -> ScrapeApiResponse:
        """
        Scrape a website
        :param scrape_config: ScrapeConfig
        :param no_raise: bool - if True, do not raise exception on error while the api response is a ScrapflyError for seamless integration
        :return: ScrapeApiResponse

        If you use no_raise=True, make sure to check the api_response.scrape_result.error attribute to handle the error.
        If the error is not none, you will get the following structure for example

        'error': {
            'code': 'ERR::ASP::SHIELD_PROTECTION_FAILED',
            'message': 'The ASP shield failed to solve the challenge against the anti scrapping protection - heuristic_engine bypass failed, please retry in few seconds',
            'retryable': False,
            'http_code': 422,
            'links': {
                'Checkout ASP documentation': 'https://scrapfly.io/docs/scrape-api/anti-scraping-protection#maximize_success_rate', 'Related Error Doc': 'https://scrapfly.io/docs/scrape-api/error/ERR::ASP::SHIELD_PROTECTION_FAILED'
            }
        }
        """

        try:
            logger.debug('--> %s Scrapping %s' % (scrape_config.method, scrape_config.url))
            request_data = self._scrape_request(scrape_config=scrape_config)
            response = self._http_handler(**request_data)
            scrape_api_response = self._handle_response(response=response, scrape_config=scrape_config)

            self.reporter.report(scrape_api_response=scrape_api_response)

            return scrape_api_response
        except BaseException as e:
            self.reporter.report(error=e)

            if no_raise and isinstance(e, ScrapflyError) and e.api_response is not None:
                return e.api_response

            raise e

    async def async_screenshot(self, screenshot_config:ScreenshotConfig, loop:Optional[AbstractEventLoop]=None) -> ScreenshotApiResponse:
        if loop is None:
            loop = asyncio.get_running_loop()

        return await loop.run_in_executor(self.async_executor, self.screenshot, screenshot_config)

    @backoff.on_exception(backoff.expo, exception=NetworkError, max_tries=5)
    def screenshot(self, screenshot_config:ScreenshotConfig, no_raise:bool=False) -> ScreenshotApiResponse:
        """
        Take a screenshot
        :param screenshot_config: ScrapeConfig
        :param no_raise: bool - if True, do not raise exception on error while the screenshot api response is a ScrapflyError for seamless integration
        :return: str

        If you use no_raise=True, make sure to check the screenshot_api_response.error attribute to handle the error.
        If the error is not none, you will get the following structure for example

        'error': {
            'code': 'ERR::SCREENSHOT::UNABLE_TO_TAKE_SCREENSHOT',
            'message': 'For some reason we were unable to take the screenshot',
            'http_code': 422,
            'links': {
                'Checkout the related doc: https://scrapfly.io/docs/screenshot-api/error/ERR::SCREENSHOT::UNABLE_TO_TAKE_SCREENSHOT'
            }
        }
        """

        try:
            logger.debug('--> %s Screenshoting' % (screenshot_config.url))
            request_data = self._screenshot_request(screenshot_config=screenshot_config)
            response = self._http_handler(**request_data)
            screenshot_api_response = self._handle_screenshot_response(response=response, screenshot_config=screenshot_config)
            return screenshot_api_response
        except BaseException as e:
            self.reporter.report(error=e)

            if no_raise and isinstance(e, ScrapflyError) and e.api_response is not None:
                return e.api_response

            raise e

    async def async_extraction(self, extraction_config:ExtractionConfig, loop:Optional[AbstractEventLoop]=None) -> ExtractionApiResponse:
        if loop is None:
            loop = asyncio.get_running_loop()

        return await loop.run_in_executor(self.async_executor, self.extract, extraction_config)

    @backoff.on_exception(backoff.expo, exception=NetworkError, max_tries=5)
    def extract(self, extraction_config:ExtractionConfig, no_raise:bool=False) -> ExtractionApiResponse:
        """
        Extract structured data from text content
        :param extraction_config: ExtractionConfig
        :param no_raise: bool - if True, do not raise exception on error while the extraction api response is a ScrapflyError for seamless integration
        :return: str

        If you use no_raise=True, make sure to check the extraction_api_response.error attribute to handle the error.
        If the error is not none, you will get the following structure for example

        'error': {
            'code': 'ERR::EXTRACTION::CONTENT_TYPE_NOT_SUPPORTED',
            'message': 'The content type of the response is not supported for extraction',
            'http_code': 422,
            'links': {
                'Checkout the related doc: https://scrapfly.io/docs/extraction-api/error/ERR::EXTRACTION::CONTENT_TYPE_NOT_SUPPORTED'
            }
        }
        """

        try:
            logger.debug('--> %s Extracting data from' % (extraction_config.content_type))
            request_data = self._extraction_request(extraction_config=extraction_config)
            response = self._http_handler(**request_data)
            extraction_api_response = self._handle_extraction_response(response=response, extraction_config=extraction_config)
            return extraction_api_response
        except BaseException as e:
            self.reporter.report(error=e)

            if no_raise and isinstance(e, ScrapflyError) and e.api_response is not None:
                return e.api_response

            raise e

    def _handle_response(self, response:Response, scrape_config:ScrapeConfig) -> ScrapeApiResponse:
        try:
            api_response = self._handle_api_response(
                response=response,
                scrape_config=scrape_config,
                raise_on_upstream_error=scrape_config.raise_on_upstream_error
            )

            if scrape_config.method == 'HEAD':
                logger.debug('<-- [%s %s] %s | %ss' % (
                    api_response.response.status_code,
                    api_response.response.reason,
                    api_response.response.request.url,
                    0
                ))
            else:
                logger.debug('<-- [%s %s] %s | %ss' % (
                    api_response.result['result']['status_code'],
                    api_response.result['result']['reason'],
                    api_response.result['config']['url'],
                    api_response.result['result']['duration'])
                )

                logger.debug('Log url: %s' % api_response.result['result']['log_url'])

            return api_response
        except UpstreamHttpError as e:
            logger.critical(e.api_response.error_message)
            raise
        except HttpError as e:
            if e.api_response is not None:
                logger.critical(e.api_response.error_message)
            else:
                logger.critical(e.message)
            raise
        except ScrapflyError as e:
            logger.critical('<-- %s | Docs: %s' % (str(e), e.documentation_url))
            raise

    def _handle_screenshot_response(self, response:Response, screenshot_config:ScreenshotConfig) -> ScreenshotApiResponse:    
        try:
            api_response = self._handle_screenshot_api_response(
                response=response,
                screenshot_config=screenshot_config,
                raise_on_upstream_error=screenshot_config.raise_on_upstream_error
            )
            return api_response
        except UpstreamHttpError as e:
            logger.critical(e.api_response.error_message)
            raise
        except HttpError as e:
            if e.api_response is not None:
                logger.critical(e.api_response.error_message)
            else:
                logger.critical(e.message)
            raise
        except ScrapflyError as e:
            logger.critical('<-- %s | Docs: %s' % (str(e), e.documentation_url))
            raise         

    def _handle_extraction_response(self, response:Response, extraction_config:ExtractionConfig) -> ExtractionApiResponse:
        try:
            api_response = self._handle_extraction_api_response(
                response=response,
                extraction_config=extraction_config,
                raise_on_upstream_error=extraction_config.raise_on_upstream_error
            )
            return api_response
        except UpstreamHttpError as e:
            logger.critical(e.api_response.error_message)
            raise
        except HttpError as e:
            if e.api_response is not None:
                logger.critical(e.api_response.error_message)
            else:
                logger.critical(e.message)
            raise
        except ScrapflyError as e:
            logger.critical('<-- %s | Docs: %s' % (str(e), e.documentation_url))
            raise    

    def save_screenshot(self, screenshot_api_response:ScreenshotApiResponse, name:str, path:Optional[str]=None):
        """
        Save a screenshot from a screenshot API response
        :param api_response: ScreenshotApiResponse
        :param name: str - name of the screenshot to save as
        :param path: Optional[str]
        """

        if screenshot_api_response.screenshot_success is not True:
            raise RuntimeError('Screenshot was not successful')

        if not screenshot_api_response.image:
            raise RuntimeError('Screenshot binary does not exist')

        content = screenshot_api_response.image
        extension_name = screenshot_api_response.metadata['extension_name']

        if path:
            os.makedirs(path, exist_ok=True)
            file_path = os.path.join(path, f'{name}.{extension_name}')
        else:
            file_path = f'{name}.{extension_name}'

        if isinstance(content, bytes):
            content = BytesIO(content)

        with open(file_path, 'wb') as f:
            shutil.copyfileobj(content, f, length=131072)

    def save_scrape_screenshot(self, api_response:ScrapeApiResponse, name:str, path:Optional[str]=None):
        """
        Save a screenshot from a scrape result
        :param api_response: ScrapeApiResponse
        :param name: str - name of the screenshot given in the scrape config
        :param path: Optional[str]
        """

        if not api_response.scrape_result['screenshots']:
            raise RuntimeError('Screenshot %s do no exists' % name)

        try:
            api_response.scrape_result['screenshots'][name]
        except KeyError:
            raise RuntimeError('Screenshot %s do no exists' % name)

        screenshot_response = self._http_handler(
            method='GET',
            url=api_response.scrape_result['screenshots'][name]['url'],
            params={'key': self.key},
            verify=self.verify
        )

        screenshot_response.raise_for_status()

        if not name.endswith('.jpg'):
            name += '.jpg'

        api_response.sink(path=path, name=name, content=screenshot_response.content)

    def sink(self, api_response:ScrapeApiResponse, content:Optional[Union[str, bytes]]=None, path: Optional[str] = None, name: Optional[str] = None, file: Optional[Union[TextIO, BytesIO]] = None) -> str:
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
        return file_path

    def _handle_scrape_large_objects(
        self,
        body: Dict
    ) -> Dict:
        content_format = body['result']['format']
        if content_format in ['clob', 'blob']:

            request_data = {
                'method': 'GET',
                'url': body['result']['content'],
                'verify': self.verify,
                'timeout': (self.connect_timeout, self.read_timeout),
                'headers': {
                    'accept-encoding': self.body_handler.content_encoding,
                    'accept': self.body_handler.accept,
                    'user-agent': self.ua
                },
                'params': {'key': self.key}
            }
            response = self._http_handler(**request_data)
            if self.body_handler.support(headers=response.headers):
                content = self.body_handler(content=response.content, content_type=response.headers['content-type'])
            else:
                content = response.content.decode('utf-8')

            body['result']['content'] = content
            if content_format == 'clob':
                body['result']['format'] = 'text'
            if content_format == 'blob':
                body['result']['format'] = 'binary' 

        return body
        
    def _handle_api_response(
        self,
        response: Response,
        scrape_config:ScrapeConfig,
        raise_on_upstream_error: Optional[bool] = True
    ) -> ScrapeApiResponse:

        if scrape_config.method == 'HEAD':
            body = None
        else:
            if self.body_handler.support(headers=response.headers):
                body = self.body_handler(content=response.content, content_type=response.headers['content-type'])
            else:
                body = response.content.decode('utf-8')

        body = self._handle_scrape_large_objects(body=body)

        api_response:ScrapeApiResponse = ScrapeApiResponse(
            response=response,
            request=response.request,
            api_result=body,
            scrape_config=scrape_config
        )

        api_response.raise_for_result(raise_on_upstream_error=raise_on_upstream_error)

        return api_response

    def _handle_screenshot_api_response(
        self,
        response: Response,
        screenshot_config:ScreenshotConfig,
        raise_on_upstream_error: Optional[bool] = True
    ) -> ScreenshotApiResponse:

        if self.body_handler.support(headers=response.headers):
            body = self.body_handler(content=response.content, content_type=response.headers['content-type'])
        else:
            body = {'result': response.content}

        api_response:ScreenshotApiResponse = ScreenshotApiResponse(
            response=response,
            request=response.request,
            api_result=body,
            screenshot_config=screenshot_config
        )

        api_response.raise_for_result(raise_on_upstream_error=raise_on_upstream_error)

        return api_response

    def _handle_extraction_api_response(
        self,
        response: Response,
        extraction_config:ExtractionConfig,
        raise_on_upstream_error: Optional[bool] = True
    ) -> ExtractionApiResponse:
        
        if self.body_handler.support(headers=response.headers):
            body = self.body_handler(content=response.content, content_type=response.headers['content-type'])
        else:
            body = response.content.decode('utf-8')

        api_response:ExtractionApiResponse = ExtractionApiResponse(
            response=response,
            request=response.request,
            api_result=body,
            extraction_config=extraction_config
        )

        api_response.raise_for_result(raise_on_upstream_error=raise_on_upstream_error)

        return api_response
    