from scrapy.pipelines.files import FilesPipeline as ScrapyFilesPipeline
from scrapy.pipelines.images import ImagesPipeline as ScrapyImagesPipeline
from itemadapter import ItemAdapter

from . import ScrapflyScrapyRequest, ScrapflyScrapyResponse
from .. import ScrapeConfig


class FilesPipeline(ScrapyFilesPipeline):
    def get_media_requests(self, item, info):
        scrape_configs = ItemAdapter(item).get(self.files_urls_field, [])

        requests = []

        for config in scrape_configs:
            if isinstance(config, str): # string link - dummy convert
                config = scrape_config=ScrapeConfig(url=url)

            if isinstance(config, ScrapeConfig):
                requests.append(ScrapflyScrapyRequest(scrape_config=config))
            else:
                raise ValueError('FilesPipeline item must ScrapeConfig Object or string url')

        return requests

class ImagesPipeline(ScrapyImagesPipeline):
    def get_media_requests(self, item, info):
        scrape_configs = ItemAdapter(item).get(self.images_urls_field, [])

        requests = []

        for config in scrape_configs:
            if isinstance(config, str):  # string link - dummy convert
                config = scrape_config = ScrapeConfig(url=url)

            if isinstance(config, ScrapeConfig):
                requests.append(ScrapflyScrapyRequest(scrape_config=config))
            else:
                raise ValueError('ImagesPipeline item must ScrapeConfig Object or string url')

        return requests

