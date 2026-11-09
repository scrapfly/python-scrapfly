"""ScrapflyClient and AsyncScrapflyClient run the same operations: every scenario runs on both, against one fake API."""
import asyncio
import gzip
import inspect
import json
import traceback
from io import BytesIO
from dataclasses import dataclass
from typing import Callable, Dict, List, Tuple
from urllib.parse import parse_qs, urlsplit

import httpx
import pytest
import requests
import urllib3

from scrapfly import AsyncScrapflyClient, ExtractionConfig, ScrapeApiResponse, ScrapeConfig, ScreenshotConfig, ScrapflyClient
from scrapfly import api_response, async_client, client
from scrapfly.api_response import ApiResponse
from scrapfly.errors import ApiHttpClientError, ApiHttpServerError, CrawlerPromptError, ExtractionAPIError, ScrapflyError, ScreenshotAPIError

pytestmark = pytest.mark.unit

KEY = 'scp-test-00000000000000000000000000000000'
HOST = 'https://api.scrapfly.test'
CLIENTS = ('sync', 'async')

# The fake API drops the connection when it answers this.
DROP = object()
# The fake API takes the request and never answers when it answers this.
READ_TIMEOUT = object()
# The fake API sends the headers and stops in the body when it answers this.
BODY_READ_TIMEOUT = object()


@dataclass
class Seen:
    method: str
    path: str
    query: Dict[str, List[str]]
    body: bytes
    headers: Dict[str, str]


Reply = Tuple[int, Dict[str, str], List[bytes]]


def json_reply(payload, status: int = 200) -> Reply:
    return status, {'content-type': 'application/json'}, [json.dumps(payload).encode()]


def envelope(content, format: str = 'text') -> dict:
    return {
        'config': {'url': 'https://web-scraping.dev/product/1', 'headers': {}},
        'context': {},
        'result': {
            'status': 'DONE', 'success': True, 'status_code': 200, 'reason': 'OK', 'error': None,
            'content': content, 'format': format, 'request_headers': {}, 'response_headers': {'content-type': 'text/html'},
            'duration': 0.1, 'log_url': 'https://scrapfly.io/dashboard/monitoring/log/01',
        },
    }


class _Chunks:
    """A raw body requests reads chunk by chunk, as the wire delivers it."""

    def __init__(self, chunks: List[bytes]):
        self._chunks = list(chunks)

    def read(self, size=None):
        return self._chunks.pop(0) if self._chunks else b''

    def close(self):
        self._chunks.clear()


def _seen(method: str, url: str, body, headers) -> Seen:
    split = urlsplit(url)
    body = body.encode() if isinstance(body, str) else (body or b'')

    return Seen(method, split.path, parse_qs(split.query), body, {k.lower(): v for k, v in headers.items()})


def run(kind: str, server: Callable[[Seen], object], scenario, monkeypatch=None):
    """Run `scenario(client)` on a ScrapflyClient or an AsyncScrapflyClient wired to `server`; returns (result, requests seen)."""
    seen: List[Seen] = []

    if monkeypatch is not None:
        monkeypatch.setattr(client, 'retry_delay', lambda attempt: 0)
        monkeypatch.setattr(async_client, 'retry_delay', lambda attempt: 0)

    if kind == 'sync':
        scrapfly = ScrapflyClient(key=KEY, host=HOST)

        def handler(method, url, params=None, headers=None, data=None, json=None, files=None, **options):
            # The session's merge is what requests.request applies before sending.
            prepared = requests.Session().prepare_request(requests.Request(method=method, url=url, params=params, headers=headers, data=data, json=json, files=files))
            seen.append(_seen(prepared.method, prepared.url, prepared.body, prepared.headers))
            reply = server(seen[-1])

            if reply is DROP:
                raise requests.ConnectionError('dropped')

            if reply is READ_TIMEOUT:
                raise requests.ReadTimeout('timed out')

            if reply is BODY_READ_TIMEOUT:
                raise requests.ConnectionError(urllib3.exceptions.ReadTimeoutError(None, None, 'Read timed out.'))

            status, reply_headers, chunks = reply
            response = requests.Response()
            response.status_code = status
            response.headers.update(reply_headers)
            response.raw = _Chunks(chunks)
            response.url = prepared.url
            response.request = prepared

            return response

        scrapfly.__dict__['_http_handler'] = handler

        return asyncio.run(scenario(scrapfly)), seen

    async def handler(request: httpx.Request):
        seen.append(_seen(request.method, str(request.url), await request.aread(), request.headers))
        reply = server(seen[-1])

        if reply is DROP:
            raise httpx.ConnectError('dropped', request=request)

        if reply is READ_TIMEOUT or reply is BODY_READ_TIMEOUT:
            raise httpx.ReadTimeout('timed out', request=request)

        status, reply_headers, chunks = reply

        async def body():
            for chunk in chunks:
                yield chunk

        return httpx.Response(status, headers=reply_headers, content=body())

    class Client(AsyncScrapflyClient):
        def _new_http(self):
            return httpx.AsyncClient(transport=httpx.MockTransport(handler))

    async def main():
        async with Client(key=KEY, host=HOST) as scrapfly:
            return await scenario(scrapfly)

    return asyncio.run(main()), seen


