"""API-level error envelope -> typed exception.

The envelope is the only carrier of the error code, the retryable flag and the
doc link, and customers branch on `e.code`. These are offline: the envelopes
below are verbatim shapes taken from the API (note the 401, which carries no
`code` and no `links` at all).
"""
import pytest
from requests import Request, Response

from scrapfly import ScrapeConfig, ScreenshotConfig, ExtractionConfig
from scrapfly.api_response import ScrapeApiResponse, ScreenshotApiResponse, ExtractionApiResponse
from scrapfly.errors import (
    ApiHttpClientError,
    ApiHttpServerError,
    ExtractionAPIError,
    ScreenshotAPIError,
    ScrapflyError,
    api_error_args,
)

pytestmark = pytest.mark.unit


def _response(status_code: int, url: str = 'https://api.scrapfly.io/scrape') -> Response:
    response = Response()
    response.status_code = status_code
    response.reason = 'Bad Request'
    response.url = url
    response.request = Request(method='GET', url=url).prepare()

    return response


SCRAPE_CONFIG_ERROR = {
    'code': 'ERR::SCRAPE::CONFIG_ERROR',
    'error_id': '4d1a5b2e-0000-4000-8000-000000000000',
    'http_code': 400,
    'links': {
        'Getting Started': 'https://scrapfly.io/docs/scrape-api/getting-started',
        'Related Error Doc': 'https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::CONFIG_ERROR',
    },
    'message': 'Scrape Configuration Error',
    'reason': 'Bad Request',
    'retryable': False,
}

# A 401 from the API carries neither `code` nor `links`.
BAD_API_KEY = {
    'error_id': 'd8c9751a-0000-4000-8000-000000000000',
    'http_code': 401,
    'message': 'Invalid API key - make sure to provide it via `key` query parameter',
    'reason': 'Unauthorized',
}

EXTRACTION_CONFIG_ERROR = {
    'code': 'ERR::EXTRACTION::CONFIG_ERROR',
    'error_id': '6e710c8a-0000-4000-8000-000000000000',
    'http_code': 400,
    'links': [
        'https://scrapfly.io/docs/extraction-api/templates',
        'https://scrapfly.io/docs/extraction-api/rules-and-template',
    ],
    'message': 'Invalid extraction_template value.',
    'reason': 'Bad Request',
    'retryable': False,
}

THROTTLE = {
    'code': 'ERR::THROTTLE::MAX_CONCURRENT_REQUEST_EXCEEDED',
    'error_id': 'aa000000-0000-4000-8000-000000000000',
    'http_code': 429,
    'doc_url': 'https://scrapfly.io/docs/scrape-api/error/ERR::THROTTLE::MAX_CONCURRENT_REQUEST_EXCEEDED',
    'message': 'Too many concurrent requests',
    'reason': 'Too Many Requests',
    'retryable': True,
}


def test_scrape_api_error_carries_the_wire_code():
    api_response = ScrapeApiResponse(
        request=_response(400).request,
        response=_response(400),
        scrape_config=ScrapeConfig(url='https://httpbin.dev/html'),
        api_result=dict(SCRAPE_CONFIG_ERROR),
    )

    with pytest.raises(ApiHttpClientError) as info:
        api_response.raise_for_result(raise_on_upstream_error=True)

    assert info.value.code == 'ERR::SCRAPE::CONFIG_ERROR'
    assert info.value.resource == ScrapflyError.RESOURCE_SCRAPE
    assert info.value.http_status_code == 400
    assert info.value.is_retryable is False
    # The error-specific link, not the generic "Getting Started" beside it.
    assert info.value.documentation_url == SCRAPE_CONFIG_ERROR['links']['Related Error Doc']


def test_extraction_api_error_carries_the_wire_code():
    api_response = ExtractionApiResponse(
        request=_response(400).request,
        response=_response(400),
        extraction_config=ExtractionConfig(body=b'<html></html>', content_type='text/html'),
        api_result=dict(EXTRACTION_CONFIG_ERROR),
    )

    with pytest.raises(ExtractionAPIError) as info:
        api_response.raise_for_result(raise_on_upstream_error=True)

    assert info.value.code == 'ERR::EXTRACTION::CONFIG_ERROR'
    assert info.value.resource == 'EXTRACTION'
    assert info.value.documentation_url == EXTRACTION_CONFIG_ERROR['links'][0]


def test_screenshot_api_error_without_code_stays_typed():
    """The 401 envelope has no `code`: rendering it must not raise KeyError."""
    api_response = ScreenshotApiResponse(
        request=_response(401).request,
        response=_response(401),
        screenshot_config=ScreenshotConfig(url='https://httpbin.dev/html'),
        api_result=dict(BAD_API_KEY),
    )

    with pytest.raises(ScreenshotAPIError) as info:
        api_response.raise_for_result(raise_on_upstream_error=True)

    assert info.value.code == ''
    assert info.value.http_status_code == 401
    assert 'Invalid API key' in str(info.value)


def test_retryable_flag_reaches_the_exception():
    """scrapy's middleware retries on `is_retryable`, so the wire flag must survive."""
    api_response = ScrapeApiResponse(
        request=_response(429).request,
        response=_response(429),
        scrape_config=ScrapeConfig(url='https://httpbin.dev/html'),
        api_result=dict(THROTTLE),
    )

    with pytest.raises(ScrapflyError) as info:
        api_response.raise_for_result(raise_on_upstream_error=True)

    assert info.value.is_retryable is True
    assert info.value.code == 'ERR::THROTTLE::MAX_CONCURRENT_REQUEST_EXCEEDED'
    assert info.value.documentation_url == THROTTLE['doc_url']


def test_server_error_carries_the_wire_code():
    envelope = {
        'code': 'ERR::SCRAPE::INTERNAL_ERROR',
        'error_id': 'bb000000-0000-4000-8000-000000000000',
        'http_code': 500,
        'message': 'Internal error',
        'reason': 'Internal Server Error',
        'retryable': True,
    }

    api_response = ScrapeApiResponse(
        request=_response(500).request,
        response=_response(500),
        scrape_config=ScrapeConfig(url='https://httpbin.dev/html'),
        api_result=envelope,
    )

    with pytest.raises(ApiHttpServerError) as info:
        api_response.raise_for_result(raise_on_upstream_error=True)

    assert info.value.code == 'ERR::SCRAPE::INTERNAL_ERROR'
    assert info.value.is_retryable is True


def test_extraction_api_error_suppressed_when_upstream_errors_are_not_raised():
    api_response = ExtractionApiResponse(
        request=_response(400).request,
        response=_response(400),
        extraction_config=ExtractionConfig(body=b'<html></html>', content_type='text/html'),
        api_result=dict(EXTRACTION_CONFIG_ERROR),
    )

    api_response.raise_for_result(raise_on_upstream_error=False)


def test_api_error_args_tolerates_a_junk_envelope():
    args = api_error_args(None, http_status_code=502)

    assert args['code'] == ''
    assert args['resource'] is None
    assert args['http_status_code'] == 502
    assert args['is_retryable'] is False
    assert args['documentation_url'] is None

    # A code shape the SDK has not seen must not blow up the resource split.
    args = api_error_args({'code': 'ERR::SCRAPE::CONFIG::EXTRA', 'reason': 'Bad Request'}, http_status_code=400)

    assert args['resource'] == 'SCRAPE'
    assert args['message'] == 'Bad Request'
