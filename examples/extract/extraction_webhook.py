from scrapfly import ScrapeConfig, ExtractionConfig, ScrapflyClient, ScrapeApiResponse, ExtractionApiResponse

scrapfly = ScrapflyClient(key='__API_KEY__')

# First, scrape the web page to retrieve its HTML
api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://web-scraping.dev/products',
    render_js=True
))

html = api_response.content

# Extraction API supports webhooks. When used, Scrapfly will immediately return a 201 and accept your request.
# Then the scheduler will automatically call your webhook URL with the extraction result.
# Crete a new webhook from: https://scrapfly.io/dashboard/webhook
extraction_api_response:ExtractionApiResponse = scrapfly.extract(
    extraction_config=ExtractionConfig(
        body=html, # pass the scraped HTML content
        content_type='text/html',
        charset='utf-8',
        extraction_prompt='what is the flavor of the dark energy potion?',
        webhook='my-webhook' # specify the webhook name
    )
)

# raw API response
print(extraction_api_response.result)
{
    'job_uuid': '7a3aa96d-fb0e-4c45-9b01-7c42f295dcac',
    'success': True,
    'webhook_name': 'my-webhook',
    'webhook_queue_limit': 10000,
    'webhook_queued_element': 7,
    'webhook_uuid': 'd7131802-1eba-4cc4-a6fd-5da6c8cf1f35'    
}