from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse

scrapfly = ScrapflyClient(key='__API_KEY__')

scrape_config = ScrapeConfig(url='https://vau.aero/navdb/chart/VQPR.pdf')

api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config)
print(api_response.scrape_result['content']) # BytesIO Object

scrapfly.sink(api_response) # create file

