"""Scrape multiple URLs in a single request using the Batch Scraping API.

`scrape_batch` accepts up to 100 ScrapeConfigs and yields each result as
soon as it's ready. Results arrive OUT OF ORDER — use `correlation_id` on
every config to match each result back to its originating request.
"""
from scrapfly import ScrapeConfig, ScrapflyClient
from scrapfly.errors import ScrapflyError

scrapfly = ScrapflyClient(key='__API_KEY__')

# Every config in a batch MUST carry a unique correlation_id.
configs = [
    ScrapeConfig(url='https://web-scraping.dev/product/1', correlation_id='product-1'),
    ScrapeConfig(url='https://web-scraping.dev/product/2', correlation_id='product-2'),
    ScrapeConfig(url='https://web-scraping.dev/product/3', correlation_id='product-3'),
]

for correlation_id, result in scrapfly.scrape_batch(configs):
    if isinstance(result, ScrapflyError):
        print(f'{correlation_id}: error {result.code}')
        continue

    sr = result.scrape_result
    print(f'{correlation_id}: status={sr["status_code"]} size={len(sr["content"])} bytes')