async def resolve(value):
    return await value if inspect.isawaitable(value) else value


async def collect(stream) -> list:
    if hasattr(stream, '__aiter__'):
        return [item async for item in stream]

    return list(stream)


@pytest.mark.parametrize('kind', CLIENTS)
def test_scrape_reads_the_envelope(kind):
    def server(seen: Seen):
        return json_reply(envelope('<html>product</html>'))

    async def scenario(scrapfly):
        return await resolve(scrapfly.scrape(ScrapeConfig(url='https://web-scraping.dev/product/1', render_js=True)))

    response, seen = run(kind, server, scenario)

    assert isinstance(response, ScrapeApiResponse)
    assert response.content == '<html>product</html>'
    assert (seen[0].method, seen[0].path) == ('GET', '/scrape')
    assert seen[0].query['url'] == ['https://web-scraping.dev/product/1']
    assert seen[0].query['render_js'] == ['true']
    assert seen[0].query['key'] == [KEY]


def test_both_clients_send_the_same_request():
    def server(seen: Seen):
        return json_reply(envelope('ok'))

    async def scenario(scrapfly):
        return await resolve(scrapfly.scrape(ScrapeConfig(url='https://web-scraping.dev/', method='POST', data={'q': 'é'}, asp=True, country='fr')))

    _, sync_seen = run('sync', server, scenario)
    _, async_seen = run('async', server, scenario)

    assert [(s.method, s.path, s.query, s.body) for s in sync_seen] == [(s.method, s.path, s.query, s.body) for s in async_seen]
    assert sync_seen[0].headers['content-type'] == async_seen[0].headers['content-type']


def test_the_screenshot_read_timeout_outlasts_the_longest_timeout_the_api_accepts():
    scrapfly = ScrapflyClient(key=KEY, host=HOST)

    timeout = scrapfly._screenshot_request(ScreenshotConfig(url='https://web-scraping.dev/product/1', timeout=120000))['timeout']

    assert timeout[1] > 120


def test_the_extraction_read_timeout_outlasts_the_longest_timeout_the_api_accepts():
    scrapfly = ScrapflyClient(key=KEY, host=HOST)

    timeout = scrapfly._extraction_request(ExtractionConfig(body='<h1>x</h1>', content_type='text/html', timeout=155))['timeout']

    assert timeout[1] > 155


@pytest.mark.parametrize('kind', CLIENTS)
def test_the_extraction_prompt_reaches_the_extraction_api_unchanged(kind):
    prompt = 'Quel est le prix en € ? réponds, merci.'

    def server(seen: Seen):
        return json_reply({'data': 'prix', 'content_type': 'application/json'})

    async def scenario(scrapfly):
        config = ExtractionConfig(body='<h1>x</h1>', content_type='text/html', extraction_prompt=prompt)
        return await resolve(scrapfly.extract(config))

    _, seen = run(kind, server, scenario)

    assert seen[0].query['extraction_prompt'] == [prompt]


def test_the_extraction_prompt_of_a_scrape_is_handed_over_unchanged():
    prompt = 'Quel est le prix en € ? réponds, merci.'
    config = ScrapeConfig(url='https://web-scraping.dev/product/1', extraction_prompt=prompt)

    params = config.to_api_params(key=KEY)

    assert params['extraction_prompt'] == prompt


@pytest.mark.parametrize('kind', CLIENTS)
def test_extraction_without_compression_sends_no_content_encoding(kind):
    def server(seen: Seen):
        return json_reply({'data': {'name': 'Box of Chocolate Candy'}, 'content_type': 'application/json'})

    async def scenario(scrapfly):
        config = ExtractionConfig(body='<h1>Box of Chocolate Candy</h1>', content_type='text/html', extraction_prompt='product name')
        return await resolve(scrapfly.extract(config))

    response, seen = run(kind, server, scenario)

    assert response.data == {'name': 'Box of Chocolate Candy'}
    assert (seen[0].method, seen[0].path) == ('POST', '/extraction')
    assert seen[0].body == b'<h1>Box of Chocolate Candy</h1>'
    assert 'content-encoding' not in seen[0].headers


