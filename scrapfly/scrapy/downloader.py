import requests
import logging as logger
from io import BytesIO

import zlib

from requests.structures import CaseInsensitiveDict
from twisted.internet.protocol import Protocol
from twisted.web.iweb import IBodyProducer

from urllib.parse import urlencode

from twisted.web._newclient import Response
from twisted.internet.defer import succeed, Deferred
from twisted.web.client import Agent
from twisted.internet import reactor
from twisted.web.http_headers import Headers
from zope.interface import implementer

from . import ScrapflyScrapyRequest, ScrapflySpider, ScrapflyScrapyResponse

logger.getLogger('scrapfly')


class ScrapflyHTTPDownloader:

    def __init__(self, settings, crawler=None):
        self._crawler = crawler
        self.agent = Agent(reactor)

    @classmethod
    def from_crawler(cls, crawler):
        return cls(crawler.settings, crawler)

    def _cb_bodydone(self, twisted_response:Response, request:ScrapflyScrapyRequest, spider:ScrapflySpider) -> Deferred:

        headers = CaseInsensitiveDict()
        status_code = twisted_response.code
        reason = twisted_response.phrase.decode('utf-8')

        for name, values in twisted_response.headers.getAllRawHeaders():
            headers[name.decode('utf-8')] = '; '.join([value.decode('utf-8') for value in values])

        defered = Deferred()
        body_receiver = BodyReceiver(defered)

        if 'x-scrapfly-api-cost' in headers:
            self._crawler.stats.inc_value('scrapfly/api_call_cost', count=int(headers['x-scrapfly-api-cost']))

        def on_body_downloaded(body):
            if 'content-encoding' in headers:
                if headers['content-encoding'] == 'gzip':
                    body = zlib.decompress(body, 16+zlib.MAX_WBITS)
                elif headers['content-encoding'] == 'br':
                    try:
                        from brotli import brotli
                    except ImportError:
                        print('You must run pip install scrapfly-sdk[speedups]')
                        raise

                    body = brotli.decompress(body)

            response = requests.Response()
            response.status_code = status_code
            response.reason = reason
            response._content = body

            response.headers.update(headers)
            response.url = request.url

            return ScrapflyScrapyResponse(
                request=request,
                scrape_api_response=spider.scrapfly_client._handle_response(response=response, scrape_config=request.scrape_config)
            )

        defered.addCallback(on_body_downloaded)
        twisted_response.deliverBody(body_receiver)

        return defered

    def download_request(self, request, spider):
        if not isinstance(request, ScrapflyScrapyRequest) or not isinstance(spider, ScrapflySpider):
            return None

        request_data = spider.scrapfly_client._scrape_request(scrape_config=request.scrape_config)

        uri = '%s?%s' % (request_data['url'], urlencode(request_data['params']))

        request_kwargs = {
            'method': request_data['method'].encode('utf-8'),
            'uri': uri.encode('utf-8'),
            'headers': Headers({name: [value] for name, value in request_data['headers'].items()})
        }

        if request_data['method'] in ['POST', 'PUT', 'PATCH']:
            request_kwargs['bodyProducer'] = BodyProducer(request_data['body'].encode('utf-8'))

        d = self.agent.request(**request_kwargs)
        d.addCallback(self._cb_bodydone, request, spider)

        return d

    def close(self):
        pass


class BinaryBody(BytesIO):

    def __init__(self, body:BytesIO):
        self.body = body
        BytesIO.__init__(self)

    def encode(self, encoding:str):
        pass


class BodyReceiver(Protocol):

    def __init__(self, defered:Deferred):
        self.defered = defered
        self.content = BytesIO()

    def dataReceived(self, bytes):
        self.content.write(bytes)

    def connectionLost(self, reason):
        self.defered.callback(self.content.getvalue())


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
