"""Mix proxified and JSON-envelope scrapes in a single batch.

A config with `proxified_response=True` returns the raw upstream response
(HTML, JSON, binary, etc.) instead of Scrapfly's JSON envelope. In a batch,
proxified parts surface as a `requests.Response` object while normal parts
surface as a `ScrapeApiResponse`.
"""
from requests import Response
from scrapfly import ScrapeConfig, ScrapflyClient
from scrapfly.errors import ScrapflyError

scrapfly = ScrapflyClient(key='__API_KEY__')

configs = [
    # Proxified: raw upstream HTML + upstream headers + X-Scrapfly-* metadata.
    ScrapeConfig(
        url='https://web-scraping.dev/product/1',
        correlation_id='html',
        proxified_response=True,
    ),
    # Normal: Scrapfly JSON envelope with config, context, result.
    ScrapeConfig(url='https://web-scraping.dev/api/products', correlation_id='api'),
]

for correlation_id, result in scrapfly.scrape_batch(configs):
    if isinstance(result, ScrapflyError):
        print(f'{correlation_id}: error {result.code}')
        continue

    if isinstance(result, Response):
        # Proxified: raw upstream response.
        print(
            f'{correlation_id}: proxified status={result.status_code}'
            f' content-type={result.headers.get("Content-Type")}'
            f' body={len(result.content)} bytes'
        )
    else:
        # Standard ScrapeApiResponse.
        sr = result.scrape_result
        print(f'{correlation_id}: scrape status={sr["status_code"]} size={len(sr["content"])} bytes')
