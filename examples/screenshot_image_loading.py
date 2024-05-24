from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse

scrapfly = ScrapflyClient(key='__API_KEY__')

api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://web-scraping.dev/products',
    render_js=True,
    screenshots={
        'main': 'fullpage'
    },
    screenshot_flags=[
        "load_images", # Enable image rendering with the request, add extra usage for the bndwidth consumed
        "dark_mode", # Enable dark mode display
        "block_banners", # Block cookies banners and overlay that cover the screen
        "high_quality", # No compression on the output image
        "print_media_format" # Render the page in the print mode
    ]
))

for name, screenshot in api_response.scrape_result['screenshots'].items():
    with scrapfly as client:
        response = client.http_session.get(screenshot['url'])
        response.raise_for_status()
        client.sink(api_response, name=name+'.jpg', content=response.content)