@pytest.mark.parametrize('kind', CLIENTS)
def test_large_content_is_fetched_before_the_response_is_built(kind):
    def server(seen: Seen):
        if seen.path == '/scrape':
            return json_reply(envelope(HOST + '/scrape/clob/01', format='clob'))

        assert seen.path == '/scrape/clob/01' and seen.query['key'] == [KEY]

        return 200, {'content-type': 'text/plain'}, [b'large ', b'text']

    async def scenario(scrapfly):
        return await resolve(scrapfly.scrape(ScrapeConfig(url='https://web-scraping.dev/')))

    response, seen = run(kind, server, scenario)

    assert response.scrape_result['content'] == 'large text'
    assert response.scrape_result['format'] == 'text'
    assert [s.path for s in seen] == ['/scrape', '/scrape/clob/01']


@pytest.mark.parametrize('kind', CLIENTS)
@pytest.mark.parametrize('format,content_type,body,expected', [
    ('clob', 'application/json', b'{"products": [{"id": 1}]}', '{"products": [{"id": 1}]}'),
    ('clob', 'text/html', b'<h1>large</h1>', '<h1>large</h1>'),
    ('blob', 'application/pdf', b'%PDF-\x00\xff', b'%PDF-\x00\xff'),
    ('blob', 'application/json', b'{"products": [{"id": 1}]}', b'{"products": [{"id": 1}]}'),
])
def test_large_object_is_returned_as_is(kind, format, content_type, body, expected):
    def server(seen: Seen):
        if seen.path == '/scrape':
            return json_reply(envelope(HOST + '/scrape/large/01', format=format))

        return 200, {'content-type': content_type}, [body]

    async def scenario(scrapfly):
        return await resolve(scrapfly.scrape(ScrapeConfig(url='https://web-scraping.dev/')))

    response, _ = run(kind, server, scenario)
    content = response.scrape_result['content']

    # The envelope around the large object is still the API result.
    assert response.config['url'] == 'https://web-scraping.dev/product/1'
    assert response.scrape_result['success'] is True

    if format == 'clob':
        assert isinstance(content, str) and content == expected
        assert response.scrape_result['format'] == 'text'
    else:
        assert isinstance(content, BytesIO) and content.read() == expected
        assert response.scrape_result['format'] == 'binary'


@pytest.mark.parametrize('kind', CLIENTS)
@pytest.mark.parametrize('status,headers,body,error', [
    (404, {'content-type': 'application/json'}, json.dumps({'reason': 'Not Found', 'message': 'Large Object 01 not found', 'error_id': '01', 'http_code': 404}).encode(), ApiHttpClientError),
    (500, {'content-type': 'application/json'}, json.dumps({'reason': 'Internal Server Error', 'message': 'Internal Error', 'error_id': '01', 'http_code': 500}).encode(), ApiHttpServerError),
    (502, {'content-type': 'text/html'}, b'<h1>Bad Gateway</h1>', requests.HTTPError),
])
@pytest.mark.parametrize('format', ['clob', 'blob'])
def test_a_large_object_error_is_raised_not_returned_as_the_page(kind, status, headers, body, error, format):
    def server(seen: Seen):
        if seen.path == '/scrape':
            return json_reply(envelope(HOST + '/scrape/large_object/01', format=format))

        return status, headers, [body]

    async def scenario(scrapfly):
        return await resolve(scrapfly.scrape(ScrapeConfig(url='https://web-scraping.dev/')))

    with pytest.raises(error) as raised:
        run(kind, server, scenario)

    # A traceback prints the chained causes too, as Sentry and logger.exception do.
    assert KEY not in ''.join(traceback.format_exception(raised.value))


@pytest.mark.parametrize('content_encoding,body,expected', [
    ('gz', gzip.compress(b'large text'), b'large text'),
    # The HTTP client inflated it and left the header: the body is returned as it is.
    ('brotli', b'large text', b'large text'),
    # A .gz file served gzip: urllib3 inflated one layer, the file is the content.
    ('gzip', gzip.compress(b'large text'), gzip.compress(b'large text')),
    ('', b'large text', b'large text'),
])
def test_an_api_response_undoes_only_the_encoding_left_in_place(content_encoding, body, expected):
    response = requests.Response()
    response.status_code = 200
    response.headers['content-encoding'] = content_encoding
    response._content = body

    assert ApiResponse(request=response.request, response=response).decompress() == expected


def test_an_api_response_past_the_decompression_limit_raises(monkeypatch):
    monkeypatch.setattr(api_response, 'MAX_DECOMPRESSED_SIZE', 16)
    response = requests.Response()
    response.status_code = 200
    response.headers['content-encoding'] = 'gz'
    response._content = gzip.compress(b'x' * 1024)

    with pytest.raises(api_response.WebhookBodyTooLarge):
        ApiResponse(request=response.request, response=response).decompress()


