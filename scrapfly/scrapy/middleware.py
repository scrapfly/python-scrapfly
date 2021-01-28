import uuid
from os import environ
from typing import Union, Optional

from scrapy import Spider
from scrapy.http import Request

from .spider import ScrapflySpider
from .request import ScrapflyScrapyRequest
from .response import ScrapflyScrapyResponse


class ScrapflyMiddleware:

    run_id:str

    def __init__(self):
        self.run_id = environ.get('SPIDER_RUN_ID') or str(uuid.uuid4())

    def process_request(self, request:Union[Request, ScrapflyScrapyRequest], spider:Union[Spider, ScrapflySpider]) -> Optional[ScrapflyScrapyResponse]:
        if not isinstance(request, ScrapflyScrapyRequest):
            return None

        if not isinstance(spider, ScrapflySpider):
            raise RuntimeError('ScrapflyScrapyRequest must be fired from ScrapflySpider, %s given' % type(spider))

        if request.scrape_config.tags is None:
            request.scrape_config.tags = []

        request.scrape_config.tags.append(spider.name)
        request.scrape_config.tags.append(self.run_id)

        return None
