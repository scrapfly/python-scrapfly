from scrapy import Item, Field, Request
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

    def start_requests(self):
        yield ScrapflyScrapyRequest(ScrapeConfig("https://web-scraping.dev/product/1", render_js=True), callback=self.parse, errback=self.error_handler, dont_filter=True)
        # yield ScrapflyScrapyRequest(ScrapeConfig("https://web-scraping.dev/product/2"), callback=self.parse, errback=self.error_handler, dont_filter=True)
        # yield ScrapflyScrapyRequest(ScrapeConfig("https://web-scraping.dev/product/3", country="US"), callback=self.parse, errback=self.error_handler, dont_filter=True)
        # yield ScrapflyScrapyRequest(ScrapeConfig("https://web-scraping.dev/product/4", proxy_pool=ScrapeConfig.PUBLIC_RESIDENTIAL_POOL), callback=self.parse, errback=self.error_handler, dont_filter=True)
        # yield ScrapflyScrapyRequest(ScrapeConfig("https://httpbin.dev/status/404"), callback=self.parse, errback=self.error_handler, dont_filter=True)
        
        # Regular Scrapy Request without using Scrapfly
        # yield Request(
        #     "https://web-scraping.dev/product/1",
        #     callback=self.parse
        # )
    
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

        item['name'] = response.css('h3.product-title::text').get()
        item['price'] = response.css('span.product-price::text').get()
        item['description'] = response.css('p.product-description::text').get()

        yield item