from typing import Union, Optional

from scrapy import Spider
from scrapy.http import Request

from .spider import ScrapflySpider
from .request import ScrapflyScrapyRequest
from .response import ScrapflyScrapyResponse


class ScrapflyMiddleware:

    def process_request(self, request:Union[Request, ScrapflyScrapyRequest], spider:Union[Spider, ScrapflySpider]) -> Optional[ScrapflyScrapyResponse]:
        if not isinstance(request, ScrapflyScrapyRequest):
            return None

        if not isinstance(spider, ScrapflySpider):
            raise RuntimeError('ScrapflyScrapyRequest must be fired from ScrapflySpider, %s given' % type(spider))

        if request.scrape_config.tags is None:
            request.scrape_config.tags = []

        request.scrape_config.tags.append(spider.name)

        return None
