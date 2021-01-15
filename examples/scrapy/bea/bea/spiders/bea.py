from scrapfly import ScrapeConfig
from scrapfly.scrapy import ScrapflyMiddleware, ScrapflyScrapyRequest, ScrapflySpider, ScrapflyScrapyResponse


class BEA(ScrapflySpider):
    name = "bea"

    allowed_domains = ["www.bea.aero", "bea.aero"]
    start_urls = [ScrapeConfig("https://bea.aero/en/investigation-reports/notified-events/?tx_news_pi1%5Baction%5D=searchResult&tx_news_pi1%5Bcontroller%5D=News&tx_news_pi1%5BfacetAction%5D=add&tx_news_pi1%5BfacetTitle%5D=year_intS&tx_news_pi1%5BfacetValue%5D=2016&cHash=408c483eae88344bf001f9cdbf653010")]

    def parse(self, response:ScrapflyScrapyResponse):
        for href in response.css('h1.search-entry__title > a::attr(href)').extract():
            yield ScrapflyScrapyRequest(
                scrape_config=ScrapeConfig(url=response.urljoin(href)),
                callback=self.parse_report
            )

    def parse_report(self, response:ScrapflyScrapyResponse):
        for el in response.css('li > a[href$=".pdf"]:first-child'):
            yield ScrapflyScrapyRequest(
                scrape_config=ScrapeConfig(url=response.urljoin(el.attrib['href'])),
                callback=self.save_pdf
            )

    def save_pdf(self, response:ScrapflyScrapyResponse):
        response.sink(path='pdf', name=response.url.split('/')[-1])
