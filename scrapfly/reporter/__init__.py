from typing import Tuple, Callable, Optional
from .NoopReporter import NoopReporter
from .PrintReporter import PrintReporter
from .ChainReporter import ChainReporter

__all__:Tuple[str, ...] = (
    'NoopReporter',
    'PrintReporter',
    'ChainReporter'
)

from .. import ScrapflyError, ScrapeApiResponse


class Reporter:

    reporter:Callable

    def __init__(self, reporter:Callable):
        self.reporter = reporter

    def report(self, error:Optional[BaseException]=None, scrape_api_response:Optional[ScrapeApiResponse]=None):
        api_response = scrape_api_response

        if error is not None and api_response is None and isinstance(error, ScrapflyError):
            api_response:Optional[ScrapeApiResponse] = error.api_response

        self.reporter(error, api_response)