@pytest.mark.parametrize('kind', CLIENTS)
def test_compressed_json_large_object_stays_text(kind):
    # `gz` is gzip that urllib3 does not inflate. The SDK must, and must not parse the JSON.
    page = b'{"products": [{"id": 1}]}'

    def server(seen: Seen):
        if seen.path == '/scrape':
            return json_reply(envelope(HOST + '/scrape/clob/02', format='clob'))

        return 200, {'content-type': 'application/json', 'content-encoding': 'gz'}, [gzip.compress(page)]

    async def scenario(scrapfly):
        return await resolve(scrapfly.scrape(ScrapeConfig(url='https://web-scraping.dev/')))

    response, _ = run(kind, server, scenario)

    assert response.scrape_result['content'] == page.decode()
    assert response.scrape_result['format'] == 'text'
    assert response.config['url'] == 'https://web-scraping.dev/product/1'
    assert response.scrape_result['success'] is True


@pytest.mark.parametrize('kind', CLIENTS)
def test_a_json_scrape_envelope_is_still_parsed(kind):
    """Sharing decompression with large objects must not skip parsing a real API envelope."""
    def server(seen: Seen):
        return json_reply(envelope('{"products": [{"id": 1}]}'))

    async def scenario(scrapfly):
        return await resolve(scrapfly.scrape(ScrapeConfig(url='https://web-scraping.dev/products.json')))

    response, seen = run(kind, server, scenario)

    assert response.scrape_result['content'] == '{"products": [{"id": 1}]}'
    assert response.scrape_result['format'] == 'text'
    assert response.config['url'] == 'https://web-scraping.dev/product/1'
    assert len(seen) == 1


@pytest.mark.parametrize('kind', CLIENTS)
def test_a_dropped_connection_is_retried(kind, monkeypatch):
    drops = [DROP, DROP]

    async def scenario(scrapfly):
        return await resolve(scrapfly.scrape(ScrapeConfig(url='https://web-scraping.dev/')))

    response, seen = run(kind, lambda seen: drops.pop() if drops else json_reply(envelope('ok')), scenario, monkeypatch)

    assert response.content == 'ok'
    assert len(seen) == 3


CAPTURE_AND_EXTRACTION = [
    pytest.param(lambda scrapfly: scrapfly.screenshot(ScreenshotConfig(url='https://web-scraping.dev/')), id='screenshot'),
    pytest.param(lambda scrapfly: scrapfly.extract(ExtractionConfig(body='<h1>x</h1>', content_type='text/html', extraction_prompt='title')), id='extraction'),
]


@pytest.mark.parametrize('kind', CLIENTS)
@pytest.mark.parametrize('call', CAPTURE_AND_EXTRACTION)
@pytest.mark.parametrize('timeout', [READ_TIMEOUT, BODY_READ_TIMEOUT], ids=['waiting-for-the-headers', 'reading-the-body'])
def test_a_read_timeout_is_not_sent_again(kind, call, timeout, monkeypatch):
    requests_seen = []

    def server(seen: Seen):
        requests_seen.append(seen)

        return timeout

    async def scenario(scrapfly):
        return await resolve(call(scrapfly))

    with pytest.raises((requests.ReadTimeout, requests.ConnectionError, httpx.ReadTimeout)):
        run(kind, server, scenario, monkeypatch)

    assert len(requests_seen) == 1


@pytest.mark.parametrize('kind', CLIENTS)
@pytest.mark.parametrize('call', CAPTURE_AND_EXTRACTION)
def test_a_dropped_connection_is_sent_again(kind, call, monkeypatch):
    drops = [DROP, DROP]

    async def scenario(scrapfly):
        return await resolve(call(scrapfly))

    def server(seen: Seen):
        if drops:
            return drops.pop()

        return 200, {'content-type': 'image/jpeg'}, [b'image']

    _, seen = run(kind, server, scenario, monkeypatch)

    assert len(seen) == 3


@pytest.mark.parametrize('kind', CLIENTS)
def test_a_read_timeout_of_a_scrape_is_sent_again(kind, monkeypatch):
    requests_seen = []

    def server(seen: Seen):
        requests_seen.append(seen)

        return READ_TIMEOUT

    async def scenario(scrapfly):
        return await resolve(scrapfly.scrape(ScrapeConfig(url='https://web-scraping.dev/')))

    with pytest.raises((requests.ReadTimeout, httpx.ReadTimeout)):
        run(kind, server, scenario, monkeypatch)

    assert len(requests_seen) == 5


@pytest.mark.parametrize('kind', CLIENTS)
@pytest.mark.parametrize('call', CAPTURE_AND_EXTRACTION)
def test_an_error_answer_without_an_envelope_is_raised(kind, call):
    async def scenario(scrapfly):
        return await resolve(call(scrapfly))

    with pytest.raises(ApiHttpServerError) as raised:
        run(kind, lambda seen: (502, {'content-type': 'text/plain'}, [b'Bad Gateway']), scenario)

    assert raised.value.http_status_code == 502 and 'Bad Gateway' in str(raised.value)
    assert KEY not in ''.join(traceback.format_exception(raised.value))


