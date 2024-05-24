from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse
from scrapfly.scrape_config import ScreenshotFlag

# to get an API key, sign up at https://scrapfly.io
scrapfly = ScrapflyClient(key='__API_KEY__')

api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://web-scraping.dev/products/',
    render_js=True,
    screenshots={
        'main': 'fullpage'
    }
))


scrapfly.save_screenshot(api_response, name='main')

# If you want to load images in the rendered page you can use the ScreenshotFlag.LOAD_IMAGES flag
# See example below, also available on ScrapeConfig.screenshot_flags
# You can also directly screenshot a URL without saving the response

scrapfly.screenshot(
    url='https://web-scraping.dev/product/1',
    name="product.jpg",
    screenshot_flags=[ScreenshotFlag.LOAD_IMAGES, ScreenshotFlag.HIGH_QUALITY]
)
