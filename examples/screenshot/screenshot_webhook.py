from scrapfly import ScreenshotConfig, ScrapflyClient, ScreenshotApiResponse
from scrapfly.screenshot_config import Options, Format

scrapfly = ScrapflyClient(key='__API_KEY__')

# Screenshot API supports webhooks. When used, Scrapfly will immediately return a 201 and accept your request.
# Then the scheduler will automatically call your webhook URL with the extraction result.
# Crete a new webhook from: https://scrapfly.io/dashboard/webhook
screenshot_api_response: ScreenshotApiResponse = scrapfly.screenshot(
    screenshot_config=ScreenshotConfig(
        url='https://web-scraping.dev/products',
        format=Format.PNG,
        options=[
            Options.LOAD_IMAGES
        ],
        webhook='my-webhook' # specify the webhook name
    )
)

# raw API response
print(screenshot_api_response.result)
{
    'job_uuid': 'a0e6f3e8-be35-438a-942a-be77aa545d30',
    'success': True,
    'webhook_name': 'my-webhook',
    'webhook_queue_limit': 10000,
    'webhook_queued_element': 7,
    'webhook_uuid': 'cdf37252-fea7-4267-a568-aa0e5964ee21'
}