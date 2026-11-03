import inspect
import zlib
from copy import copy
from io import BytesIO
from typing import Optional
from urllib.parse import urlencode

import requests
from requests.structures import CaseInsensitiveDict
from twisted.internet.defer import Deferred, succeed
from twisted.internet.protocol import Protocol
from twisted.web.iweb import IBodyProducer
from zope.interface import implementer

from scrapy.core.downloader.handlers import DownloadHandlers
from scrapy.utils.defer import deferred_from_coro, maybe_deferred_to_future
from scrapy.utils.python import without_none_values

from . import ScrapflyScrapyRequest, ScrapflySpider, ScrapflyScrapyResponse
from .. import AsyncScrapflyClient, HttpError, ScrapeApiResponse, ScrapflyError

import logging as logger
logger.getLogger(__name__)

try:
    from scrapy.core.downloader.handlers import DownloadHandlerProtocol
except ImportError:  # Scrapy < 2.13
    DownloadHandlerProtocol = None

# Scrapy 2.14+ awaits download_request(request) and close(); older versions call download_request(request, spider) for a Deferred.
ASYNC_HANDLERS = DownloadHandlerProtocol is not None and inspect.iscoroutinefunction(DownloadHandlerProtocol.download_request)


def asyncio_available() -> bool:
    """Whether an asyncio loop drives Scrapy: the asyncio reactor, or no reactor at all (Scrapy 2.15+)."""
    try:
        from scrapy.utils.asyncio import is_asyncio_available  # Scrapy 2.14+
    except ImportError:
        from scrapy.utils.reactor import is_asyncio_reactor_installed

        return is_asyncio_reactor_installed()

    return is_asyncio_available()


