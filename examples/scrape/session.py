from pprint import pprint
from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse
scrapfly = ScrapflyClient(key='__API_KEY__')

api_response:ScrapeApiResponse = scrapfly.scrape(ScrapeConfig(url='https://httpbin.dev/cookies/set?k1=v1&k2=v2&k3=v3', session='test'))
print("=== Initiated Session ===")
pprint(api_response.context['session'])

api_response:ScrapeApiResponse = scrapfly.scrape(ScrapeConfig(url='https://httpbin.dev/anything', session='test'))

print("=== Request headers")
pprint(api_response.scrape_result['request_headers'])

print("=== Response === ")
print(api_response.scrape_result['content'])
