import asyncio
import logging as logger
from sys import stdout
from scrapfly import ScrapeConfig, ScrapflyClient

scrapfly = ScrapflyClient(key='__API_KEY__', max_concurrency=8)

scrapfly_logger = logger.getLogger('scrapfly')
scrapfly_logger.setLevel(logger.DEBUG)
logger.StreamHandler(stdout)

async def main():
    scrape_configs = [
        ScrapeConfig(url='https://httpbin.dev/anything'),
        ScrapeConfig(url='https://httpbin.dev/anything'),
        ScrapeConfig(url='https://httpbin.dev/anything'),
        ScrapeConfig(url='https://httpbin.dev/anything')
    ]

    async for result in scrapfly.concurrent_scrape(scrape_configs):
        print(result)

asyncio.run(main())
