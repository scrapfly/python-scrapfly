"""ScrapflyClient: the Scrapfly API over requests."""
import asyncio
import base64
import http
import logging
import time
from asyncio import AbstractEventLoop, Task
from concurrent.futures.thread import ThreadPoolExecutor
from functools import cached_property, partial, wraps
from io import BytesIO
from typing import Any, Callable, Dict, Iterator, List, Literal, Optional, Tuple, Union

import requests
import urllib3
from requests import Response, Session

# Every name this module held before the API moved to api.py.
from .api import *
from .api import ScrapflyApi, NetworkError, PromptEventDecoder
from .api_response import ScrapeApiResponse, ScreenshotApiResponse, ExtractionApiResponse
from .crawler import CrawlerPromptEvent
from .extraction_config import ExtractionConfig
from .schedule import CreateScheduleRequest, UpdateScheduleRequest, ScheduleRecurrence, ScheduleEnd, ScheduleAPIError, Schedule
from .scrape_config import ScrapeConfig
from .screenshot_config import ScreenshotConfig
from .transport import Call, Sleep, Steps, Streamed, retry_delay, signed, without_key

logger = logging.getLogger(__name__)


def read_stream(streamed: Streamed, run: Optional[Callable[[Steps], Any]]) -> Iterator:
    """The items of a streamed requests.Response, each through its finishing operation."""
    try:
        for chunk in streamed.response.iter_content(chunk_size=streamed.chunk_size):
            for item in streamed.decoder.feed(chunk):
                yield item if streamed.finish is None else run(streamed.finish(item))

            if streamed.decoder.done:
                return

        for item in streamed.decoder.close():
            yield item if streamed.finish is None else run(streamed.finish(item))
    finally:
        streamed.response.close()


def _is_read_timeout(error: BaseException) -> bool:
    """A read that timed out: requests raises ReadTimeout while it waits for the headers, and a ConnectionError holding
    urllib3's ReadTimeoutError while it reads the body."""
    if isinstance(error, requests.ReadTimeout):
        return True

    if isinstance(error, requests.ConnectionError) and error.args:
        return isinstance(error.args[0], urllib3.exceptions.ReadTimeoutError)

    return False


