from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse

scrapfly = ScrapflyClient(key='__API_KEY__')


# scrapfly.screenshot(url='https://news.ycombinator.com/', name="hackernews.jpg")

api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://news.ycombinator.com/',
    render_js=True,
    screenshots={
        'main': 'fullpage'
    }
))

for name, screenshot in api_response.scrape_result['screenshots'].items():
    with scrapfly as client:
        response = client.http_session.get(screenshot['url'])
        response.raise_for_status()
        client.sink(api_response, name=name+'.jpg', content=response.content)