class ScrapflyHTTPDownloader:
    """
    Sends a ScrapflyScrapyRequest of a ScrapflySpider to the Scrapfly API, through AsyncScrapflyClient when an
    asyncio loop drives Scrapy and through Twisted's HTTP client under another reactor. Any other request goes
    to the handler Scrapy has for its scheme.
    """

    # Loaded on the first request: the DownloadHandlers built below would otherwise load this class again.
    lazy = True

    def __init__(self, settings, crawler=None):
        self._crawler = crawler
        self._donwload_handler = DownloadHandlers(crawler)
        self._client: Optional[AsyncScrapflyClient] = None

        # Restore default downloader for http/https when not using ScraplyRequest following Scrapy's default behavior
        settings_without_scrapfly_http_downloader = copy(settings)
        del settings_without_scrapfly_http_downloader['DOWNLOAD_HANDLERS']['http']
        del settings_without_scrapfly_http_downloader['DOWNLOAD_HANDLERS']['https']
        self._donwload_handler.handlers = without_none_values(settings_without_scrapfly_http_downloader.getwithbase("DOWNLOAD_HANDLERS"))

        for scheme, clspath in self._donwload_handler.handlers.items():
            self._donwload_handler._schemes[scheme] = clspath
            self._donwload_handler._load_handler(scheme, skip_lazy=True)
        # End

        if settings.get('SCRAPFLY_SSL_VERIFY') is False:
            import twisted.internet._sslverify as v
            v.platformTrust = lambda : None

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings, crawler)

    if ASYNC_HANDLERS:
        async def download_request(self, request):
            return await self._download(request)

        async def close(self):
            await self._close()
    else:
        def download_request(self, request, spider):
            return deferred_from_coro(self._download(request))

        def close(self):
            return deferred_from_coro(self._close())

    async def _download(self, request):
        spider = self._crawler.spider

        if not isinstance(request, ScrapflyScrapyRequest) or not isinstance(spider, ScrapflySpider):
            if ASYNC_HANDLERS:
                return await self._donwload_handler.download_request_async(request)

            return await maybe_deferred_to_future(self._donwload_handler.download_request(request, spider))

        request.scrape_config.raise_on_upstream_error = False

        try:
            if asyncio_available():
                api_response = await (await self._async_client(spider)).scrape(request.scrape_config)
            else:
                api_response = await self._scrape_over_twisted(request, spider)
        except HttpError as error:
            self._count_cost(error.response)
            raise
        except ScrapflyError as error:
            self._count_cost(None if error.api_response is None else error.api_response.response)
            raise

        self._count_cost(api_response.response)

        return ScrapflyScrapyResponse(request=request, scrape_api_response=api_response)

    def _count_cost(self, response: Optional[requests.Response]):
        """Every API answer is billed, an error included."""
        if response is not None and 'x-scrapfly-api-cost' in response.headers:
            self._crawler.stats.inc_value('scrapfly/api_call_cost', count=int(response.headers['x-scrapfly-api-cost']))

    async def _async_client(self, spider: ScrapflySpider) -> AsyncScrapflyClient:
        """An AsyncScrapflyClient set like the spider's ScrapflyClient, its connections kept until the handler closes."""
        if self._client is None:
            settings = spider.scrapfly_client
            self._client = AsyncScrapflyClient(
                key=settings.key,
                host=settings.host,
                verify=settings.verify,
                connect_timeout=settings.connect_timeout,
                web_scraping_api_read_timeout=settings.web_scraping_api_read_timeout,
                default_read_timeout=settings.default_read_timeout,
            )
            self._client.version = settings.version
            await self._client.open()

        return self._client

    async def _close(self):
        if self._client is not None:
            await self._client.close()
            self._client = None

    def _scrape_over_twisted(self, request: ScrapflyScrapyRequest, spider: ScrapflySpider) -> Deferred:
        from twisted.internet import reactor
        from twisted.web.client import Agent
        from twisted.web.http_headers import Headers

        request_data = spider.scrapfly_client._scrape_request(scrape_config=request.scrape_config)

        uri = '%s?%s' % (request_data['url'], urlencode(request_data['params']))

        request_kwargs = {
            'method': request_data['method'].encode('utf-8'),
            'uri': uri.encode('utf-8'),
            'headers': Headers({name: [value] for name, value in request_data['headers'].items()})
        }

        if request_data['method'] in ['POST', 'PUT', 'PATCH']:
            request_kwargs['bodyProducer'] = BodyProducer(request_data['data'].encode('utf-8'))

        d = Agent(reactor).request(**request_kwargs)
        d.addCallback(self._cb_bodydone, request, spider)

        return d

    def _cb_bodydone(self, twisted_response, request:ScrapflyScrapyRequest, spider:ScrapflySpider) -> Deferred:

        headers = CaseInsensitiveDict()
        status_code = twisted_response.code
        reason = twisted_response.phrase.decode('utf-8')

        for name, values in twisted_response.headers.getAllRawHeaders():
            headers[name.decode('utf-8')] = '; '.join([value.decode('utf-8') for value in values])

        deferred = Deferred()
        body_receiver = BodyReceiver(deferred)

        def on_body_downloaded(body):
            if 'content-encoding' in headers:
                if headers['content-encoding'] == 'gzip':
                    body = zlib.decompress(body, 16+zlib.MAX_WBITS)
                elif headers['content-encoding'] == 'br':
                    try:
                        try:
                            import brotlicffi as brotli
                        except ImportError:
                            import brotli
                    except ImportError:
                        print('You must run pip install scrapfly-sdk[speedups] - brotli is missing - or disable brotli compression')
                        raise

                    body = brotli.decompress(body)

            response = requests.Response()
            response.status_code = status_code
            response.reason = reason
            response._content = body

            response.headers.update(headers)
            response.url = request.url

            return spider.scrapfly_client._handle_response(response=response, scrape_config=request.scrape_config)

        deferred.addCallback(on_body_downloaded)
        twisted_response.deliverBody(body_receiver)

        return deferred


class BinaryBody(BytesIO):

    def __init__(self, body:BytesIO):
        self.body = body
        BytesIO.__init__(self)

    def encode(self, encoding:str):
        pass


class BodyReceiver(Protocol):

    def __init__(self, deferred:Deferred):
        self.deferred = deferred
        self.content = BytesIO()

    def dataReceived(self, bytes):
        self.content.write(bytes)

    def connectionLost(self, reason):
        self.deferred.callback(self.content.getvalue())


@implementer(IBodyProducer)
class BodyProducer(object):
    def __init__(self, body):
        self.body = body
        self.length = len(body)

    def startProducing(self, consumer):
        consumer.write(self.body)
        return succeed(None)

    def pauseProducing(self):
        pass

    def stopProducing(self):
        pass
