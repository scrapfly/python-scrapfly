from io import BytesIO
from typing import Union, Dict, Optional, TextIO

from scrapy.http import TextResponse, HtmlResponse, XmlResponse

from .. import ScrapeApiResponse, ScrapeConfig
from .request import ScrapflyScrapyRequest


class ScrapflyScrapyResponse(TextResponse):

    content:Union[str, BytesIO]
    scrape_api_response:ScrapeApiResponse

    context:Dict
    scrape_config:ScrapeConfig
    log_url:str
    status:str
    config:Dict
    success:bool
    duration:float
    format:str
    screenshots:Dict
    dns:Optional[Dict]
    ssl:Optional[Dict]
    iframes:Dict
    browser_data:Dict
    error:Optional[Dict]

    DEFAULT_ENCODING = 'utf-8'

    def __init__(self, request:ScrapflyScrapyRequest, scrape_api_response:ScrapeApiResponse):
        self.scrape_api_response = scrape_api_response
        self.content = self.scrape_api_response.scrape_result['content']

        self.context = self.scrape_api_response.context
        self.scrape_config = self.scrape_api_response.scrape_config
        self.log_url = self.scrape_api_response.scrape_result['log_url']
        self.status = self.scrape_api_response.scrape_result['status']
        self.success = self.scrape_api_response.scrape_result['success']
        self.duration = self.scrape_api_response.scrape_result['duration']
        self.format = self.scrape_api_response.scrape_result['format']
        self.screenshots = self.scrape_api_response.scrape_result['screenshots']
        self.dns = self.scrape_api_response.scrape_result['dns']
        self.ssl = self.scrape_api_response.scrape_result['ssl']
        self.iframes = self.scrape_api_response.scrape_result['iframes']
        self.browser_data = self.scrape_api_response.scrape_result['browser_data']
        self.error = self.scrape_api_response.scrape_result['error']
        self.ip_address = self.scrape_api_response.context['proxy']['ipv4'] if self.scrape_api_response.context['proxy'] else None

        if isinstance(self.content, str):
            content = self.content.encode('utf-8')
        elif isinstance(self.content, (BytesIO, TextIO)):
            content = self.content.read()
        else:
            raise RuntimeError('Unsupported body %s' % type(self.content))

        TextResponse.__init__(
            self,
            url=self.scrape_api_response.scrape_result['url'],
            status=self.scrape_api_response.scrape_result['status_code'],
            headers=self.scrape_api_response.scrape_result['response_headers'],
            body=content,
            request=request,
            ip_address=self.scrape_api_response.context['proxy']['ipv4']
        )

    @property
    def __class__(self):
        response_headers = self.scrape_api_response.scrape_result['response_headers']

        if 'content-type' in response_headers and response_headers['content-type'].find('text/html') >= 0:
            return HtmlResponse
        elif 'content-type' in response_headers and response_headers['content-type'].find('application/xml') >= 0:
            return XmlResponse
        else:
            return TextResponse

    def sink(self, path: Optional[str] = None, name: Optional[str] = None, file: Optional[Union[TextIO, BytesIO]] = None):
        self.scrape_api_response.sink(path=path, name=name, file=file)
