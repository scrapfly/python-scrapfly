"""Use msgpack wire encoding for per-part bodies in a batch.

Msgpack produces slightly smaller payloads than JSON and decodes faster.
Pass ``format='msgpack'`` to ``scrape_batch`` to opt in — the SDK handles
decoding transparently so callers consume results the same way as with
JSON.

Msgpack support requires the optional ``msgpack`` package:
    pip install scrapfly-sdk[speedups]
"""
from scrapfly import ScrapeConfig, ScrapflyClient
from scrapfly.errors import ScrapflyError

scrapfly = ScrapflyClient(key='__API_KEY__')

configs = [
    ScrapeConfig(url='https://web-scraping.dev/product/1', correlation_id='product-1'),
    ScrapeConfig(url='https://web-scraping.dev/product/2', correlation_id='product-2'),
]

for correlation_id, result in scrapfly.scrape_batch(configs, format='msgpack'):
    if isinstance(result, ScrapflyError):
        print(f'{correlation_id}: error {result.code}')
        continue

    sr = result.scrape_result
    print(f'{correlation_id}: status={sr["status_code"]}')
