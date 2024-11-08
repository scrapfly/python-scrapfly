import json
from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse

scrapfly = ScrapflyClient(key='__API_KEY__')

# extraction template for HTML parsing instructions. It accepts the following:
# selectors: CSS, XPath, JMESPath, Regex, Nested (nesting multiple selector types)
# extractors: extracts commonly accessed data types: price, image, links, emails
# formatters: transforms the extracted data for common methods: lowercase, uppercase, datatime, etc.
# refer to the docs for more details: https://scrapfly.io/docs/extraction-api/rules-and-template#rules
extraction_template = {
    "selectors": [
        {
            "name": "description",
            "query": "p.product-description::text",
            "type": "css"
        },
        {
            "name": "price_block",
            "nested": [
                {
                    "extractor": {
                        "name": "price"
                    },
                    "formatters": [
                        {
                            "args": {
                                "key": "currency"
                            },
                            "name": "pick"
                        }
                    ],
                    "name": "price_regex",
                    "options": {
                        "content": "text",
                        "dotall": True,
                        "ignorecase": True,
                        "multiline": False
                    },
                    "query": "(\\$\\d{2}\\.\\d{2})",
                    "type": "regex"
                }
            ],
            "query": ".product-data div.price",
            "type": "css"
        },
        {
            "name": "price_from_html",
            "nested": [
                {
                    "formatters": [
                        {
                            "name": "uppercase"
                        },
                        {
                            "name": "remove_html"
                        }
                    ],
                    "name": "price_html_regex",
                    "nested": [
                        {
                            "multiple": True,
                            "name": "price regex",
                            "query": ".+",
                            "type": "regex"
                        }
                    ],
                    "query": ".+",
                    "type": "regex"
                }
            ],
            "query": ".product-data div.price",
            "type": "css"
        },
        {
            "extractor": {
                "name": "price"
            },
            "name": "price",
            "query": "span.product-price::text",
            "type": "css"
        },
        {
            "formatters": [
                {
                    "name": "absolute_url"
                },
                {
                    "name": "unique"
                }
            ],
            "multiple": True,
            "name": "page_links",
            "query": "//a/@href",
            "type": "xpath"
        },
        {
            "formatters": [
                {
                    "name": "absolute_url"
                },
                {
                    "name": "unique"
                }
            ],
            "multiple": True,
            "name": "page_images",
            "query": "//img/@src",
            "type": "xpath"
        },
        {
            "name": "reviews",
            "nested": [
                {
                    "cast": "float",
                    "name": "rating",
                    "query": "count(//svg)",
                    "type": "xpath"
                },
                {
                    "formatters": [
                        {
                            "args": {
                                "format": "%d-%m-%Y"
                            },
                            "name": "datetime"
                        }
                    ],
                    "name": "date",
                    "query": "//span[1]/text()",
                    "type": "xpath"
                },
                {
                    "name": "text",
                    "query": "//p[1]/text()",
                    "type": "xpath"
                }
            ],
            "query": "#reviews > div.review",
            "type": "css"
        }
    ],
    "source": "html"
}

# Scrape the web page and utilize the extraction template for auto extraction
api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://web-scraping.dev/product/1',
    render_js=True,
    extraction_ephemeral_template=extraction_template
))

# extraction results
print (json.dumps(api_response.scrape_result['extracted_data'], indent=2))
