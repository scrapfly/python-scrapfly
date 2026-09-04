import base64
from typing import Dict, Optional, Tuple
from requests import Request, Response


class WebhookError(Exception):
    pass


class WebhookSignatureMissMatch(WebhookError):
    pass

class ContentError(Exception):
    pass

class ScrapflyError(Exception):
    KIND_HTTP_BAD_RESPONSE = 'HTTP_BAD_RESPONSE'
    KIND_SCRAPFLY_ERROR = 'SCRAPFLY_ERROR'

    RESOURCE_PROXY = 'PROXY'
    RESOURCE_THROTTLE = 'THROTTLE'
    RESOURCE_SCRAPE = 'SCRAPE'
    RESOURCE_ASP = 'ASP'
    RESOURCE_SCHEDULE = 'SCHEDULE'
    RESOURCE_WEBHOOK = 'WEBHOOK'
    RESOURCE_SESSION = 'SESSION'

    def __init__(
        self,
        message: str,
        code: str,
        http_status_code: int,
        resource: Optional[str]=None,
        is_retryable: bool = False,
        retry_delay: Optional[int] = None,
        retry_times: Optional[int] = None,
        documentation_url: Optional[str] = None,
        api_response: Optional['ApiResponse'] = None
    ):
        self.message = message
        self.code = code
        self.retry_delay = retry_delay
        self.retry_times = retry_times
        self.resource = resource
        self.is_retryable = is_retryable
        self.documentation_url = documentation_url
        self.api_response = api_response
        self.http_status_code = http_status_code

        super().__init__(self.message, str(self.code))

    def __str__(self):
        message = self.message

        if self.documentation_url is not None:
            message += '. Learn more: %s' % self.documentation_url

        return message


class EncoderError(BaseException):

    def __init__(self, content:str):
        self.content = content
        super().__init__()

    def __str__(self) -> str:
        return self.content

    def __repr__(self):
        return "Invalid payload: %s" % self.content


class ExtraUsageForbidden(ScrapflyError):
    pass


class HttpError(ScrapflyError):

    def __init__(self, request:Request, response:Optional[Response]=None, **kwargs):
        self.request = request
        self.response = response
        super().__init__(**kwargs)

    def __str__(self) -> str:
        if isinstance(self, UpstreamHttpError):
            return f"Target website responded with {self.api_response.scrape_result['status_code']} - {self.api_response.scrape_result['reason']}"

        if self.api_response is not None:
            return self.api_response.error_message

        text = f"{self.response.status_code} - {self.response.reason}"

        # Include detailed error message for all HTTP errors
        if self.message:
            text += f" - {self.message}"

        return text


class UpstreamHttpError(HttpError):
    pass


class UpstreamHttpClientError(UpstreamHttpError):
    pass


class UpstreamHttpServerError(UpstreamHttpClientError):
    pass

class ApiHttpClientError(HttpError):
    pass


class BadApiKeyError(ApiHttpClientError):
    pass


class PaymentRequired(ApiHttpClientError):
    pass


class TooManyRequest(ApiHttpClientError):
    pass


class ApiHttpServerError(ApiHttpClientError):
    pass


class ScraperAPIError(HttpError):
    pass


class ScrapflyScrapeError(ScraperAPIError):
    pass


class ScrapflyProxyError(ScraperAPIError):
    pass


class ScrapflyThrottleError(ScraperAPIError):
    pass


class ScrapflyAspError(ScraperAPIError):
    pass


# The customer-facing name of the feature is now "Unblocker"; the error class
# keeps its `Asp` name because the API status it carries is still `ERR::ASP::*`.
# This alias is the SAME class object, not a subclass, so `except
# ScrapflyAspError` keeps catching everything it caught before and the two names
# are interchangeable in `except`, `isinstance` and `issubclass`. Matches the Go
# SDK's `ErrUnblockerBypassFailed` and the TypeScript SDK's
# `ScrapflyUnblockerError`, which are aliases of their Asp-named originals too.
ScrapflyUnblockerError = ScrapflyAspError


class ScrapflyScheduleError(ScraperAPIError):
    pass