class ScrapflyClient(ScrapflyApi):
    """The Scrapfly API over requests. Every operation of ScrapflyApi is a plain method here."""

    def _init_transport(self):
        self.async_executor = ThreadPoolExecutor()
        self.http_session = None

        if self.debug is True:
            http.client.HTTPConnection.debuglevel = 5

    @cached_property
    def _http_handler(self):
        return partial(self.http_session.request if self.http_session else requests.request)

    @property
    def http(self):
        return self._http_handler

    @staticmethod
    def _method(steps):
        @wraps(steps)
        def method(self, *args, **kwargs):
            result = self._run(steps(self, *args, **kwargs))

            return read_stream(result, self._run) if isinstance(result, Streamed) else result

        return signed(method, steps, Iterator)

    @staticmethod
    def _stream_method(steps):
        def items(self, args, kwargs):
            yield from read_stream(self._run(steps(self, *args, **kwargs)), self._run)

        # A plain function returning a lazy iterator: nothing is sent before the first item is asked for.
        @wraps(steps)
        def method(self, *args, **kwargs):
            return items(self, args, kwargs)

        return signed(method, steps, Iterator)

    def _run(self, steps: Steps):
        send, value = steps.send, None

        while True:
            try:
                step = send(value)
            except StopIteration as done:
                return done.value
            except requests.RequestException as error:
                # raise_for_status() prints the request URL, key included.
                masked = without_key(error)
                if masked is error:
                    raise

                raise masked from None

            # Raised inside the operation, at the yield, so its own handlers see it.
            try:
                value, send = self._perform(step), steps.send
            except BaseException as error:
                value, send = error, steps.throw

    def _perform(self, step: Call | Sleep) -> Optional[Response]:
        if isinstance(step, Sleep):
            time.sleep(step.seconds)

            return None

        for attempt in range(step.tries):
            try:
                return self._http_handler(method=step.method, url=step.url, **step.options)
            except (*NetworkError, requests.RequestException) as error:
                retries = isinstance(error, NetworkError) and attempt + 1 < step.tries

                if _is_read_timeout(error) and not step.retry_read_timeout:
                    retries = False

                if retries:
                    time.sleep(retry_delay(attempt))
                    continue

                masked = without_key(error)
                if masked is error:
                    raise

                # The chained urllib3 errors print the key too.
                raise masked from None

    # The private methods of the client before ScrapflyApi, still called by the Scrapy downloader and subclasses.

    def _handle_response(self, response: Response, scrape_config: ScrapeConfig) -> ScrapeApiResponse:
        return self._run(self._scrape_response_steps(response, scrape_config))

    def _handle_api_response(self, response: Response, scrape_config: ScrapeConfig, raise_on_upstream_error: Optional[bool] = True) -> ScrapeApiResponse:
        return self._build_scrape_api_response(response, scrape_config, self._scrape_body(response, scrape_config), self._handle_scrape_large_objects, raise_on_upstream_error)

    def _handle_scrape_large_objects(self, callback_url: str, format: Literal['clob', 'blob']) -> Tuple[Union[BytesIO, str], str]:
        return self._run(self._large_object_steps(callback_url, format))

    def _monitoring_request(self, path: str, params: dict):
        return self._run(self._monitoring_steps(path, params))

    def _schedule_request(self, method: str, path: str, *, query: Optional[Dict[str, str]] = None, body: Optional[Dict[str, Any]] = None) -> Any:
        return self._run(self._schedule_steps(method, path, query=query, body=body))

    def _create_schedule(self, path: str, config_key: str, config: Dict[str, Any], request: CreateScheduleRequest) -> Schedule:
        return self._run(self._create_schedule_steps(path, config_key, config, request))

    @staticmethod
    def _iter_prompt_events(response: Response) -> Iterator[CrawlerPromptEvent]:
        yield from read_stream(Streamed(response=response, decoder=PromptEventDecoder(response.status_code), chunk_size=512), None)

    def open(self):
        if self.http_session is None:
            self.http_session = Session()
            self.http_session.verify = self.verify
            self.http_session.timeout = (self.connect_timeout, self.default_read_timeout)
            self.http_session.params['key'] = self.key
            self.http_session.headers['accept-encoding'] = self.body_handler.content_encoding
            self.http_session.headers['accept'] = self.body_handler.accept
            self.http_session.headers['user-agent'] = self.ua

    def close(self):
        if self.http_session is not None:
            self.http_session.close()
            self.http_session = None
        # The executor owns worker threads that outlive the HTTP session.
        if self.async_executor is not None:
            self.async_executor.shutdown(wait=False)
            self.async_executor = None

    def __enter__(self) -> 'ScrapflyClient':
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    # Thread-pool helpers kept from before AsyncScrapflyClient, which awaits the same calls natively.

    async def async_scrape(self, scrape_config:ScrapeConfig, loop:Optional[AbstractEventLoop]=None) -> ScrapeApiResponse:
        if loop is None:
            loop = asyncio.get_running_loop()

        return await loop.run_in_executor(self.async_executor, self.scrape, scrape_config)

    async def async_screenshot(self, screenshot_config:ScreenshotConfig, loop:Optional[AbstractEventLoop]=None) -> ScreenshotApiResponse:
        if loop is None:
            loop = asyncio.get_running_loop()

        return await loop.run_in_executor(self.async_executor, self.screenshot, screenshot_config)

    async def async_extraction(self, extraction_config:ExtractionConfig, loop:Optional[AbstractEventLoop]=None) -> ExtractionApiResponse:
        if loop is None:
            loop = asyncio.get_running_loop()

        return await loop.run_in_executor(self.async_executor, self.extract, extraction_config)

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
                        except IndexError:
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