@pytest.mark.parametrize('kind', CLIENTS)
@pytest.mark.parametrize('call,error', [
    pytest.param(CAPTURE_AND_EXTRACTION[0].values[0], ScreenshotAPIError, id='screenshot'),
    pytest.param(CAPTURE_AND_EXTRACTION[1].values[0], ExtractionAPIError, id='extraction'),
])
def test_a_client_error_answer_without_an_envelope_raises_the_error_of_its_api(kind, call, error):
    async def scenario(scrapfly):
        return await resolve(call(scrapfly))

    with pytest.raises(error) as raised:
        run(kind, lambda seen: (404, {'content-type': 'text/html'}, [b'<h1>Not Found</h1>']), scenario)

    assert raised.value.http_status_code == 404


@pytest.mark.parametrize('kind', CLIENTS)
def test_a_screenshot_error_answer_without_an_envelope_is_returned_under_no_raise(kind):
    async def scenario(scrapfly):
        return await resolve(scrapfly.screenshot(ScreenshotConfig(url='https://web-scraping.dev/'), no_raise=True))

    response, _ = run(kind, lambda seen: (502, {'content-type': 'text/plain'}, [b'Bad Gateway']), scenario)

    assert response.screenshot_success is False and response.image == ''
    assert response.error['http_code'] == 502


@pytest.mark.parametrize('kind', CLIENTS)
def test_an_extraction_error_returned_under_no_raise_carries_its_envelope(kind):
    envelope_of_error = {'reason': 'Unprocessable', 'message': 'nothing to extract', 'error_id': '01', 'http_code': 422, 'code': 'ERR::EXTRACTION::NO_CONTENT', 'retryable': False}

    async def scenario(scrapfly):
        config = ExtractionConfig(body='<h1>x</h1>', content_type='text/html', extraction_prompt='title')

        return await resolve(scrapfly.extract(config, no_raise=True))

    response, _ = run(kind, lambda seen: json_reply(envelope_of_error, status=422), scenario)

    assert response.error['code'] == 'ERR::EXTRACTION::NO_CONTENT'
    assert response.data is None and response.extraction_success is False


@pytest.mark.parametrize('kind', CLIENTS)
def test_an_error_envelope_with_upstream_errors_allowed_is_returned(kind):
    envelope_of_error = {'reason': 'Unprocessable', 'message': 'no capture', 'error_id': '01', 'http_code': 422, 'code': 'ERR::SCREENSHOT::UNABLE_TO_TAKE_SCREENSHOT', 'retryable': False}

    async def scenario(scrapfly):
        return await resolve(scrapfly.screenshot(ScreenshotConfig(url='https://web-scraping.dev/', raise_on_upstream_error=False)))

    response, _ = run(kind, lambda seen: json_reply(envelope_of_error, status=422), scenario)

    assert response.screenshot_success is False


@pytest.mark.parametrize('kind', CLIENTS)
def test_a_call_unsafe_to_repeat_is_sent_once(kind, monkeypatch):
    async def scenario(scrapfly):
        return await resolve(scrapfly.cancel_crawl('7c7a7c3e'))

    with pytest.raises((requests.ConnectionError, httpx.TransportError)):
        run(kind, lambda seen: DROP, scenario, monkeypatch)


SSE = (
    b'event: source\ndata: {"rank": 1}\n\n'
    b':keepalive\n\n'
    b'event: token\ndata: "Caf\xc3\xa9 "\n\n'
    b'event: token\ndata: "ouvert"\n\n'
    b'event: done\ndata: {"sources_used": [1]}\n\n'
)


@pytest.mark.parametrize('kind', CLIENTS)
@pytest.mark.parametrize('size', [len(SSE), 7, 1])
def test_prompt_events_arrive_whole_across_chunks(kind, size):
    """Chunks cut lines, frames and the UTF-8 of a token anywhere."""
    def server(seen: Seen):
        assert json.loads(seen.body)['generation'] == {'stream': True}

        return 200, {'content-type': 'text/event-stream'}, [SSE[at:at + size] for at in range(0, len(SSE), size)]

    async def scenario(scrapfly):
        return await collect(await resolve(scrapfly.crawl_prompt(['7c7a7c3e'], 'Is the café open?')))

    events, _ = run(kind, server, scenario)

    assert [event.event for event in events] == ['source', 'token', 'token', 'done']
    assert ''.join(event.data for event in events if event.is_token) == 'Café ouvert'


