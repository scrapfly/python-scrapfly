from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse
from scrapfly.errors import ExtraUsageForbidden

# to get an API key, sign up at https://scrapfly.io
scrapfly = ScrapflyClient(key='__API_KEY__')

response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(url='https://httpbin.dev/status/200'))

try:
    response.prevent_extra_usage()
except ExtraUsageForbidden:
    print('I might stop my scraper')


print(response.remaining_quota)
print(response.cost)
print(response.duration_ms)
