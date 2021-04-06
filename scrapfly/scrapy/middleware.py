from typing import Union, Optional

from scrapy import Spider
from scrapy.http import Request, Response
from twisted.web._newclient import ResponseNeverReceived

from .spider import ScrapflySpider
from .request import ScrapflyScrapyRequest
from .response import ScrapflyScrapyResponse

import logging

logger = logging.getLogger(__name__)

from .. import ScrapflyError, HttpError


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
        if isinstance(exception, ResponseNeverReceived):
            return spider.retry(request, exception, 5)

        if not isinstance(exception, ScrapflyError):
            raise exception

        if isinstance(exception, HttpError):
            if exception.code in ScrapflyError.RETRYABLE_CODE or exception.http_status_code in [502]:
                delay = 5

                if 'retry-after' in exception.response.headers:
                    delay = int(exception.response.headers['retry-after'])

                return spider.retry(request, exception, delay)

        if spider.settings.get('SCRAPFLY_CUSTOM_RETRY_CODE', False) and exception.code in spider.settings.get('SCRAPFLY_CUSTOM_RETRY_CODE'):
            return spider.retry(request, exception, 5)
        elif exception.is_retryable is True:
            return spider.retry(request, exception, 5)

        raise exception

    def process_response(self, request: Union[Request, ScrapflyScrapyRequest], response: Union[Response, ScrapflyScrapyResponse], spider: Union[Spider, ScrapflySpider]) -> Union[ScrapflyScrapyResponse, ScrapflyScrapyRequest]:
        return response
