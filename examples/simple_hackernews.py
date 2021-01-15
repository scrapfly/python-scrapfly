import re
from contextlib import suppress
from dataclasses import dataclass
from typing import Optional
from pprint import pprint

from scrapfly import ScrapeConfig, ScrapflyClient, ScrapeApiResponse
from bs4 import BeautifulSoup

scrapfly = ScrapflyClient(key='__API_KEY__')

api_response:ScrapeApiResponse = scrapfly.scrape(scrape_config=ScrapeConfig(url='https://news.ycombinator.com/'))

soup = BeautifulSoup(api_response.scrape_result['content'], "html.parser")

@dataclass
class Article:
    title:Optional[str]=None
    rank:Optional[int]=None
    link:Optional[str]=None
    user:Optional[str]=None
    score:Optional[str]=None
    comments:Optional[str]=None

    def is_valid(self) -> bool:
        if self.title is None or self.link is None:
            return False

        return True

articles = []

for item in soup.find("table", {"class": "itemlist"}).find_all("tr", {"class": "athing"}):
    article = Article()

    article.rank = int(item.find("span", {"class": "rank"}).get_text().replace('.', ''))
    article.link = item.find("a", {"class": "storylink"})['href']
    article.title = item.find("a", {"class": "storylink"}).get_text()

    metadata = item.next_sibling()[1]
    score = metadata.find("span", {"class": "score"})

    if score is not None:
        with suppress(IndexError):
            article.score = int(re.findall(r"\d+", score.get_text())[0])

    user = metadata.find("a", {"class": {"hnuser"}})

    if user is not None:
        article.user = user.get_text()

    with suppress(IndexError):
        article.comments = int(re.findall(r"(\d+)\scomment?", metadata.get_text())[0])

    if article.is_valid() is True:
        articles.append(article)

pprint(articles)

scrapfly.sink(api_response)
