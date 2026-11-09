"""ScrapflySpider crawls through a fake Scrapfly API in every way the installed Scrapy runs: its reactors, and no reactor."""
import json
import subprocess
import sys
from pathlib import Path

import pytest

pytest.importorskip('scrapy')

from scrapy import crawler  # noqa: E402

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
    assert [warning for warning in result['warnings'] if 'scrapfly' in warning.lower()] == []
