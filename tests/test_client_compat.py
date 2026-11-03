"""ScrapflyClient on top of ScrapflyApi keeps the surface it had: methods, private hooks and module names."""
import inspect
import json

import pytest
import requests

from scrapfly import ScrapeApiResponse, ScrapeConfig, ScrapflyClient
from scrapfly import api

pytestmark = pytest.mark.unit

KEY = 'scp-test-00000000000000000000000000000000'


def envelope(content, format: str = 'text') -> dict:
    return {
        'config': {'url': 'https://web-scraping.dev/', 'headers': {}},
        'context': {},
        'result': {
            'status': 'DONE', 'success': True, 'status_code': 200, 'reason': 'OK', 'error': None,
            'content': content, 'format': format, 'request_headers': {}, 'response_headers': {},
            'duration': 0.1, 'log_url': 'https://scrapfly.io/dashboard/monitoring/log/01',
        },
    }


def reply(payload, status: int = 200, url: str = 'https://api.scrapfly.io/scrape') -> requests.Response:
    response = requests.Response()
    response.status_code = status
    response.headers['content-type'] = 'application/json'
    response._content = json.dumps(payload).encode()
    response.url = url
    response.request = requests.Request(method='GET', url=url).prepare()

    return response


def stubbed(handler) -> ScrapflyClient:
    client = ScrapflyClient(key=KEY)
    client.__dict__['_http_handler'] = handler

    return client


def test_operations_are_plain_methods():
    assert inspect.isfunction(ScrapflyClient.scrape)
    assert inspect.ismethod(ScrapflyClient(key=KEY).scrape)
    assert list(inspect.signature(ScrapflyClient.scrape).parameters) == ['self', 'scrape_config', 'no_raise']
    assert not inspect.isgeneratorfunction(ScrapflyClient.scrape_batch)
    assert inspect.signature(ScrapflyClient.scrape).return_annotation is ScrapeApiResponse
    assert 'Scrape a website' in ScrapflyClient.scrape.__doc__


def test_an_operation_called_on_the_class_takes_the_client():
    client = stubbed(lambda **kwargs: reply(envelope('ok')))

    assert ScrapflyClient.scrape(client, ScrapeConfig(url='https://web-scraping.dev/')).content == 'ok'


def test_a_subclass_override_is_kept():
    class Client(ScrapflyClient):
        def account(self):
            return 'overridden'

    assert Client(key=KEY).account() == 'overridden'


def test_handle_response_fetches_large_content_as_before():
    """The Scrapy downloader hands its own response to _handle_response."""
    seen = []

    def handler(**kwargs):
        seen.append(kwargs['url'])
        response = requests.Response()
        response.status_code = 200
        response.headers['content-type'] = 'text/plain'
        response._content = b'large text'

        return response

    client = stubbed(handler)
    scrape_config = ScrapeConfig(url='https://web-scraping.dev/')
    api_response = client._handle_response(reply(envelope('https://api.scrapfly.io/scrape/clob/01', format='clob')), scrape_config)

    assert isinstance(api_response, ScrapeApiResponse)
    assert api_response.scrape_result['content'] == 'large text'
    assert seen == ['https://api.scrapfly.io/scrape/clob/01']


def test_resilient_scrape_retries_a_scrapfly_error(monkeypatch):
    monkeypatch.setattr(api, 'retry_delay', lambda attempt: 0)
    replies = [
        reply({'code': 'ERR::API::INTERNAL_ERROR', 'error_id': '4d1a5b2e-0000-4000-8000-000000000000', 'http_code': 503,
               'message': 'busy', 'reason': 'Service Unavailable', 'retryable': True, 'links': {}}, status=503),
        reply(envelope('ok')),
    ]
    client = stubbed(lambda **kwargs: replies.pop(0))

    assert client.resilient_scrape(ScrapeConfig(url='https://web-scraping.dev/')).content == 'ok'
    assert replies == []


def test_private_hooks_keep_their_signatures():
    for name, parameters in {
        '_handle_response': ['self', 'response', 'scrape_config'],
        '_handle_api_response': ['self', 'response', 'scrape_config', 'raise_on_upstream_error'],
        '_handle_scrape_large_objects': ['self', 'callback_url', 'format'],
        '_monitoring_request': ['self', 'path', 'params'],
        '_schedule_request': ['self', 'method', 'path', 'query', 'body'],
        '_create_schedule': ['self', 'path', 'config_key', 'config', 'request'],
        '_scrape_request': ['self', 'scrape_config'],
    }.items():
        assert list(inspect.signature(getattr(ScrapflyClient, name)).parameters) == parameters, name


def test_names_the_client_module_exported_are_still_there():
    from scrapfly.client import (  # noqa: F401
        HttpError, MonitoringAggregation, MonitoringTargetPeriod, NetworkError, ScrapeConfig, ScraperAPI, ScrapflyClient,
        ScrapflyError, ScreenshotConfig, UpstreamHttpError,
    )
