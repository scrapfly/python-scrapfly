from dataclasses import dataclass
from pprint import pprint
from typing import Optional

from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse


scrapfly = ScrapflyClient(key="YOUR API KEY")  # <--- Add your API KEY here!

api_response: ScrapeApiResponse = scrapfly.scrape(
    ScrapeConfig(
        url="https://web-scraping.dev/products",
    )
)


@dataclass
class Product:
    title: Optional[str] = None
    link: Optional[str] = None
    description: Optional[str] = None
    price: Optional[float] = None

    def is_valid(self) -> bool:
        if self.title is None or self.link is None:
            return False

        return True


products = []

# every product is a row with the classes "row product"
for item in api_response.selector.css("div.row.product"):
    price = item.css(".price::text").get()
    product = Product(
        title=item.css("h3 a::text").get(),
        link=item.css("h3 a::attr(href)").get(),
        description=item.css(".short-description::text").get(),
        price=float(price) if price else None,
    )
    if product.is_valid():
        products.append(product)
    else:
        print("invalid product: ", product)

pprint(products)
