from contextlib import suppress
from dataclasses import dataclass
from pprint import pprint
from urllib.parse import urljoin
from typing import Optional

from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse


scrapfly = ScrapflyClient(key="YOUR API KEY")  # <--- Add your API KEY here!

api_response: ScrapeApiResponse = scrapfly.scrape(
    ScrapeConfig(
        url="https://news.ycombinator.com/",
    )
)


@dataclass
class Article:
    title:Optional[str]=None
    rank:Optional[int]=None
    link:Optional[str]=None
    user:Optional[str]=None
    score:Optional[int]=None
    comments:Optional[int]=None

    def is_valid(self) -> bool:
        if self.title is None or self.link is None:
            return False

        return True


articles = []

# all articles are in rows with class "athing"
items = api_response.selector.css("tr.athing")
for item in items:
    article = Article(
        title=item.css(".titleline a::text").get(),
        link=item.css(".titleline a::attr(href)").get(),
        rank=int(item.css("span.rank::text").get("").strip('.')),
    )
    # article meta information is in the next table row:
    item_meta = item.xpath("following-sibling::tr")[0]
    comments = item_meta.css(".subline>a:last-child::attr(href)").get()
    if comments:  # comments are not always present, check and turn to absolute url
        article.comments = urljoin(api_response.context["url"], comments)
    with suppress(IndexError):  # score is not always present
        article.score = int(item_meta.css(".score::text").re("(\d+) points")[0])
    article.user = item_meta.css(".hnuser::text").get()
    if article.is_valid():
        articles.append(article)
    else:
        print("invalid article: ", article)

pprint(articles)
