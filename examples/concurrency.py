import asyncio
import logging as logger
from sys import stdout
from scrapfly import ScrapeConfig, ScrapflyClient

scrapfly = ScrapflyClient(key='__API_KEY__', max_concurrency=8)

scrapfly_logger = logger.getLogger('scrapfly')
scrapfly_logger.setLevel(logger.DEBUG)
logger.StreamHandler(stdout)

async def main():
    results = await scrapfly.concurrent_scrape(scrape_configs=[
        ScrapeConfig(url='http://httpbin.org/anything', render_js=True),
        ScrapeConfig(url='http://httpbin.org/anything', render_js=True),
        ScrapeConfig(url='http://httpbin.org/anything', render_js=True),
        ScrapeConfig(url='http://httpbin.org/anything', render_js=True)
    ])


    print(results)

asyncio.run(main())
