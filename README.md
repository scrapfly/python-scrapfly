# Scrapfly SDK

## Installation

`pip install scrapfly-sdk`

You can also install extra dependencies

* `pip install "scrapfly-sdk[seepdup]"` for performance improvement
* `pip install "scrapfly-sdk[concurrency]"` for concurrency out of the box (asyncio / thread)
* `pip install "scrapfly-sdk[scrapy]"` for scrapy integration
* `pip install "scrapfly-sdk[all]"` Everything!

For use of built-in HTML parser (via `ScrapeApiResponse.selector` property) additional requirement of either [parsel](https://pypi.org/project/parsel/) or [scrapy](https://pypi.org/project/Scrapy/) is required.

## Get Your API Key

You can create a free account on [Scrapfly](https://scrapfly.io/register) to get your API Key.

* [Usage](https://scrapfly.io/docs/sdk/python)
* [Python API](https://scrapfly.github.io/python-scrapfly/scrapfly)
* [Open API 3 Spec](https://scrapfly.io/docs/openapi#get-/scrape) 
* [Scrapy Integration](https://scrapfly.io/docs/sdk/scrapy)

## Migration

### Migrate from 0.7.x to 0.8

asyncio-pool dependency has been dropped

`scrapfly.concurrent_scrape` is now an async generator. If the concurrency is `None` or not defined, the max concurrency allowed by
your current subscription is used.

```python
    async for result in scrapfly.concurrent_scrape(concurrency=10, scrape_configs=[ScrapConfig(...), ...]):
        print(result)
```

brotli args is deprecated and will be removed in the next minor. There is not benefit in most of case
versus gzip regarding and size and use more CPU.

### What's new

### 0.8.x

* Better error log
* Async/Improvement for concurrent scrape with asyncio
* Scrapy media pipeline are now supported out of the box



