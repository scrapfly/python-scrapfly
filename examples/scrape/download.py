from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse

# to get an API key, sign up at https://scrapfly.io
scrapfly = ScrapflyClient(key='__API_KEY__')

scrape_config = ScrapeConfig(url='https://httpbin.dev/image/jpeg')

api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config)
print(api_response.scrape_result['content']) # BytesIO Object

scrapfly.sink(api_response) # create file

