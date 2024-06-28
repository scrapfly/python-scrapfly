from scrapfly import ScrapeConfig, ExtractionConfig, ScrapflyClient, ScrapeApiResponse, ExtractionApiResponse

scrapfly = ScrapflyClient(key='__API_KEY__')

# First, scrape the web page to retrieve its HTML
api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://web-scraping.dev/reviews',
    render_js=True
))

html = api_response.content

# use the AI auto extraction models for common web pages types:
# for the available models, refer to https://scrapfly.io/docs/extraction-api/automatic-ai#models 
extraction_api_response:ExtractionApiResponse = scrapfly.extract(
    extraction_config=ExtractionConfig(
        body=html, # pass the HTML content
        content_type='text/html', # content data type
        charset='utf-8', # passed content charset, use `auto` if you aren't sure
        url='https://web-scraping.dev/product/1', # when passed, used to transform relative URLs in the document into absolute URLs automatically
        extraction_model='review_list'
    )
)

# result
print(extraction_api_response.data)
