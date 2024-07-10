from scrapfly import ScrapeConfig, ExtractionConfig, ScrapflyClient, ScrapeApiResponse, ExtractionApiResponse

scrapfly = ScrapflyClient(key='__API_KEY__')

# First, scrape the web page to retrieve its HTML
api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://web-scraping.dev/product/1',
    render_js=True
))

html = api_response.content

# extraction template for HTML parsing instructions. It accepts the following:
# selectors: CSS, XPath, JMESPath, Regex, Nested (nesting multiple selector types)
# extractors: extracts commonly accessed data types: price, image, links, emails
# formatters: transforms the extracted data for common methods: lowercase, uppercase, datatime, etc.
# refer to the docs for more details: https://scrapfly.io/docs/extraction-api/rules-and-template#rules
extraction_template = {
    "source": "html",
    "selectors": [    
        {
            "name": "title",
            "query": "h3.product-title::text",
            "type": "css",
            "formatters": [
                {
                    "name": "uppercase"
                }
            ],
        },
        {
            "name": "description",
            "query": "p.product-description::text",
            "type": "css"
        },
        {
            "extractor": {
                "name": "price"
            },
            "name": "price",
            "query": ".product-price::text",
            "type": "css"
        },
        {
            "name": "variants",
          	"query": "div.variants",
            "type": "css",
            "nested": [
                {
                    "name": "name",
                    "query": "//a[@data-variant-id]/@data-variant-id",
                    "type": "xpath",
                    "multiple": True,
                },
                {
                    "name": "link",
                    "query": "//a[@data-variant-id]/@href",
                    "type": "xpath",
                    "multiple": True,
                },
            ]
        },
        {
            "name": "reviews",
            "query": "div.review>p::text",
            "type": "css",
            "multiple": True,            
        }
    ]
}

extraction_api_response:ExtractionApiResponse = scrapfly.extract(
    extraction_config=ExtractionConfig(
        body=html, # pass the HTML content
        content_type='text/html', # content data type
        charset='utf-8', # passed content charset, use `auto` if you aren't sure
        epehemeral_template=extraction_template # declared template defintion or template name saved on the dashboard
    )
)

# result
extraction_api_response.data

# result content_type
extraction_api_response.content_type
'application/json'