@pytest.mark.parametrize('kind', CLIENTS)
def test_prompt_error_frame_raises_after_the_events_before_it(kind):
    body = b'event: token\ndata: "half"\n\nevent: error\ndata: {"code": "ERR::CRAWLER::PROMPT_GENERATION_FAILED", "message": "quota"}\n\n'
    delivered = []

    async def scenario(scrapfly):
        stream = await resolve(scrapfly.crawl_prompt(['7c7a7c3e'], 'q'))

        if hasattr(stream, '__aiter__'):
            async for event in stream:
                delivered.append(event)
        else:
            for event in stream:
                delivered.append(event)

    with pytest.raises(CrawlerPromptError, match='quota'):
        run(kind, lambda seen: (200, {'content-type': 'text/event-stream'}, [body]), scenario)

    assert [event.data for event in delivered] == ['half']


def multipart(parts: List[Tuple[str, dict]], boundary: str = 'b0und') -> bytes:
    out = b''

    for correlation_id, payload in parts:
        body = json.dumps(payload).encode()
        out += (
            f'--{boundary}\r\ncontent-type: application/json\r\nx-scrapfly-correlation-id: {correlation_id}\r\n'
            f'content-length: {len(body)}\r\n\r\n'
        ).encode() + body + b'\r\n'

    return out + f'--{boundary}--\r\n'.encode()


@pytest.mark.parametrize('kind', CLIENTS)
@pytest.mark.parametrize('size', [4096, 13, 1])
def test_batch_parts_are_decoded_as_they_arrive(kind, size):
    wire = multipart([('two', envelope('second')), ('one', envelope('first'))])

    def server(seen: Seen):
        assert [config['correlation_id'] for config in json.loads(seen.body)['configs']] == ['one', 'two']

        return 200, {'content-type': 'multipart/mixed; boundary=b0und'}, [wire[at:at + size] for at in range(0, len(wire), size)]

    async def scenario(scrapfly):
        configs = [ScrapeConfig(url='https://web-scraping.dev/1', correlation_id='one'), ScrapeConfig(url='https://web-scraping.dev/2', correlation_id='two')]

        return await collect(scrapfly.scrape_batch(configs))

    results, seen = run(kind, server, scenario)

    assert [(correlation_id, result.content) for correlation_id, result in results] == [('two', 'second'), ('one', 'first')]
    assert seen[0].path == '/scrape/batch'


@pytest.mark.parametrize('kind', CLIENTS)
def test_batch_reads_the_enqueue_ack_of_a_webhook(kind):
    scrape = envelope('')
    scrape['result'].update({'status': 'QUEUED', 'success': None, 'status_code': None})
    wire = multipart([('hook', {'correlation_id': 'hook', 'webhook_name': 'my-webhook', 'job_uuid': '01', 'enqueued': True, 'result': scrape})])

    def server(seen: Seen):
        return 200, {'content-type': 'multipart/mixed; boundary=b0und'}, [wire]

    async def scenario(scrapfly):
        return await collect(scrapfly.scrape_batch([ScrapeConfig(url='https://web-scraping.dev/1', correlation_id='hook', webhook='my-webhook')]))

    results, _ = run(kind, server, scenario)

    assert results[0][0] == 'hook'
    assert results[0][1].scrape_result['status'] == 'QUEUED'


@pytest.mark.parametrize('kind', CLIENTS)
def test_batch_sends_each_configs_method_and_body(kind):
    wire = multipart([('post', envelope('posted')), ('get', envelope('got'))])

    async def scenario(scrapfly):
        configs = [
            ScrapeConfig(url='https://web-scraping.dev/api', method='POST', body='{"q": 1}', headers={'content-type': 'application/json'}, correlation_id='post'),
            ScrapeConfig(url='https://web-scraping.dev/page', correlation_id='get'),
        ]

        return await collect(scrapfly.scrape_batch(configs))

    _, seen = run(kind, lambda seen: (200, {'content-type': 'multipart/mixed; boundary=b0und'}, [wire]), scenario)

    post, get = json.loads(seen[0].body)['configs']
    assert (post['method'], post['body']) == ('POST', '{"q": 1}')
    assert get['method'] == 'GET'
    assert 'body' not in get


@pytest.mark.parametrize('kind', CLIENTS)
def test_batch_error_reads_a_msgpack_body(kind):
    """The batch asks for msgpack when it is installed, and the API answers its errors in it too."""
    msgpack = pytest.importorskip('msgpack')
    error = {'code': 'ERR::SCRAPE::BATCH_CONFIG', 'message': 'configs[1] has no url', 'http_code': 422, 'retryable': False}

    async def scenario(scrapfly):
        return await collect(scrapfly.scrape_batch([ScrapeConfig(url='https://web-scraping.dev/', correlation_id='one')]))

    with pytest.raises(ScrapflyError, match='configs\\[1\\] has no url'):
        run(kind, lambda seen: (422, {'content-type': 'application/msgpack'}, [msgpack.packb(error)]), scenario)


