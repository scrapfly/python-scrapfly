import json
from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse

scrapfly = ScrapflyClient(key='__API_KEY__')

# use the AI auto extraction models for common web pages types:
# for the available models, refer to https://scrapfly.io/docs/extraction-api/automatic-ai#models 
api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://web-scraping.dev/product/1',
    render_js=True,
    extraction_model='product'
))

# extraction results
print (json.dumps(api_response.scrape_result['extracted_data'], indent=2))
