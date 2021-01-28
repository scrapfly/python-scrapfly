import copy
from typing import Dict, Iterable, Sequence

import scrapy
from scrapy.crawler import Crawler
from scrapy.spiders import Rule
from scrapy.utils.spider import iterate_spider_output

from scrapfly import ScrapflyClient, ScrapeConfig
from . import ScrapflyScrapyRequest, ScrapflyScrapyResponse


class ScrapflySpider(scrapy.Spider):

    scrapfly_client:ScrapflyClient
    account_info:Dict

    custom_settings:Dict = {
        'DOWNLOADER_MIDDLEWARES': {
            'scrapfly.scrapy.middleware.ScrapflyMiddleware': 725,
            'scrapy.downloadermiddlewares.httpauth.HttpAuthMiddleware': None,
            'scrapy.downloadermiddlewares.downloadtimeout.DownloadTimeoutMiddleware': None,
            'scrapy.downloadermiddlewares.defaultheaders.DefaultHeadersMiddleware': None,
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware': None,
            'scrapy.downloadermiddlewares.redirect.MetaRefreshMiddleware': None,
            'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware': None,
            'scrapy.downloadermiddlewares.redirect.RedirectMiddleware': None,
            'scrapy.downloadermiddlewares.cookies.CookiesMiddleware': None,
            'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': None
        },
        'DOWNLOAD_HANDLERS_BASE': {
            'http': 'scrapfly.scrapy.downloader.ScrapflyHTTPDownloader',
            'https': 'scrapfly.scrapy.downloader.ScrapflyHTTPDownloader'
        },
    }

    def __init__(self, scrapfly_client:ScrapflyClient, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.scrapfly_client = scrapfly_client

    def closed(self, reason:str):
        self.scrapfly_client.close()

    def start_requests(self) -> Iterable[ScrapflyScrapyRequest]:
        for scrape_config in self.start_urls:
            if not isinstance(scrape_config, ScrapeConfig):
                raise RuntimeError('start_urls must contains ScrapeConfig Object with ScrapflySpider')
            yield ScrapflyScrapyRequest(scrape_config=scrape_config)

    @classmethod
    def from_crawler(cls, crawler:Crawler, *args, **kwargs):
        crawler.stats.set_value('scrapfly/api_call_cost', 0)

        scrapfly_client = ScrapflyClient(
            key=crawler.settings.get('SCRAPFLY_API_KEY'),
            host=crawler.settings.get('SCRAPFLY_HOST', ScrapflyClient.HOST),
            verify=crawler.settings.get('SCRAPFLY_SSL_VERIFY', True),
            debug=crawler.settings.get('SCRAPFLY_DEBUG', False),
            distributed_mode=crawler.settings.get('SCRAPFLY_DISTRIBUTED_MODE', False),
            connect_timeout=crawler.settings.get('SCRAPFLY_CONNECT_TIMEOUT', ScrapflyClient.DEFAULT_CONNECT_TIMEOUT),
            read_timeout=crawler.settings.get('SCRAPFLY_READ_TIMEOUT', ScrapflyClient.DEFAULT_READ_TIMEOUT)
        )

        scrapfly_client.open()
        spider = cls(*args, scrapfly_client=scrapfly_client, **kwargs)
        spider._set_crawler(crawler)

        return spider


class ScrapflyCrawlSpider(ScrapflySpider):

    def _scrape_config_factory(self, rule_index, link):
        return ScrapeConfig(url=link.url)

    def _build_request(self, rule_index, link):
        return ScrapflyScrapyRequest(
            scrape_config=self._scrape_config_factory(rule_index, link),
            callback=self._callback,
            errback=self._errback,
            meta=dict(rule=rule_index, link_text=link.text),
        )

    rules: Sequence[Rule] = ()

    def __init__(self, *a, **kw):
        super().__init__(*a, **kw)
        self._compile_rules()

    def _parse(self, response, **kwargs):

        return self._parse_response(
            response=response,
            callback=self.parse_start_url,
            cb_kwargs=kwargs,
            follow=True,
        )

    def parse_start_url(self, response, **kwargs):
        return []

    def process_results(self, response, results):
        return results

    def _requests_to_follow(self, response):
        if not isinstance(response, ScrapflyScrapyResponse):
            return

        seen = set()

        for rule_index, rule in enumerate(self._rules):

            links = [lnk for lnk in rule.link_extractor.extract_links(response) if lnk not in seen]

            for link in rule.process_links(links):
                seen.add(link)
                request = self._build_request(rule_index, link)
                yield rule.process_request(request, response)

    def _callback(self, response):
        rule = self._rules[response.meta['rule']]
        return self._parse_response(response, rule.callback, rule.cb_kwargs, rule.follow)

    def _errback(self, failure):
        rule = self._rules[failure.request.meta['rule']]
        return self._handle_failure(failure, rule.errback)

    def _parse_response(self, response, callback, cb_kwargs, follow=True):
        if callback:
            cb_res = callback(response, **cb_kwargs) or ()
            cb_res = self.process_results(response, cb_res)
            for request_or_item in iterate_spider_output(cb_res):
                yield request_or_item

        if follow and self._follow_links:
            for request_or_item in self._requests_to_follow(response):
                yield request_or_item

    def _handle_failure(self, failure, errback):
        if errback:
            results = errback(failure) or ()
            for request_or_item in iterate_spider_output(results):
                yield request_or_item

    def _compile_rules(self):
        self._rules = []
        for rule in self.rules:
            self._rules.append(copy.copy(rule))
            self._rules[-1]._compile(self)

    @classmethod
    def from_crawler(cls, crawler, *args, **kwargs):
        spider = super().from_crawler(crawler, *args, **kwargs)
        spider._follow_links = crawler.settings.getbool('CRAWLSPIDER_FOLLOW_LINKS', True)
        return spider