@pytest.mark.parametrize('kind', CLIENTS)
def test_batch_validation_sends_nothing(kind):
    async def scenario(scrapfly):
        return await collect(scrapfly.scrape_batch([ScrapeConfig(url='https://web-scraping.dev/')]))

    with pytest.raises(ScrapflyError, match='correlation_id'):
        run(kind, lambda seen: pytest.fail('nothing must be sent'), scenario)


@pytest.mark.parametrize('kind', CLIENTS)
def test_playback_is_polled_until_ready(kind):
    replies = iter([{'status': 'uploading', 'retry_after_ms': 1}, {'status': 'uploading', 'retry_after_ms': 1}, {'status': 'ready', 'video_url': 'v'}])

    async def scenario(scrapfly):
        return await resolve(scrapfly.cloud_browser_wait_for_playback('run-1', timeout=10))

    playback, seen = run(kind, lambda seen: json_reply(next(replies)), scenario)

    assert playback['status'] == 'ready'
    assert [s.path for s in seen] == ['/run/run-1/playback'] * 3


@pytest.mark.parametrize('kind', CLIENTS)
def test_extension_upload_is_sent_as_multipart(kind, tmp_path):
    extension = tmp_path / 'ext.zip'
    extension.write_bytes(b'PK\x03\x04zip')

    async def scenario(scrapfly):
        return await resolve(scrapfly.cloud_browser_extension_upload(str(extension)))

    result, seen = run(kind, lambda seen: json_reply({'extension': {'id': 'e1'}}), scenario)

    assert result == {'extension': {'id': 'e1'}}
    assert seen[0].headers['content-type'].startswith('multipart/form-data; boundary=')
    assert b'filename="ext.zip"' in seen[0].body and b'PK\x03\x04zip' in seen[0].body


def test_async_operations_are_coroutines_with_the_sync_docstring():
    scrapfly = AsyncScrapflyClient(key=KEY)

    assert inspect.iscoroutinefunction(scrapfly.scrape)
    assert inspect.isasyncgenfunction(scrapfly.scrape_batch)
    assert scrapfly.scrape.__doc__ == ScrapflyClient(key=KEY).scrape.__doc__
    assert not inspect.iscoroutinefunction(ScrapflyClient(key=KEY).scrape)


def test_async_concurrent_scrape_yields_results_and_errors(monkeypatch):
    def server(seen: Seen):
        return DROP if seen.query['url'] == ['https://web-scraping.dev/down'] else json_reply(envelope(seen.query['url'][0]))

    async def scenario(scrapfly):
        configs = [ScrapeConfig(url=f'https://web-scraping.dev/{path}') for path in ('a', 'down', 'b')]

        return [result async for result in scrapfly.concurrent_scrape(configs, concurrency=2)]

    results, _ = run('async', server, scenario, monkeypatch)

    assert sorted(result.content for result in results if isinstance(result, ScrapeApiResponse)) == ['https://web-scraping.dev/a', 'https://web-scraping.dev/b']
    assert [type(result) for result in results if not isinstance(result, ScrapeApiResponse)] == [httpx.ConnectError]


def test_async_client_opened_once_reuses_one_connection_pool():
    opened = []

    class Client(AsyncScrapflyClient):
        def _new_http(self):
            opened.append(1)

            return httpx.AsyncClient(transport=httpx.MockTransport(lambda request: httpx.Response(200, json=envelope('ok'))))

    async def main():
        async with Client(key=KEY, host=HOST) as scrapfly:
            for _ in range(3):
                await scrapfly.scrape(ScrapeConfig(url='https://web-scraping.dev/'))

        await Client(key=KEY, host=HOST).scrape(ScrapeConfig(url='https://web-scraping.dev/'))

    asyncio.run(main())

    assert len(opened) == 2


EXTRACT = {
    'prompt': 'Every plan with its monthly price',
    'data': {'plans': [{'name': 'Pro', 'monthly_price_usd': 30}]},
    'sources': [{'id': 1, 'crawler_uuid': '7c7a7c3e', 'url': 'https://web-scraping.dev/pricing', 'title': 'Pricing', 'score': 0.8}],
    'sources_used': [],
    'sources_dropped': 0,
    'truncated': False,
    'search': {'completeness': 'exact', 'crawls_requested': 2, 'crawls_searched': 1, 'crawls_pruned_exact': 0,
               'skipped': [{'crawler_uuid': '9f1b', 'reason': 'search_not_enabled'}]},
}

SCHEMA = {'type': 'object', 'properties': {'plans': {'type': 'array'}}, 'required': ['plans']}


