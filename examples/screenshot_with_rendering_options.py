from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse
from scrapfly.scrape_config import ScreenshotFlag

# to get an API key, sign up at https://scrapfly.io
scrapfly = ScrapflyClient(key='__API_KEY__')

api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://web-scraping.dev/products',
    render_js=True,
    screenshots={
        'main': 'fullpage'
    },
    screenshot_flags=[
        ScreenshotFlag.LOAD_IMAGES, # Enable image rendering with the request, add extra usage for the bndwidth consumed
        ScreenshotFlag.DARK_MODE, # Enable dark mode display
        ScreenshotFlag.BLOCK_BANNERS, # Block cookies banners and overlay that cover the screen
        ScreenshotFlag.HIGH_QUALITY, # No compression on the output image
        ScreenshotFlag.PRINT_MEDIA_FORMAT # Render the page in the print mode
    ]
))

scrapfly.save_screenshot(api_response, name='main')
