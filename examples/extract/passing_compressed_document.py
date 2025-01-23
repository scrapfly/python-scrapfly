from scrapfly import ScrapeConfig, ExtractionConfig, ScrapflyClient, ScrapeApiResponse, ExtractionApiResponse
from scrapfly.extraction_config import CompressionFormat

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
        body=html,
        content_type='text/html',
        charset='utf-8',
        extraction_model='review_list',
        document_compression_format=CompressionFormat.GZIP # specify that compression format
        # If the body is not compressed, Scrapfly will automatically compress it based on the document_compression_format value
    )
)

# result
print(extraction_api_response.data)
