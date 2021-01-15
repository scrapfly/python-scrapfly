from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse

scrapfly = ScrapflyClient(key='__API_KEY__')

api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://api.myip.com',
    country="nl"
))

print(api_response.context['proxy'])
print(api_response.scrape_result['content'])

api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://api.myip.com',
    country="de"
))

print(api_response.context['proxy'])
print(api_response.scrape_result['content'])
