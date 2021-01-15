from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse

scrapfly = ScrapflyClient(key='__API_KEY__')

print('===== HEAD request =====')

api_response:ScrapeApiResponse = scrapfly.scrape(ScrapeConfig(
    url='https://httpbin.org/anything',
    method='HEAD'
))

# HEAD do not have body, so API response is truncate to strict minimum (headers, status, reason of upstream
print(api_response.result)

print('======== Default Body Url Encode ========')
api_response:ScrapeApiResponse = scrapfly.scrape(ScrapeConfig(
    url='https://httpbin.org/anything',
    method='POST',
    data={'hello': 'world'},
    headers={'X-Scrapfly': 'Yes'}
))

print(api_response.scrape_result['content'])

print('======== Json content-type ======== ')

api_response:ScrapeApiResponse = scrapfly.scrape(ScrapeConfig(
    url='https://httpbin.org/anything',
    method='POST',
    data={'hello': 'world'},
    headers={'X-Scrapfly': 'Yes', 'content-type': 'application/json'}
))

print(api_response.scrape_result['content'])
