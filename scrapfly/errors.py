from typing import Optional, Tuple
from requests import Request, Response


class ScrapflyError(BaseException):
    KIND_HTTP_BAD_RESPONSE = 'HTTP_BAD_RESPONSE'
    KIND_SCRAPFLY_ERROR = 'SCRAPFLY_ERROR'

    RESOURCE_PROXY = 'PROXY'
    RESOURCE_THROTTLE = 'THROTTLE'
    RESOURCE_SCRAPE = 'SCRAPE'
    RESOURCE_ASP = 'ASP'
    RESOURCE_SCHEDULE = 'SCHEDULE'
    RESOURCE_WEBHOOK = 'WEBHOOK'
    RESOURCE_SESSION = 'SESSION'

    KNOWN_HTTP_API_ERROR_CODE = [
        400,
        401,
        404,
        422,
        429,
        500,
        503,
        504
    ]

    def __init__(
        self,
        message: str,
        code: int,
        resource: str,
        http_status_code: int,
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


class HttpError(ScrapflyError):

    def __init__(self, request:Request, response:Optional[Response]=None, **kwargs):
        self.request = request
        self.response = response
        super().__init__(**kwargs)


class UpstreamHttpClientError(HttpError):
    pass


class UpstreamHttpServerError(UpstreamHttpClientError):
    pass


class ApiHttpClientError(HttpError):
    pass


class BadApiKeyError(ApiHttpClientError):
    pass


class TooManyRequest(ApiHttpClientError):
    pass


class ApiHttpServerError(ApiHttpClientError):
    pass


class ScrapflyScrapeError(ScrapflyError):
    pass


class ScrapflyProxyError(ScrapflyError):
    pass


class ScrapflyThrottleError(ScrapflyError):
    pass


class ScrapflyAspError(ScrapflyError):
    pass


class ScrapflyScheduleError(ScrapflyError):
    pass


class ScrapflyWebhookError(ScrapflyError):
    pass


class ScrapflySessionError(ScrapflyError):
    pass


class TooManyConcurrentRequest(ScrapflyScrapeError):
    pass


class QuotaLimitReached(ScrapflyScrapeError):
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
    HTTP_STATUS_TO_ERROR = {
        401: BadApiKeyError,
        429: TooManyRequest
    }

    @staticmethod
    def _get_resource(code: str) -> Optional[Tuple[str, str]]:

        if isinstance(code, str) and '::' in code:
            _, resource, _ = code.split('::')
            return resource

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
            http_code = api_response.error['http_code']

        if 'description' in api_response.error:
            description = api_response.error['description']

        message = str(http_code) + ' ' + api_response.error['message']

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
            if 400 <= http_code < 500:
                if http_code in ErrorFactory.HTTP_STATUS_TO_ERROR:
                    return ErrorFactory.HTTP_STATUS_TO_ERROR[http_code](**args)
                return ApiHttpClientError(**args)

            return ApiHttpServerError(**args)
        elif kind == ScrapflyError.KIND_SCRAPFLY_ERROR:
            if code == 'ERR::SCRAPE::BAD_UPSTREAM_RESPONSE':
                if 400 <= http_code < 500:
                    return UpstreamHttpClientError(**args)

                return UpstreamHttpClientError(**args)

            if resource in ErrorFactory.RESOURCE_TO_ERROR:
                return ErrorFactory.RESOURCE_TO_ERROR[resource](**args)

            return ScrapflyError(**args)


__all__:Tuple[str, ...] = [
    'ScrapflyError',
    'ScrapflyAspError',
    'ScrapflyProxyError',
    'ScrapflyScheduleError',
    'ScrapflyScrapeError',
    'ScrapflySessionError',
    'ScrapflyThrottleError',
    'ScrapflyWebhookError',
    'UpstreamHttpClientError',
    'UpstreamHttpServerError',
    'ApiHttpClientError',
    'ApiHttpServerError'
]
