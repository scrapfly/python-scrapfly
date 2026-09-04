"""Anti-bot bypass.

`unblocker` is the current name of the parameter. `asp` is its deprecated
alias and keeps working, so existing code needs no change.
"""

from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse

scrapfly = ScrapflyClient(key='__API_KEY__')

api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://amazon.com',
    unblocker=True
))
