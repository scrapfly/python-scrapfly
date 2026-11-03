from typing import Union, Optional, Iterable

import httpx
from scrapy import Spider
from scrapy.http import Request, Response
from scrapy.spidermiddlewares.referer import RefererMiddleware as ScrapyRefererMidleware
from scrapy.utils.defer import maybe_deferred_to_future
from twisted.internet.defer import Deferred
from twisted.web._newclient import ResponseNeverReceived

from .spider import ScrapflySpider
from .request import ScrapflyScrapyRequest
from .response import ScrapflyScrapyResponse

from .. import HttpError, ScrapflyError


def _in_session(response) -> bool:
    """A Scrapfly session carries the Referer of the requests made in it."""
    return isinstance(response, ScrapflyScrapyResponse) and response.scrape_config.session is not None


# spider middleware
class ScrapflyRefererMiddleware(ScrapyRefererMidleware):

    if hasattr(ScrapyRefererMidleware, 'get_processed_request'):  # Scrapy 2.13+
        def get_processed_request(self, request, response):
            if _in_session(response):
                return request # bypass - already handled by scrapfly session system

            return super().get_processed_request(request, response)
    else:
        def process_spider_output(self, response, result, spider) -> Iterable:
            if _in_session(response):
                return result # bypass - already handled by scrapfly session system

            return ScrapyRefererMidleware.process_spider_output(self, response, result, spider)

    if hasattr(ScrapyRefererMidleware, 'request_scheduled'):  # Scrapy < 2.19
        def request_scheduled(self, request, spider):
            if isinstance(request, ScrapflyScrapyRequest) and request.scrape_config.session is not None:
                return # bypass - already handled by scrapfly session system

            ScrapyRefererMidleware.request_scheduled(self, request, spider)


# downloader middleware
class ScrapflyMiddleware:
    MAX_API_RETRIES = 20

    # Scrapy 2.15+ no longer passes the spider to these methods: it is the crawler's.
    def __init__(self, crawler=None):
        self.crawler = crawler

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler)

    def _spider(self, spider: Optional[Spider]) -> Spider:
        return self.crawler.spider if spider is None else spider

    def process_request(self, request: Union[Request, ScrapflyScrapyRequest], spider: Optional[Union[Spider, ScrapflySpider]] = None) -> Optional[ScrapflyScrapyResponse]:
        if not isinstance(request, ScrapflyScrapyRequest):
            return None

        spider = self._spider(spider)

        if not isinstance(spider, ScrapflySpider):
            raise RuntimeError('ScrapflyScrapyRequest must be fired from ScrapflySpider, %s given' % type(spider))

        if request.scrape_config.tags is None:
            request.scrape_config.tags = set()

        request.scrape_config.tags.add(spider.name)
        request.scrape_config.tags.add(str(spider.run_id))

        if request.scrape_config.proxy_pool is None and spider.settings.get('SCRAPFLY_PROXY_POOL'):
            request.scrape_config.proxy_pool = spider.settings.get('SCRAPFLY_PROXY_POOL')

        return None

    async def process_exception(self, request, exception:Union[str, Exception], spider:Optional[ScrapflySpider] = None):
        spider = self._spider(spider)
        delay = 1

        # ResponseNeverReceived from Twisted's HTTP client, TransportError from AsyncScrapflyClient's.
        if isinstance(exception, (ResponseNeverReceived, httpx.TransportError)):
            return await self._retried(spider.retry(request, exception, delay))

        if isinstance(exception, ScrapflyError):
            if exception.is_retryable:
                if isinstance(exception, HttpError) and exception.response is not None:
                    if 'retry-after' in exception.response.headers:
                        delay = int(exception.response.headers['retry-after'])

                return await self._retried(spider.retry(request, exception, delay))

            if spider.settings.get('SCRAPFLY_CUSTOM_RETRY_CODE', False) and exception.code in spider.settings.get('SCRAPFLY_CUSTOM_RETRY_CODE'):
                return await self._retried(spider.retry(request, exception, delay))

        raise exception

    @staticmethod
    async def _retried(scheduled) -> None:
        """Wait until ScrapflySpider.retry() has scheduled the retry: a Deferred under a reactor, an asyncio task without one."""
        if isinstance(scheduled, Deferred):
            await maybe_deferred_to_future(scheduled)
        elif scheduled is not None:
            await scheduled

    def process_response(self, request: Union[Request, ScrapflyScrapyRequest], response: Union[Response, ScrapflyScrapyResponse], spider: Optional[Union[Spider, ScrapflySpider]] = None) -> Union[ScrapflyScrapyResponse, ScrapflyScrapyRequest]:
        return response
