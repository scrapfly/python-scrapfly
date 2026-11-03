"""AsyncScrapflyClient: the Scrapfly API over httpx."""
import asyncio
from functools import wraps
from typing import AsyncIterator, List, Optional, Union

import httpx
import requests
from requests.structures import CaseInsensitiveDict
from requests.utils import get_encoding_from_headers

from .api import ScrapflyApi
from .api_response import ScrapeApiResponse
from .scrape_config import ScrapeConfig
from .transport import Call, Sleep, Steps, Streamed, retry_delay, signed, without_key


class AsyncScrapflyClient(ScrapflyApi):
    """
    The Scrapfly API over httpx. Every operation of ScrapflyApi is a coroutine
    here, and a streamed one an async iterator. Responses are requests.Response
    objects, as with ScrapflyClient.

    Each call opens its own connection unless the client is opened, with
    ``async with AsyncScrapflyClient(...) as client`` or ``await client.open()``.
    """

    def _init_transport(self):
        self._http: Optional[httpx.AsyncClient] = None

    def _new_http(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(verify=self.verify)

    async def open(self):
        if self._http is None:
            self._http = self._new_http()

    async def close(self):
        if self._http is not None:
            await self._http.aclose()
            self._http = None

    async def __aenter__(self) -> 'AsyncScrapflyClient':
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    @staticmethod
    def _method(steps):
        @wraps(steps)
        async def method(self, *args, **kwargs):
            result = await self._run(steps(self, *args, **kwargs))

            return self._read_stream(result) if isinstance(result, Streamed) else result

        return signed(method, steps, AsyncIterator)

    @staticmethod
    def _stream_method(steps):
        @wraps(steps)
        async def method(self, *args, **kwargs):
            async for item in self._read_stream(await self._run(steps(self, *args, **kwargs))):
                yield item

        return signed(method, steps, AsyncIterator)

    async def _run(self, steps: Steps):
        send, value = steps.send, None

        while True:
            try:
                step = send(value)
            except StopIteration as done:
                return done.value
            except requests.RequestException as error:
                # raise_for_status() prints the request URL, key included.
                masked = without_key(error)
                if masked is error:
                    raise

                raise masked from None

            # Raised inside the operation, at the yield, so its own handlers see it.
            try:
                value, send = await self._perform(step), steps.send
            except BaseException as error:
                value, send = error, steps.throw

    async def _perform(self, step: Call | Sleep) -> Optional[requests.Response]:
        if isinstance(step, Sleep):
            await asyncio.sleep(step.seconds)

            return None

        for attempt in range(step.tries):
            try:
                return await self._send(step)
            except httpx.TransportError:
                if attempt + 1 == step.tries:
                    raise

                await asyncio.sleep(retry_delay(attempt))

    async def _send(self, call: Call) -> requests.Response:
        options = call.options
        # requests encodes the query, the body and the multipart exactly as ScrapflyClient sends them.
        # Session.request drops a header set to None, prepare() alone rejects it.
        prepared = requests.Request(
            method=call.method,
            url=call.url,
            params=options.get('params'),
            headers={name: value for name, value in (options.get('headers') or {}).items() if value is not None},
            data=options.get('data'),
            json=options.get('json'),
            files=options.get('files'),
        ).prepare()
        # httpx then asks for the encodings it can decode.
        prepared.headers.pop('Accept-Encoding', None)

        http = self._http or self._new_http()
        owned = None if http is self._http else http

        try:
            raw = await http.send(
                http.build_request(prepared.method, prepared.url, headers=prepared.headers, content=prepared.body, timeout=_timeout(options.get('timeout'))),
                stream=True,
            )
        except BaseException:
            if owned is not None:
                await owned.aclose()
            raise

        response = requests.Response()
        response.status_code = raw.status_code
        response.reason = raw.reason_phrase
        response.headers = CaseInsensitiveDict(raw.headers.items())
        response.url = str(raw.url)
        response.encoding = get_encoding_from_headers(response.headers)
        response.request = prepared

        # An error body is read whole: the operation reads it as it would a plain response.
        if call.stream and raw.is_success:
            response.raw = _Body(raw, owned)

            return response

        try:
            response._content = await raw.aread()
            response._content_consumed = True
        finally:
            await _Body(raw, owned).aclose()

        return response

    async def _read_stream(self, streamed: Streamed) -> AsyncIterator:
        body: _Body = streamed.response.raw

        try:
            async for chunk in body.raw.aiter_bytes():
                for item in streamed.decoder.feed(chunk):
                    yield item if streamed.finish is None else await self._run(streamed.finish(item))

                if streamed.decoder.done:
                    return

            for item in streamed.decoder.close():
                yield item if streamed.finish is None else await self._run(streamed.finish(item))
        finally:
            await body.aclose()

    async def concurrent_scrape(
        self,
        scrape_configs: List[ScrapeConfig],
        concurrency: Optional[int] = None,
    ) -> AsyncIterator[Union[ScrapeApiResponse, Exception]]:
        """Scrape every config, `concurrency` at a time, and yield each result or error as it completes."""
        if concurrency is None:
            concurrency = self.max_concurrency
        elif concurrency == self.CONCURRENCY_AUTO:
            concurrency = (await self.account())['subscription']['max_concurrency']

        slots = asyncio.Semaphore(concurrency)

        async def scrape(scrape_config: ScrapeConfig):
            scrape_config.raise_on_upstream_error = False

            async with slots:
                try:
                    return await self.scrape(scrape_config)
                except Exception as error:
                    return error

        tasks = [asyncio.ensure_future(scrape(scrape_config)) for scrape_config in scrape_configs]

        try:
            for done in asyncio.as_completed(tasks):
                yield await done
        finally:
            for task in tasks:
                task.cancel()


class _Body:
    """A streamed httpx response, and the client opened for it alone."""

    def __init__(self, raw: httpx.Response, owned: Optional[httpx.AsyncClient]):
        self.raw = raw
        self.owned = owned

    async def aclose(self):
        await self.raw.aclose()

        if self.owned is not None:
            await self.owned.aclose()


def _timeout(timeout) -> httpx.Timeout:
    """requests' timeout, None (no limit), seconds or (connect, read), as an httpx.Timeout."""
    if isinstance(timeout, tuple):
        connect, read = timeout

        return httpx.Timeout(read, connect=connect)

    return httpx.Timeout(timeout)
