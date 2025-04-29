import collections
import copy
import uuid
import logging

try:
    from functools import cached_property
except ImportError:
    from ..polyfill.cached_property import cached_property

from os import environ
from typing import Dict, Iterable, Sequence, Union, Optional

import scrapy
from scrapy.spiders import Rule
from scrapy.utils.python import global_object_name
from scrapy.utils.spider import iterate_spider_output
from scrapy.crawler import Crawler
from scrapy.settings import BaseSettings

from twisted.internet.defer import Deferred
from twisted.internet import task

from scrapfly import ScrapflyClient, ScrapeConfig, ScrapflyError
from . import ScrapflyScrapyRequest, ScrapflyScrapyResponse

logger = logging.getLogger(__name__)

class ScrapflySpider(scrapy.Spider):

    scrapfly_client:ScrapflyClient
    account_info:Dict
    run_id:int

    scrapfly_settings:Dict = {
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
            'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware': None,
        },
        'DOWNLOAD_HANDLERS': {
            'http': 'scrapfly.scrapy.downloader.ScrapflyHTTPDownloader',
            'https': 'scrapfly.scrapy.downloader.ScrapflyHTTPDownloader'
        },
        'SPIDER_MIDDLEWARES': {
            'scrapfly.scrapy.middleware.ScrapflyRefererMiddleware': 10,
            'scrapy.spidermiddlewares.referer.RefererMiddleware': None,
        },
        'ITEM_PIPELINES': {
            'scrapfly.scrapy.pipelines.FilesPipeline': 50,
            'scrapfly.scrapy.pipelines.ImagesPipeline': 50,
            'scrapy.pipelines.files.FilesPipeline': None,
            'scrapy.pipelines.images.ImagesPipeline': None
        }
    }

    # User config cant override these settings
    _MANDATORY_SETTINGS = {
        'SPIDER_MIDDLEWARES': [
            'scrapfly.scrapy.middleware.ScrapflyRefererMiddleware',
            'scrapy.spidermiddlewares.referer.RefererMiddleware',
        ],
        'DOWNLOADER_MIDDLEWARES': [
            'scrapfly.scrapy.middleware.ScrapflyMiddleware',
            'scrapy.downloadermiddlewares.httpauth.HttpAuthMiddleware',
            'scrapy.downloadermiddlewares.downloadtimeout.DownloadTimeoutMiddleware',
            'scrapy.downloadermiddlewares.defaultheaders.DefaultHeadersMiddleware',
            'scrapy.downloadermiddlewares.useragent.UserAgentMiddleware',
            'scrapy.downloadermiddlewares.redirect.MetaRefreshMiddleware',
            'scrapy.downloadermiddlewares.httpcompression.HttpCompressionMiddleware',
            'scrapy.downloadermiddlewares.redirect.RedirectMiddleware',
            'scrapy.downloadermiddlewares.cookies.CookiesMiddleware',
            'scrapy.downloadermiddlewares.httpproxy.HttpProxyMiddleware'
        ],
        'DOWNLOAD_HANDLERS': '*',
        'ITEM_PIPELINES': []
    }

    @classmethod
    def _merge_settings(cls, d, u):
        for k, v in u.items():
            if isinstance(v, collections.abc.Mapping):
                d[k] = cls._merge_settings(d.get(k, {}), v)
            else:
                d[k] = v
        return d

    @classmethod
    def update_settings(cls, settings: BaseSettings) -> None:
        spider_scrapfly_settings = copy.deepcopy(cls.scrapfly_settings)
        spider_user_settings = settings.copy_to_dict()

        # we only merge SPIDER_MIDDLEWARES and ITEM_PIPELINEE and prevent user from overriding them
        for key, values in cls._MANDATORY_SETTINGS.items():
            if values == '*':
                spider_user_settings.pop(key)
            elif key in spider_user_settings:
                for value in values:
                    if value in spider_user_settings[key]:
                        spider_user_settings[key].remove(value)

        _settings = cls._merge_settings(spider_scrapfly_settings, spider_user_settings)
        settings.update(_settings, priority='spider')

    @cached_property
    def run_id(self):
        return environ.get('SPIDER_RUN_ID') or str(uuid.uuid4())

    def closed(self, reason:str):
        self.scrapfly_client.close()

    def start_requests(self) -> Iterable[ScrapflyScrapyRequest]:
        for scrape_config in self.start_urls:
            if not isinstance(scrape_config, ScrapeConfig):
                raise RuntimeError('start_urls must contains ScrapeConfig Object with ScrapflySpider')
            yield ScrapflyScrapyRequest(scrape_config=scrape_config)

    def retry(self, request:ScrapflyScrapyRequest, reason:Union[str, Exception], delay:Optional[int]=None):
        logger.info('==> Retrying request for reason %s' % reason)
        stats = self.crawler.stats
        retries = request.meta.get('retry_times', 0) + 1

        if retries >= self.custom_settings.get('SCRAPFLY_MAX_API_RETRIES', 5):
            return None

        retryreq = request.replace(dont_filter=True)
        retryreq.priority += 100

        if retryreq.scrape_config.cache is True:
            retryreq.scrape_config.cache_clear = True

        retryreq.meta['retry_times'] = retries

        if stats:
            stats.inc_value('scrapfly/api_retry/count')

            if isinstance(reason, ScrapflyError):
                stats.inc_value(f'scrapfly/api_retry/{reason.code}')

        if isinstance(reason, Exception):
            reason = global_object_name(reason.__class__)

        logger.warning(f"Retrying {request} for x{retries - 1}: {reason}", extra={'spider': self})

        if delay is None:
            deferred = Deferred()
            deferred.addCallback(self.crawler.engine.schedule, request=retryreq, spider=self)
        else:
            from twisted.internet import reactor # prevent reactor already install issue
            from . import current_scrapy_version, comparable_version
            if current_scrapy_version >= comparable_version('2.10.0'):
                deferred = task.deferLater(reactor, delay, self.crawler.engine.crawl, retryreq)
            else:
                deferred = task.deferLater(reactor, delay, self.crawler.engine.crawl, retryreq, self)

        return deferred

    @classmethod
    def from_crawler(cls, crawler:Crawler, *args, **kwargs):
        from . import current_scrapy_version, comparable_version

        scrapfly_client = ScrapflyClient(
            key=crawler.settings.get('SCRAPFLY_API_KEY'),
            host=crawler.settings.get('SCRAPFLY_HOST', ScrapflyClient.HOST),
            verify=crawler.settings.get('SCRAPFLY_SSL_VERIFY', True),
            debug=crawler.settings.get('SCRAPFLY_DEBUG', False),
            distributed_mode=crawler.settings.get('SCRAPFLY_DISTRIBUTED_MODE', False),
            connect_timeout=crawler.settings.get('SCRAPFLY_CONNECT_TIMEOUT', ScrapflyClient.DEFAULT_CONNECT_TIMEOUT),
            read_timeout=crawler.settings.get('SCRAPFLY_READ_TIMEOUT', ScrapflyClient.DEFAULT_READ_TIMEOUT),
        )

        settings_max_concurrency = crawler.settings.get('CONCURRENT_REQUESTS', -1)
        account_info = scrapfly_client.account()

        if account_info['account']['suspended'] is True:
            raise RuntimeError('Your account is suspended, please check your subscription status. Reason: %s' % account_info['account']['suspension_reason'])

        max_account_concurrency = account_info['subscription']['max_concurrency']
        project_concurrency_limit = account_info['project']['concurrency_limit']
        maximum_allowed_concurrency = max_account_concurrency

        if project_concurrency_limit is not None:
            maximum_allowed_concurrency = project_concurrency_limit

        if settings_max_concurrency == -1:
            crawler.settings.set('CONCURRENT_REQUESTS', maximum_allowed_concurrency, 255)
            logger.warning('Concurrent request auto configured to %d' % maximum_allowed_concurrency)
        else:
            if settings_max_concurrency > maximum_allowed_concurrency:
                logger.warning('==> Your maximum concurrency has been adjusted following your subscription because it\'s missconfigured. Configured: %d, Maximum Allowed: %d' % (settings_max_concurrency, maximum_allowed_concurrency))
                crawler.settings.set('CONCURRENT_REQUESTS', maximum_allowed_concurrency, 255)

        if current_scrapy_version >= comparable_version('2.11.0'):
            crawler._apply_settings()

        if crawler.stats:
            crawler.stats.set_value('scrapfly/api_call_cost', 0)

        spider = cls(*args, **kwargs)
        spider._set_crawler(crawler)
        spider.scrapfly_client = scrapfly_client
        spider.scrapfly_client.version += "+scrapy@%s" % scrapy.__version__

        spider.scrapfly_client.open()
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