class ScrapflyWebhookError(ScraperAPIError):
    pass


class ScrapflySessionError(ScraperAPIError):
    pass


class TooManyConcurrentRequest(HttpError):
    pass


class QuotaLimitReached(HttpError):
    pass


class ScreenshotAPIError(HttpError):
    pass


class ExtractionAPIError(HttpError):
    pass


class CrawlerError(ScrapflyError):
    """Base exception for Crawler API errors"""
    pass


class ScrapflyCrawlerError(CrawlerError):
    """Exception raised when a crawler job fails or is cancelled"""
    pass


class CrawlerSearchError(CrawlerError):
    """
    Exception raised when ``POST /crawl/search`` cannot answer.

    Carries the API code, e.g. ``ERR::CRAWLER::SEARCH_NOT_ENABLED``,
    ``ERR::CRAWLER::SEARCH_NOT_READY``, ``ERR::CRAWLER::SEARCH_TOO_MANY_CRAWLS``.
    A crawl that is merely skipped is *not* an error: it is reported in
    ``CrawlerSearchResponse.skipped`` and the search still answers.
    """
    pass


class CrawlerPromptError(CrawlerError):
    """
    Exception raised when ``POST /crawl/prompt`` fails.

    Also raised mid-stream when the server sends an ``event: error`` frame:
    generation can fail after tokens have already been delivered, so a caller
    consuming the iterator must be ready for this on any ``next()``.
    """
    pass


class CrawlerRefreshError(CrawlerError):
    """
    Exception raised when a crawl refresh call fails.

    Carries the API code, e.g. ``ERR::CRAWLER::REFRESH_NOT_ENABLED``,
    ``ERR::CRAWLER::REFRESH_IN_PROGRESS``,
    ``ERR::CRAWLER::REFRESH_INTERVAL_INVALID``.
    """
    pass


class ErrorFactory:
    RESOURCE_TO_ERROR = {
        ScrapflyError.RESOURCE_SCRAPE: ScrapflyScrapeError,
        ScrapflyError.RESOURCE_WEBHOOK: ScrapflyWebhookError,
        ScrapflyError.RESOURCE_PROXY: ScrapflyProxyError,
        ScrapflyError.RESOURCE_SCHEDULE: ScrapflyScheduleError,
        ScrapflyError.RESOURCE_ASP: ScrapflyAspError,
        ScrapflyError.RESOURCE_SESSION: ScrapflySessionError
    }

    # Notable http error has own class for more convenience
    # Only applicable for generic API error
    HTTP_STATUS_TO_ERROR = {
        401: BadApiKeyError,
        402: PaymentRequired,
        429: TooManyRequest
    }

    @staticmethod
    def _get_resource(code: str) -> Optional[str]:
        # Codes are ERR::<RESOURCE>::<REASON>, but the segment count is the
        # API's to change, so index rather than unpack.
        if isinstance(code, str) and '::' in code:
            return code.split('::')[1]

        return None

    @staticmethod
    def create(api_response: 'ScrapeApiResponse'):
        is_retryable = False
        kind = ScrapflyError.KIND_HTTP_BAD_RESPONSE if api_response.success is False else ScrapflyError.KIND_SCRAPFLY_ERROR
        http_code = api_response.status_code
        retry_delay = 5
        retry_times = 3
        description = None
        error_url = 'https://scrapfly.io/docs/scrape-api/errors#api'
        code = api_response.error['code']

        if code == 'ERR::SCRAPE::BAD_UPSTREAM_RESPONSE':
            http_code = api_response.scrape_result['status_code']

        if 'description' in api_response.error:
            description = api_response.error['description']

        message = '%s %s %s' % (str(http_code), code, api_response.error['message'])

        if 'doc_url' in api_response.error:
            error_url = api_response.error['doc_url']

        if 'retryable' in api_response.error:
            is_retryable = api_response.error['retryable']

        resource = ErrorFactory._get_resource(code=code)

        if is_retryable is True:
            if 'X-Retry' in api_response.headers:
                retry_delay = int(api_response.headers['Retry-After'])

        message = '%s: %s' % (message, description) if description else message

        if retry_delay is not None and is_retryable is True:
            message = '%s. Retry delay : %s seconds' % (message, str(retry_delay))

        args = {
            'message': message,
            'code': code,
            'http_status_code': http_code,
            'is_retryable': is_retryable,
            'api_response': api_response,
            'resource': resource,
            'retry_delay': retry_delay,
            'retry_times': retry_times,
            'documentation_url': error_url,
            'request': api_response.request,
            'response': api_response.response
        }

        if kind == ScrapflyError.KIND_HTTP_BAD_RESPONSE:
            if http_code >= 500:
                return ApiHttpServerError(**args)

            is_scraper_api_error = resource in ErrorFactory.RESOURCE_TO_ERROR

            if http_code in ErrorFactory.HTTP_STATUS_TO_ERROR and not is_scraper_api_error:
                return ErrorFactory.HTTP_STATUS_TO_ERROR[http_code](**args)

            if is_scraper_api_error:
                return ErrorFactory.RESOURCE_TO_ERROR[resource](**args)

            return ApiHttpClientError(**args)

        elif kind == ScrapflyError.KIND_SCRAPFLY_ERROR:
            if code == 'ERR::SCRAPE::BAD_UPSTREAM_RESPONSE':
                if http_code >= 500:
                    return UpstreamHttpServerError(**args)

                if http_code >= 400:
                    return UpstreamHttpClientError(**args)

            if resource in ErrorFactory.RESOURCE_TO_ERROR:
                return ErrorFactory.RESOURCE_TO_ERROR[resource](**args)

            return ScrapflyError(**args)


