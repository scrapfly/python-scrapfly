from copy import deepcopy
from functools import partial
from typing import Dict, Optional, List

from scrapy import Request

from .. import ScrapeConfig


class ScrapflyScrapyRequest(Request):

    scrape_config:ScrapeConfig

    # url:str   inherited
    # method:str inherited
    # body:bytes inherited
    # headers:Dict inherited
    # encoding:Dict inherited

    def __init__(self, scrape_config:ScrapeConfig, meta:Dict={}, *args, **kwargs):
        self.scrape_config = scrape_config

        meta['scrapfly_scrape_config'] = self.scrape_config

        super().__init__(
            *args,
            url=self.scrape_config.url,
            headers=self.scrape_config.headers,
            cookies=self.scrape_config.cookies,
            body=self.scrape_config.body,
            meta=meta,
            **kwargs
        )

    def replace(self, *args, **kwargs):
        for x in [
            'meta',
            'flags',
            'encoding',
            'priority',
            'dont_filter',
            'callback',
            'errback',
            'cb_kwargs',
        ]:
            kwargs.setdefault(x, getattr(self, x))
            kwargs['scrape_config'] = deepcopy(self.scrape_config)

        cls = kwargs.pop('cls', self.__class__)
        return cls(*args, **kwargs)
