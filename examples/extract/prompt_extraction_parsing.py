from scrapfly import ScrapeConfig, ExtractionConfig, ScrapflyClient, ScrapeApiResponse, ExtractionApiResponse

scrapfly = ScrapflyClient(key='__API_KEY__')

# First, scrape the web page to retrieve its HTML
api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(
    url='https://web-scraping.dev/products',
    render_js=True
))

html = api_response.content

# In this example, we'll pass a detailed extraction prompt
extraction_api_response:ExtractionApiResponse = scrapfly.extract(
    extraction_config=ExtractionConfig(
        body=html, # pass the HTML content
        content_type='text/html', # content data type
        charset='utf-8', # passed content charset, use `auto` if you aren't sure
        extraction_prompt="""
        extract product data in JSON for the following fields:
        name: product name.
        image: product image.
        description: product description.
        flavor: this field doesn't exist in the HTML, extract it from the product description.
        price: product price. 
        """ 
    )
)

# result
extraction_api_response.extraction_result['data']
# or
print(extraction_api_response.data)
'''
[
  {
    'name': 'Box of Chocolate Candy',
    'image': 'https://web-scraping.dev/assets/products/orange-chocolate-box-medium-1.webp',
    'description': "Indulge your sweet tooth with our Box of Chocolate Candy. Each box contains an assortment of rich, flavorful chocolates with a smooth, creamy filling. Choose from a variety of flavors including zesty orange and sweet cherry. Whether you're looking for the perfect gift or just want to treat yourself, our Box of Chocolate Candy is sure to satisfy.",
    'flavor': 'zesty orange and sweet cherry',
    'price': '24.99'
  },
  ....
]
'''


# result content_type
extraction_api_response.extraction_result['content_type']
# or
print(extraction_api_response.content_type)
'application/json'
