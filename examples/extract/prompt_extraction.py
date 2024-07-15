from scrapfly import ScrapeConfig, ExtractionConfig, ScrapflyClient, ScrapeApiResponse, ExtractionApiResponse

scrapfly = ScrapflyClient(key='__API_KEY__')

# First, scrape the web page to retrieve its HTML
api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://web-scraping.dev/products',
    render_js=True
))

html = api_response.content

# Second, pass the HTML and an extraction prompt
# In this example, we'll ask a question about the data
extraction_api_response:ExtractionApiResponse = scrapfly.extract(
    extraction_config=ExtractionConfig(
        body=html, # pass the HTML content
        content_type='text/html', # content data type
        charset='utf-8', # passed content charset, use `auto` if you aren't sure
        extraction_prompt='what is the flavor of the dark energy potion?' # LLM extraction prompt
    )
)

# result
extraction_api_response.extraction_result['data']
# or
print(extraction_api_response.data)
'The document says the Dark Red Energy Potion has a bold cherry cola flavor.'

# result content_type
extraction_api_response.extraction_result['content_type']
# or
print(extraction_api_response.content_type)
'text/plain'
