from scrapfly import ScrapeConfig
from scrapfly.scrapy import ScrapflyMiddleware, ScrapflyScrapyRequest, ScrapflySpider, ScrapflyScrapyResponse


class CovidSpider(ScrapflySpider):
    name = 'covid'
    allowed_domains = ['www.worldmeters.info/coronavirus']
    start_urls = [ScrapeConfig(url='https://www.worldometers.info/coronavirus')]

    def parse(self, response:ScrapflyScrapyResponse):
        rows = response.xpath('//*[@id="main_table_countries_today"]//tr[position()>1 and not(contains(@style,"display: none"))]')

        for row in rows:
            country = row.xpath(".//td[2]/a/text()").get()
            totalCase = row.xpath(".//td[3]/text()").get()
            totalDeath = row.xpath(".//td[5]/text()").get()
            totalRecovered = row.xpath(".//td[7]/text()").get()
            activeCase = row.xpath(".//td[8]/text()").get()
            seriousCritical = row.xpath(".//td[9]/text()").get()
            population = row.xpath(".//td[14]/text()").get()

            yield {
                "CountryName": country,
                "Total Case": totalCase,
                "Total Deaths": totalDeath,
                "Total Recovered": totalRecovered,
                "Active Cases": activeCase,
                "Critical Cases": seriousCritical,
                "Population": population
            }
