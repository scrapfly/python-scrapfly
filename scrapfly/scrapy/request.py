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

    retry:bool
    proxy_country:str
    render_js:bool
    cache:bool
    cache_clear:bool
    cache_ttl:Optional[int]
    ssl:bool
    dns:bool
    asp:bool
    session:Optional[str]
    debug:bool
    tags:Optional[List[str]]
    correlation_id:Optional[str]
    graphql:Optional[str]
    js:Optional[str]
    rendering_wait:Optional[int]
    screenshots:Optional[Dict]

    def __init__(self, scrape_config:ScrapeConfig, meta:Dict={}, *args, **kwargs):
        self.scrape_config = scrape_config

        meta['scrapfly_scrape_config'] = scrape_config

        super().__init__(
            *args,
            url=self.scrape_config.url,
            headers=self.scrape_config.headers,
            cookies=self.scrape_config.cookies,
            body=self.scrape_config.body,
            meta=meta,
            **kwargs
        )

        self.retry = scrape_config.retry
        self.proxy_country = scrape_config.country
        self.render_js = scrape_config.render_js
        self.cache = scrape_config.cache
        self.cache_ttl = scrape_config.cache_ttl
        self.cache_clear = scrape_config.cache_clear
        self.ssl = scrape_config.ssl
        self.dns = scrape_config.dns
        self.asp = scrape_config.asp
        self.session = scrape_config.session
        self.debug = scrape_config.debug
        self.tags = scrape_config.tags
        self.correlation_id = scrape_config.correlation_id
        self.graphql = scrape_config.graphql
        self.js = scrape_config.js
        self.rendering_wait = scrape_config.rendering_wait
        self.screenshots = scrape_config.screenshots