def _documentation_url(envelope: Dict) -> Optional[str]:
    doc_url = envelope.get('doc_url')

    if isinstance(doc_url, str) and doc_url:
        return doc_url

    links = envelope.get('links')

    # `links` maps a human label to a URL while documentation_url holds a
    # single string, so only one survives: the error-specific entry, not the
    # generic "Getting Started" that ships alongside it.
    if isinstance(links, dict):
        for label, value in links.items():
            if isinstance(value, str) and value and 'error' in str(label).lower():
                return value

        return next((value for value in links.values() if isinstance(value, str) and value), None)

    if isinstance(links, list):
        return next((value for value in links if isinstance(value, str) and value), None)

    return None


def api_error_args(envelope: Optional[Dict], http_status_code: int) -> Dict:
    """Map an API-level error envelope onto ScrapflyError constructor kwargs.

    Every field is optional on the wire - a 401 envelope carries neither `code`
    nor `links` - so nothing here may index into it. Kept in one place because
    both the single-request path (ApiResponse.raise_for_result) and the batch
    part path decode the same envelope.
    """

    if not isinstance(envelope, dict):
        envelope = {}

    code = envelope.get('code')

    if not isinstance(code, str):
        code = ''

    message = envelope.get('message') or envelope.get('reason') or 'API error'

    if not isinstance(message, str):
        message = str(message)

    status_code = envelope.get('http_code')

    if not isinstance(status_code, int) or isinstance(status_code, bool):
        status_code = http_status_code

    return {
        'message': message,
        'code': code,
        'resource': ErrorFactory._get_resource(code=code),
        'http_status_code': status_code,
        'is_retryable': envelope.get('retryable') is True,
        'documentation_url': _documentation_url(envelope),
    }


__all__:Tuple[str, ...] = [
    'EncoderError',
    'ScrapflyError',
    'ScrapflyAspError',
    'ScrapflyUnblockerError',
    'ScrapflyProxyError',
    'ScrapflyScheduleError',
    'ScrapflyScrapeError',
    'ScrapflySessionError',
    'ScrapflyThrottleError',
    'ScrapflyWebhookError',
    'UpstreamHttpClientError',
    'UpstreamHttpServerError',
    'ApiHttpClientError',
    'ApiHttpServerError',
    'CrawlerError',
    'ScrapflyCrawlerError',
    'CrawlerSearchError',
    'CrawlerPromptError',
    'CrawlerRefreshError',
]
