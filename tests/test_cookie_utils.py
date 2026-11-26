import pytest
from requests import Request, Response

from scrapfly import ScrapeConfig
from scrapfly.api_response import ScrapeApiResponse
from scrapfly.cookie_utils import parse_cookie_expires

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    'value',
    [
        'Wed, 21 Oct 2026 07:28:00 GMT',
        'Wed, 21-Oct-2026 07:28:00 GMT',
        'Wednesday, 21-Oct-26 07:28:00 GMT',
        'Wed Oct 21 07:28:00 2026',
    ],
)
def test_http_cookie_date_formats(value):
    assert parse_cookie_expires(value) == 1792567680.0


@pytest.mark.parametrize(
    'value, expected',
    [
        ('1792567680', 1792567680),
        ('1792567680.5', 1792567680.5),
        ('-1', -1),
        ('Wednesday, 21-Oct-69 07:28:00 GMT', 3149566080.0),
        ('Wednesday, 21-Oct-70 07:28:00 GMT', 25342080.0),
    ],
)
def test_cookie_expiration_epochs_and_two_digit_years(value, expected):
    assert parse_cookie_expires(value) == expected


@pytest.mark.parametrize(
    'value',
    [
        '',
        'not a date',
        '21 Oct 2026',
        'Wed, 21 Oct 2026 24:28:00 GMT',
        'Wed, 31 Feb 2026 07:28:00 GMT',
        'Wed, 21 Oct 1500 07:28:00 GMT',
    ],
)
def test_invalid_cookie_expiration(value):
    assert parse_cookie_expires(value) is None


def _upstream_response(set_cookie):
    url = 'https://web-scraping.dev'
    response = Response()
    response.status_code = 200
    response.reason = 'OK'
    response.url = url
    response.request = Request(method='GET', url=url).prepare()
    scrape_config = ScrapeConfig(url=url)
    api_response = ScrapeApiResponse(
        request=response.request,
        response=response,
        scrape_config=scrape_config,
        api_result={
            'config': scrape_config.__dict__,
            'context': {},
            'result': {
                'status': 'DONE',
                'success': True,
                'status_code': 200,
                'reason': 'OK',
                'format': 'text',
                'content': '',
                'request_headers': {},
                'response_headers': {'set-cookie': [set_cookie]},
                'url': url,
            },
        },
    )

    return api_response.upstream_result_into_response()


def test_cookie_expiration_reaches_upstream_response():
    response = _upstream_response('session=abc; Expires=Wed, 21-Oct-2026 07:28:00 GMT; Path=/')

    assert response.cookies['session'] == 'abc'
    assert response.cookies.get_dict()['session'] == 'abc'
    cookie = next(cookie for cookie in response.cookies if cookie.name == 'session')
    assert cookie.expires == 1792567680


def test_invalid_cookie_expiration_does_not_drop_cookie():
    response = _upstream_response('session=abc; Expires=invalid; Path=/')
    cookie = next(cookie for cookie in response.cookies if cookie.name == 'session')

    assert cookie.value == 'abc'
    assert cookie.expires is None
