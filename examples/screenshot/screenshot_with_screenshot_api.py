from scrapfly import ScreenshotConfig, ScrapflyClient, ScreenshotApiResponse
from scrapfly.screenshot_config import Options, Format

scrapfly = ScrapflyClient(key='__API_KEY__')

screenshot_api_response: ScreenshotApiResponse = scrapfly.screenshot(
    screenshot_config=ScreenshotConfig(
        url='https://web-scraping.dev/products',
        format=Format.PNG,
        options=[
            Options.LOAD_IMAGES, # Enable image rendering with the request, add extra usage for the bndwidth consumed
            Options.DARK_MODE, # Enable dark mode display
            Options.BLOCK_BANNERS, # Block cookies banners and overlay that cover the screen
            Options.PRINT_MEDIA_FORMAT # Render the page in the print mode
        ],
        resolution='1920x1080', # Screenshot resolution
        rendering_wait=5000, # Delay in milliseconds to wait after the page was loaded
        wait_for_selector='div.products-wrap', # XPath or CSS selector to wait for
        auto_scroll=True, # Whether to automatically scroll down to the bottom of the page
    )
)

# screenshot metadata
screenshot_format = screenshot_api_response.metadata

# screenshot format
screenshot_format = screenshot_api_response.metadata['format']

# screenshot binary
screenshot_binary = screenshot_api_response.image

# save the screenshot binary
scrapfly.save_screenshot_api(screenshot_api_response, "products", path="screenshots")