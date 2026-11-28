"""
ScrapflySpider crawls through a fake Scrapfly API in every way the installed Scrapy runs: its reactors, and no reactor.
ScrapflyMiddleware retries a failed request, but not one whose read timed out.
"""
import asyncio
import json
import subprocess
import sys
from pathlib import Path

import httpx
import pytest

pytest.importorskip('scrapy')

from scrapy import Request, crawler  # noqa: E402
from twisted.web._newclient import ResponseNeverReceived  # noqa: E402

from scrapfly import ScrapflyError  # noqa: E402
from scrapfly.scrapy.middleware import ScrapflyMiddleware  # noqa: E402

pytestmark = pytest.mark.unit

CRAWL = Path(__file__).with_name('scrapy_crawl.py')

# The default reactor, the asyncio one, and from Scrapy 2.14 no reactor at all.
MODES = ['default', 'asyncio'] + (['reactorless'] if hasattr(crawler, 'AsyncCrawlerProcess') else [])


@pytest.mark.parametrize('mode', MODES)
def test_spider_crawls_follows_and_retries(mode):
    run = subprocess.run([sys.executable, str(CRAWL), mode], capture_output=True, text=True, timeout=180)
    assert run.stdout.strip(), run.stderr[-3000:]
    result = json.loads(run.stdout.strip().splitlines()[-1])

    assert result['titles'] == ['page 1', 'page 2', 'page 3'], run.stderr[-3000:]
    # A plain Request reaches Scrapy's own http handler, not the Scrapfly one again.
    assert result['plain'] == ([] if mode == 'reactorless' else ['plain']), run.stderr[-3000:]
    assert result['finish_reason'] == 'finished'
    # Page 2 answers one retryable error first: retried once, both answers billed.
    assert result['retries'] == 1
    assert result['api_cost'] == 4
    assert [warning for warning in result['warnings'] if 'scrapfly' in warning.partition(': ')[2].lower() or '/scrapfly/' in warning.partition(': ')[0]] == []


class RetryingSpider:
    """Records each failure ScrapflyMiddleware hands to retry()."""

    def __init__(self):
        self.retried = []

    def retry(self, request, reason, delay=None):
        self.retried.append(reason)


@pytest.mark.parametrize('exception,retried', [
    pytest.param(httpx.ReadTimeout('timed out'), False, id='read-timeout'),
    pytest.param(httpx.ConnectError('refused'), True, id='connect-error'),
    pytest.param(httpx.ConnectTimeout('timed out'), True, id='connect-timeout'),
    pytest.param(httpx.RemoteProtocolError('closed'), True, id='dropped-connection'),
    pytest.param(ResponseNeverReceived([]), True, id='twisted-dropped-connection'),
    pytest.param(ScrapflyError(message='busy', code='ERR::SCRAPE::NETWORK_ERROR', http_status_code=503, is_retryable=True), True, id='retryable-api-error'),
])
def test_the_middleware_retries_a_failure_but_a_read_timeout(exception, retried):
    spider = RetryingSpider()
    raised = None

    try:
        asyncio.run(ScrapflyMiddleware().process_exception(Request('https://web-scraping.dev/product/1'), exception, spider))
    except Exception as error:
        raised = error

    assert (spider.retried, raised) == (([exception], None) if retried else ([], exception))
