from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse

# to get an API key, sign up at https://scrapfly.io
scrapfly = ScrapflyClient(key='__API_KEY__')

api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://tools.scrapfly.io/api/info/ip',
    country="nl"
))

print(api_response.context['proxy'])
print(api_response.scrape_result['content'])

api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://tools.scrapfly.io/api/info/ip',
    country="de"
))

print(api_response.context['proxy'])
print(api_response.scrape_result['content'])
