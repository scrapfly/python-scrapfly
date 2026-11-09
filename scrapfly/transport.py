"""
API calls written once, run by ScrapflyClient (requests) and AsyncScrapflyClient (httpx).

An operation is a generator: it yields a Call or a Sleep and is sent back the
requests.Response (None after a Sleep), so building the request and reading the
response are shared, and only the clients' run loops do I/O.
"""
import functools
import inspect
import random
import re
from dataclasses import dataclass
from typing import (
    TYPE_CHECKING, Any, AsyncIterator, Awaitable, Callable, Concatenate, Generator, Generic, Iterable, Iterator,
    Optional, ParamSpec, Protocol, TypeVar, Union, get_args, get_origin, overload,
)

from requests import RequestException, Response

if TYPE_CHECKING:
    from .async_client import AsyncScrapflyClient
    from .client import ScrapflyClient

T = TypeVar('T')
R = TypeVar('R')
P = ParamSpec('P')


class Call:
    """One HTTP exchange, as the keyword arguments of requests.request."""

    def __init__(self, method: str, url: str, *, tries: int = 1, retry_read_timeout: bool = True, **options: Any):
        self.method = method
        self.url = url
        # A retry on a network error sends the request again: only for calls safe to repeat.
        self.tries = tries
        # False: a read timeout is raised at once, the other network errors are retried.
        self.retry_read_timeout = retry_read_timeout
        self.options = options

    @property
    def stream(self) -> bool:
        return bool(self.options.get('stream'))


@dataclass
class Sleep:
    seconds: float


type Steps[R] = Generator[Call | Sleep, Any, R]


class StreamDecoder(Protocol[T]):
    """Push decoder of a streamed body: done once it read what it needed."""

    done: bool

    def feed(self, chunk: bytes) -> Iterable[T]: ...

    def close(self) -> Iterable[T]: ...


@dataclass
class Streamed(Generic[T]):
    """A response read as it arrives, each decoded item finished by an operation of its own."""

    response: Response
    decoder: StreamDecoder
    chunk_size: Optional[int] = None
    finish: Optional[Callable[[Any], Steps[T]]] = None


def signed(method: Callable, steps: Callable, stream: type) -> Callable:
    """Give the client method that runs `steps` its signature: Steps[R] returns R, a Streamed[T] in R reads as stream[T]."""
    signature = inspect.signature(steps)

    if get_args(signature.return_annotation):
        signature = signature.replace(return_annotation=_streams(get_args(signature.return_annotation)[0], stream))
        method.__annotations__ = {**steps.__annotations__, 'return': signature.return_annotation}

    method.__signature__ = signature

    return method


def _streams(annotation, stream: type):
    if get_origin(annotation) is Streamed:
        return stream[get_args(annotation)[0]]

    if get_origin(annotation) is Union:
        return Union[tuple(_streams(arg, stream) for arg in get_args(annotation))]

    return annotation


KEY_IN_URL = re.compile(r'(?<=[?&]key=)[^&\s\'")]+')


def without_key(error: BaseException) -> BaseException:
    """The error with the API key masked, or the error itself when it does not print one.

    requests puts the request URL in a connection error message, query and key included.
    """
    message = str(error)
    if not KEY_IN_URL.search(message):
        return error

    masked = KEY_IN_URL.sub('REDACTED', message)
    if isinstance(error, RequestException):
        return type(error)(masked, request=error.request, response=error.response)

    return type(error)(masked)


def retry_delay(attempt: int) -> float:
    """Exponential backoff with full jitter, attempt 0 first."""
    return random.uniform(0, 2 ** attempt)


def ready(value: T) -> Steps[T]:
    """An operation that needs no call."""
    return value
    yield


class operation(Generic[P, R]):
    """
    A method written once as Steps: a plain method of ScrapflyClient, a coroutine of AsyncScrapflyClient.

    ScrapflyApi.__init_subclass__ replaces it by the client's method; __get__ only types that method.
    """

    def __init__(self, steps: Callable[Concatenate[Any, P], Steps[R]]):
        self.steps = steps
        functools.update_wrapper(self, steps)

    @overload
    def __get__(self, client: None, owner: type) -> 'operation[P, R]': ...

    @overload
    def __get__(self, client: 'AsyncScrapflyClient', owner: type) -> Callable[P, Awaitable[R]]: ...

    @overload
    def __get__(self, client: 'ScrapflyClient', owner: type) -> Callable[P, R]: ...

    def __get__(self, client: Any, owner: type) -> Any:
        return self


class streaming(Generic[P, T]):
    """An operation whose result arrives as a stream: an iterator of ScrapflyClient, an async iterator of AsyncScrapflyClient."""

    def __init__(self, steps: Callable[Concatenate[Any, P], Steps[Streamed[T]]]):
        self.steps = steps
        functools.update_wrapper(self, steps)

    @overload
    def __get__(self, client: None, owner: type) -> 'streaming[P, T]': ...

    @overload
    def __get__(self, client: 'AsyncScrapflyClient', owner: type) -> Callable[P, AsyncIterator[T]]: ...

    @overload
    def __get__(self, client: 'ScrapflyClient', owner: type) -> Callable[P, Iterator[T]]: ...

    def __get__(self, client: Any, owner: type) -> Any:
        return self
