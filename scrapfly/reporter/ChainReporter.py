from typing import Callable, Tuple, Optional

from scrapfly import ScrapeApiResponse


class ChainReporter:
    reporters: Tuple[Callable]

    def __init__(self, *args:Tuple[Callable]):
        self.reporters = args

    def __call__(self, error:Optional[Exception]=None, scrape_api_response:Optional[ScrapeApiResponse]=None):
        [reporter(error, scrape_api_response) for reporter in self.reporters]