@pytest.mark.parametrize('kind', CLIENTS)
def test_extract_sends_the_schema_and_reads_the_data(kind):
    async def scenario(scrapfly):
        return await resolve(scrapfly.crawl_extract(['7c7a7c3e', '9f1b'], 'Every plan with its monthly price', SCHEMA, search={'limit': 20}))

    result, seen = run(kind, lambda seen: json_reply(EXTRACT), scenario)

    assert (seen[0].method, seen[0].path) == ('POST', '/crawl/extract')
    assert json.loads(seen[0].body) == {'prompt': 'Every plan with its monthly price', 'crawl_ids': ['7c7a7c3e', '9f1b'], 'schema': SCHEMA, 'search': {'limit': 20}}
    assert result.data == {'plans': [{'name': 'Pro', 'monthly_price_usd': 30}]}
    assert [source.url for source in result.sources] == ['https://web-scraping.dev/pricing']
    assert result.is_exact
    assert (result.crawls_requested, result.crawls_searched, result.crawls_pruned_exact) == (2, 1, 0)
    assert [(skip.crawler_uuid, skip.reason) for skip in result.skipped] == [('9f1b', 'search_not_enabled')]


@pytest.mark.parametrize('kind', CLIENTS)
def test_extract_error_is_typed(kind):
    from scrapfly import CrawlerExtractError

    async def scenario(scrapfly):
        return await resolve(scrapfly.crawl_extract(['7c7a7c3e'], 'plans', SCHEMA))

    error = {'code': 'ERR::CRAWLER::CONFIG_ERROR', 'message': 'A non-empty schema must be given'}

    with pytest.raises(CrawlerExtractError, match='schema') as raised:
        run(kind, lambda seen: json_reply(error, status=400), scenario)

    assert raised.value.code == 'ERR::CRAWLER::CONFIG_ERROR'


@pytest.mark.parametrize('kind', CLIENTS)
def test_extract_engine_failure_keeps_its_message(kind):
    from scrapfly import CrawlerExtractError

    async def scenario(scrapfly):
        return await resolve(scrapfly.crawl_extract(['7c7a7c3e'], 'plans', SCHEMA))

    # The engine relays its own failures with the message under `error`.
    error = {'error': 'the model returned no text', 'code': 'ERR::CRAWLER::PROMPT_GENERATION_FAILED'}

    with pytest.raises(CrawlerExtractError, match='the model returned no text') as raised:
        run(kind, lambda seen: json_reply(error, status=500), scenario)

    assert raised.value.code == 'ERR::CRAWLER::PROMPT_GENERATION_FAILED'


@pytest.mark.parametrize('kind', CLIENTS)
@pytest.mark.parametrize('crawl_ids, prompt, schema', [
    ([], 'plans', SCHEMA), (['7c7a7c3e'], '', SCHEMA), (['7c7a7c3e'], 'plans', {}), (['7c7a7c3e'], 'plans', ['type']),
])
def test_extract_validation_sends_nothing(kind, crawl_ids, prompt, schema):
    async def scenario(scrapfly):
        return await resolve(scrapfly.crawl_extract(crawl_ids, prompt, schema))

    with pytest.raises(ValueError):
        run(kind, lambda seen: pytest.fail('nothing must be sent'), scenario)


@pytest.mark.parametrize('kind', CLIENTS)
def test_prompt_without_stream_returns_one_object(kind):
    answer = {'prompt': 'q', 'answer': 'It sells chocolate.', 'sources': [], 'sources_used': [], 'sources_dropped': 0,
              'truncated': False, 'search': {'completeness': 'exact', 'skipped': []}, 'api_credit': 5}

    async def scenario(scrapfly):
        return await resolve(scrapfly.crawl_prompt(['7c7a7c3e'], 'q', stream=False))

    result, seen = run(kind, lambda seen: json_reply(answer), scenario)

    assert json.loads(seen[0].body)['generation'] == {'stream': False}
    assert seen[0].headers['accept'] == 'application/json'
    assert result == answer


@pytest.mark.parametrize('kind', CLIENTS)
def test_a_connection_error_does_not_print_the_key(kind):
    import traceback

    key = 'scp-live-0123456789abcdef'

    async def main():
        if kind == 'sync':
            return ScrapflyClient(key=key, host='http://127.0.0.1:1').account()

        async with AsyncScrapflyClient(key=key, host='http://127.0.0.1:1') as scrapfly:
            return await scrapfly.account()

    with pytest.raises((requests.ConnectionError, httpx.ConnectError)) as raised:
        asyncio.run(main())

    assert '0123456789abcdef' not in ''.join(traceback.format_exception(raised.value))
    if kind == 'sync':
        assert 'key=REDACTED' in str(raised.value)


@pytest.mark.parametrize('kind', CLIENTS)
def test_an_http_error_does_not_print_the_key(kind):
    import traceback

    async def scenario(scrapfly):
        return await resolve(scrapfly.account())

    with pytest.raises(requests.HTTPError) as raised:
        run(kind, lambda seen: json_reply({'message': 'throttled'}, status=429), scenario)

    assert KEY not in ''.join(traceback.format_exception(raised.value))
    assert 'key=REDACTED' in str(raised.value)
