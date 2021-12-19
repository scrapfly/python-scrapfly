from typing import Optional

from scrapfly import ScrapeApiResponse


class NoopReporter:

    def __call__(self, error:Optional[Exception]=None, scrape_api_response:Optional[ScrapeApiResponse]=None):
        pass
