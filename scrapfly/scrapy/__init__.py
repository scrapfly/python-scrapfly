from typing import Tuple
from functools import cache

from .request import ScrapflyScrapyRequest
from .response import ScrapflyScrapyResponse
from .middleware import ScrapflyMiddleware
from .spider import ScrapflySpider, ScrapflyCrawlSpider
from .pipelines import FilesPipeline, ImagesPipeline

current_scrapy_version = 0

@cache
def comparable_version(version: str) -> int:
    l = [int(x, 10) for x in version.split('.')]
    l.reverse()
    return sum(x * (10 ** i) for i, x in enumerate(l))

try:
    from scrapy import __version__
    current_scrapy_version = comparable_version(__version__)
except ModuleNotFoundError:
    # Error handling
    pass


__all__:Tuple[str, ...] = (
    'ScrapflyScrapyRequest',
    'ScrapflyScrapyResponse',
    'ScrapflyMiddleware',
    'ScrapflySpider',
    'ScrapflyCrawlSpider',
    'FilesPipeline',
    'ImagesPipeline',
    'current_scrapy_version',
    'comparable_version'
)

