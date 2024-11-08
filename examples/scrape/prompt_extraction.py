import json
from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse

scrapfly = ScrapflyClient(key='__API_KEY__')

# Use LLM prompts to automatically extract data from a web page response
api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://web-scraping.dev/product/1',
    render_js=True,
    extraction_prompt='Extract the product specification in json format'
))

# extraction results
print (json.dumps(api_response.scrape_result['extracted_data'], indent=2))
