"""
A ScrapflySpider crawl through a fake Scrapfly API, printed as JSON: run by test_scrapy.py in a subprocess,
since a Twisted reactor cannot be started twice in one process.

Usage: python scrapy_crawl.py <mode>, mode being default (Scrapy's own reactor default), asyncio, or reactorless.
"""
import json
import logging
import sys
import threading
import warnings
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlsplit

PAGES = 3


class FakeApi(BaseHTTPRequestHandler):
    """Answers /account and /scrape as the Scrapfly API does, the page at /page/<n> linking to the next one."""

    def do_GET(self):
        split = urlsplit(self.path)
        query = parse_qs(split.query)

        if split.path == '/account':
            return self._json({'account': {'suspended': False}, 'subscription': {'max_concurrency': 4}, 'project': {'concurrency_limit': None}})

        url = query['url'][0]
        page = int(url.rsplit('/', 1)[1])

        if page == 2 and query.get('tags') and not self.server.retried:
            # One retryable API error, which ScrapflyMiddleware retries.
            self.server.retried = True

            return self._json({
                'code': 'ERR::SCRAPE::NETWORK_ERROR', 'error_id': '0', 'http_code': 503, 'message': 'busy', 'reason': 'Service Unavailable',
                'retryable': True, 'links': {},
            }, status=503, headers={'Retry-After': '1'})

        link = f'<a href="https://web-scraping.dev/page/{page + 1}">next</a>' if page < PAGES else ''
        self._json({
            'config': {'url': url, 'headers': {}},
            'context': {},
            'result': {
                'status': 'DONE', 'success': True, 'status_code': 200, 'reason': 'OK', 'error': None, 'url': url, 'format': 'text',
                'content': f'<html><body><h1>page {page}</h1>{link}</body></html>',
                'request_headers': {}, 'response_headers': {'content-type': 'text/html; charset=utf-8'},
                'duration': 0.1, 'log_url': 'https://scrapfly.io/dashboard/monitoring/log/01',
                'screenshots': {}, 'dns': None, 'ssl': None, 'iframes': [], 'browser_data': {},
            },
        })

    def _json(self, payload, status=200, headers=None):
        body = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Scrapfly-Api-Cost', '1')

        for name, value in (headers or {}).items():
            self.send_header(name, value)

        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):
        pass


class Warnings(logging.Handler):
    """Scrapy routes warnings to the py.warnings logger."""

    def __init__(self):
        super().__init__()
        self.messages = []

    def emit(self, record):
        self.messages.append(record.getMessage().strip().splitlines()[0][-300:])


def main(mode: str):
    warnings.simplefilter('always')
    caught = Warnings()
    logging.getLogger('py.warnings').addHandler(caught)

    server = ThreadingHTTPServer(('127.0.0.1', 0), FakeApi)
    server.retried = False
    threading.Thread(target=server.serve_forever, daemon=True).start()

    import scrapy
    from scrapy import signals
    from scrapy.crawler import CrawlerProcess

    from scrapfly import ScrapeConfig
    from scrapfly.scrapy import ScrapflyScrapyRequest, ScrapflySpider

    class Spider(ScrapflySpider):
        name = 'fake'
        start_urls = [ScrapeConfig(url='https://web-scraping.dev/page/1')]
        custom_settings = {'SCRAPFLY_MAX_API_RETRIES': 3}

        def parse(self, response):
            yield {'title': response.css('h1::text').get(), 'url': response.url}

            for href in response.css('a::attr(href)').getall():
                yield ScrapflyScrapyRequest(scrape_config=ScrapeConfig(url=href), callback=self.parse)

    settings = {
        'SCRAPFLY_API_KEY': 'scp-test-0000',
        'SCRAPFLY_HOST': f'http://127.0.0.1:{server.server_port}',
        'LOG_LEVEL': 'ERROR',
        'TELNETCONSOLE_ENABLED': False,
    }

    if mode == 'asyncio':
        settings['TWISTED_REACTOR'] = 'twisted.internet.asyncioreactor.AsyncioSelectorReactor'
    elif mode == 'default':
        settings['TWISTED_REACTOR'] = None
    elif mode == 'reactorless':
        settings['TWISTED_REACTOR_ENABLED'] = False

    items, errors = [], []

    # Signals hold their receivers weakly: these must stay referenced until the crawl ends.
    def on_item(item, **kwargs):
        items.append(item)

    def on_error(failure, **kwargs):
        errors.append(repr(failure.value))

    if mode == 'reactorless':
        from scrapy.crawler import AsyncCrawlerProcess as Process
    else:
        Process = CrawlerProcess

    process = Process(settings)
    crawler = process.create_crawler(Spider)
    crawler.signals.connect(on_item, signal=signals.item_scraped)
    crawler.signals.connect(on_error, signal=signals.spider_error)
    process.crawl(crawler)
    process.start()

    stats = crawler.stats.get_stats()
    print(json.dumps({
        'scrapy': scrapy.__version__,
        'mode': mode,
        'titles': sorted(item['title'] for item in items),
        'errors': errors,
        'retries': stats.get('scrapfly/api_retry/count', 0),
        'api_cost': stats.get('scrapfly/api_call_cost'),
        'finish_reason': stats.get('finish_reason'),
        'warnings': sorted(set(caught.messages)),
    }))


if __name__ == '__main__':
    main(sys.argv[1])
