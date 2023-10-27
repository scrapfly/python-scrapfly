from scrapy import Item, Field
from scrapy.exceptions import CloseSpider
from scrapy.spidermiddlewares.httperror import HttpError
from twisted.python.failure import Failure

from scrapfly import ScrapeConfig
from scrapfly.errors import ScraperAPIError, ApiHttpServerError
from scrapfly.scrapy import ScrapflyScrapyRequest, ScrapflySpider, ScrapflyScrapyResponse


class Product(Item):

    name = Field()
    price = Field()
    description = Field()

    # scrapy.pipelines.images.ImagesPipeline
    image_urls = Field()
    images = Field()


class Demo(ScrapflySpider):
    name = "demo"

    allowed_domains = ["web-scraping.dev", "httpbin.dev"]
    start_urls = [
        ScrapeConfig("https://web-scraping.dev/product/1", render_js=True),
        ScrapeConfig("https://web-scraping.dev/product/2"),
        ScrapeConfig("https://web-scraping.dev/product/3"),
        ScrapeConfig("https://web-scraping.dev/product/4"),
        ScrapeConfig("https://web-scraping.dev/product/5", render_js=True),
        ScrapeConfig("https://httpbin.dev/status/403", asp=True, retry=False), # it will fail on purpose
        ScrapeConfig("https://httpbin.dev/status/400"), # it will fail on purpose - will fall on scrapy.spidermiddlewares.httperror.HttpError
        ScrapeConfig("https://httpbin.dev/status/404"), # it will fail on purpose - will fall on scrapy.spidermiddlewares.httperror.HttpError
    ]

    def start_requests(self):
        for scrape_config in self.start_urls:
            yield ScrapflyScrapyRequest(scrape_config, callback=self.parse, errback=self.error_handler, dont_filter=True)

    def error_handler(self, failure:Failure):
        if failure.check(ScraperAPIError): # The scrape errored
            error_code = failure.value.code # https://scrapfly.io/docs/scrape-api/errors#web_scraping_api_error

            if error_code == "ERR::ASP::SHIELD_PROTECTION_FAILED":
                self.logger.warning("The url %s must be retried" % failure.request.url)
        elif failure.check(HttpError): # The scrape succeed but the target server returned a non success http code >=400
            response:ScrapflyScrapyResponse = failure.value.response

            if response.status == 404:
                self.logger.warning("The url %s returned a 404 http code - Page not found" % response.url)
            elif response.status == 500:
                raise CloseSpider(reason="The target server returned a 500 http code - Website down")

        elif failure.check(ApiHttpServerError): # Generic API error, config error, quota reached, etc
            self.logger.error(failure)
        else:
            self.logger.error(failure)

    def parse(self, response:ScrapflyScrapyResponse, **kwargs):
        item = Product()

        if response.status == 200:
            # make sure the url is absolute
            item['image_urls'] = [response.urljoin(response.css('img.product-img::attr(src)').get())]

        item['name'] = response.css('h3.product-title').get()
        item['price'] = response.css('span.product-price::text').get()
        item['description'] = response.css('p.product-description').get()

        yield item