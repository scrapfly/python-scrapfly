from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse
from scrapfly.scrape_config import Format

scrapfly = ScrapflyClient(key='__API_KEY__')

api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://web-scraping.dev/products',
    # scrape the page data as markdown format supproted by LLMs.
    # None=raw(unchanged), other supported formats are: json, text, clean_html 
    format=Format.MARKDOWN
))

print(api_response.scrape_result["content"])