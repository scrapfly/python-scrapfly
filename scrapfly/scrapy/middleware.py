from typing import Union, Optional, Iterable

from scrapy import Spider
from scrapy.http import Request, Response
from scrapy.spidermiddlewares.referer import RefererMiddleware as ScrapyRefererMidleware
from twisted.web._newclient import ResponseNeverReceived

from .spider import ScrapflySpider
from .request import ScrapflyScrapyRequest
from .response import ScrapflyScrapyResponse

from .. import HttpError, ScrapflyError


# spider middleware
class ScrapflyRefererMiddleware(ScrapyRefererMidleware):

    def process_spider_output(self, response, result, spider) -> Iterable:
        if isinstance(response, ScrapflyScrapyResponse) and response.scrape_config.session is not None:
            return result # bypass - already handled by scrapfly session system

        return ScrapyRefererMidleware.process_spider_output(self, response, result, spider)

    def request_scheduled(self, request, spider):
        if isinstance(request, ScrapflyScrapyRequest) and request.scrape_config.session is not None:
            return # bypass - already handled by scrapfly session system

        ScrapyRefererMidleware.request_scheduled(self, request, spider)


# downloader middleware
class ScrapflyMiddleware:
    MAX_API_RETRIES = 20

    def process_request(self, request: Union[Request, ScrapflyScrapyRequest], spider: Union[Spider, ScrapflySpider]) -> Optional[ScrapflyScrapyResponse]:
        if not isinstance(request, ScrapflyScrapyRequest):
            return None

        if not isinstance(spider, ScrapflySpider):
            raise RuntimeError('ScrapflyScrapyRequest must be fired from ScrapflySpider, %s given' % type(spider))

        if request.scrape_config.tags is None:
            request.scrape_config.tags = set()

        request.scrape_config.tags.add(spider.name)
        request.scrape_config.tags.add(str(spider.run_id))

        if request.scrape_config.proxy_pool is None and spider.settings.get('SCRAPFLY_PROXY_POOL'):
            request.scrape_config.proxy_pool = spider.settings.get('SCRAPFLY_PROXY_POOL')

        return None

    def process_exception(self, request, exception:Union[str, Exception], spider:ScrapflySpider):
        delay = 1

        if isinstance(exception, ResponseNeverReceived):
            return spider.retry(request, exception, delay)

        if isinstance(exception, ScrapflyError):
            if exception.is_retryable:
                if isinstance(exception, HttpError) and exception.response is not None:
                    if 'retry-after' in exception.response.headers:
                        delay = int(exception.response.headers['retry-after'])

                return spider.retry(request, exception, delay)

            if spider.settings.get('SCRAPFLY_CUSTOM_RETRY_CODE', False) and exception.code in spider.settings.get('SCRAPFLY_CUSTOM_RETRY_CODE'):
                return spider.retry(request, exception, delay)

        raise exception

    def process_response(self, request: Union[Request, ScrapflyScrapyRequest], response: Union[Response, ScrapflyScrapyResponse], spider: Union[Spider, ScrapflySpider]) -> Union[ScrapflyScrapyResponse, ScrapflyScrapyRequest]:
        return response
