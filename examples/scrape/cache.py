from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse
scrapfly = ScrapflyClient(key='__API_KEY__')
scrape_config = ScrapeConfig(url='https://web-scraping.dev/products/', cache=True, cache_ttl=500)

api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config)
print(api_response.context['cache'])

api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config)
print(api_response.context['cache'])
