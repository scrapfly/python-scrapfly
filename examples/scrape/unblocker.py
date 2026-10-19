"""Anti-bot bypass with the proxy pools.

`proxy_pool` takes ScrapeConfig.BASIC, ScrapeConfig.UNBLOCKER,
ScrapeConfig.UNBLOCKER_ULTRA or ScrapeConfig.AUTO. `unblocker=True` (or `asp=True`) is
deprecated: use `proxy_pool` (ScrapeConfig.UNBLOCKER_ULTRA for the Unblocker). The
migration guide covers requests written before the proxy pools:
https://scrapfly.io/new-pricing#legacy-spellings
"""

from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse

scrapfly = ScrapflyClient(key='__API_KEY__')

api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://amazon.com',
    proxy_pool=ScrapeConfig.UNBLOCKER
))
