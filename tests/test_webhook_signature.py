import gzip
import hashlib
import hmac
import json
import os
import sys
import threading
import time
import types
import zlib

import pytest

from scrapfly import api_response
from scrapfly.api_response import ResponseBodyHandler, WebhookBodyTooLarge, decompress
from scrapfly.crawler.crawler_webhook import webhook_from_payload
from scrapfly.errors import WebhookSignatureMissMatch
from scrapfly.webhook import create_server

SECRET = 'probe-signing-secret'

# Hardcoded on purpose: reading the SDK's own enum would make this test agree
# with whatever drift it is meant to catch.
EMITTED_RESOURCE_TYPES = ('scrape', 'ping', 'crawl', 'extraction', 'screenshot')


def sign(body: bytes) -> str:
    return hmac.new(SECRET.encode('utf-8'), body, hashlib.sha256).hexdigest().upper()


def wire(data) -> bytes:
    """
    Byte-for-byte what Scrapfly puts on the wire for application/json:
    json.dumps() with its DEFAULT separators, then utf-8. Tests must never
    re-derive this with compact separators.
    """
    return json.dumps(data).encode('utf-8')


@pytest.fixture
def server():
    pytest.importorskip('flask')

    received = []
    app = create_server(signing_secrets=(SECRET,), callback=lambda data, kind, request: received.append(data))

    def post(body: bytes, resource_type: str = 'scrape', signature: str = 'auto', content_encoding: str = None,
             signature_header: str = 'X-Scrapfly-Webhook-Signature', on_wire: bytes = None):
        headers = {'X-Scrapfly-Webhook-Resource-Type': resource_type, 'Content-Type': 'application/json'}

        if signature == 'auto':
            headers[signature_header] = sign(body)
        elif signature is not None:
            headers[signature_header] = signature

        if content_encoding:
            headers['Content-Encoding'] = content_encoding

        before = len(received)
        response = app.test_client().post('/webhook', data=on_wire if on_wire is not None else body, headers=headers)

        return response.status_code, len(received) > before

    return post


def test_missing_signature_is_rejected(server):
    """A configured secret means every request must be signed: absence is forgery, not exemption."""
    assert server(wire({'result': {'content': 'forged'}}), signature=None) == (401, False)


def test_wrong_signature_is_rejected(server):
    assert server(wire({'result': {'content': 'forged'}}), signature='DEAD') == (401, False)


def test_valid_signature_is_accepted(server):
    assert server(wire({'result': {'content': 'legit'}})) == (200, True)


def test_lowercase_digest_is_accepted(server):
    """The digest is also sent as X-Scrapfly-Webhook-Signature-Lowercase."""
    body = wire({'result': {'content': 'legit'}})
    assert server(body, signature=sign(body).lower()) == (200, True)


def test_unsigned_ping_answers_the_probe_without_delivering(server):
    """A ping sent while a webhook is being created is unsigned: answer it, deliver nothing."""
    assert server(wire({'ping': 'OK'}), resource_type='ping', signature=None) == (200, False)


def test_ping_carve_out_cannot_smuggle_a_payload(server):
    """
    The resource type is as unauthenticated as the signature, so the carve-out must not
    become a labelled bypass: an unsigned body wearing 'ping' still reaches no callback.
    """
    assert server(wire({'result': {'content': 'forged'}}), resource_type='ping', signature=None) == (200, False)


def test_signed_ping_is_delivered(server):
    """A ping on an existing webhook is signed like any other resource type, so it verifies."""
    assert server(wire({'ping': 'OK'}), resource_type='ping') == (200, True)


@pytest.mark.parametrize('resource_type', EMITTED_RESOURCE_TYPES)
def test_every_emitted_resource_type_is_routed(server, resource_type):
    """Every resource type Scrapfly sends must be delivered."""
    assert server(wire({'result': {}}), resource_type=resource_type) == (200, True)


def test_unknown_resource_type_is_rejected(server):
    assert server(wire({'result': {}}), resource_type='bogus') == (400, False)


CRAWLER_PAYLOAD = {
    'event': 'crawler_finished',
    'payload': {
        'crawler_uuid': 'abc',
        'project': 'café',
        'env': 'prod',
        'action': 'crawl',
        'seed_url': 'https://example.com',
        'links': {'status': 'https://api.scrapfly.io/crawl/abc'},
        'state': {
            'urls_visited': 3, 'urls_extracted': 9, 'urls_to_crawl': 6,
            'urls_failed': 0, 'urls_skipped': 3, 'api_credit_used': 42,
            'duration': 12.5, 'stop_reason': 'page_limit',
        },
    },
}


def test_crawler_webhook_verifies_against_raw_body():
    """
    Guards the encoder trap: the signature covers the wire bytes, so verifying a
    re-serialized dict fails on separators, unicode escaping and float repr alike.
    """
    raw = wire(CRAWLER_PAYLOAD)
    webhook = webhook_from_payload(CRAWLER_PAYLOAD, signing_secrets=(SECRET,), signature=sign(raw), raw_body=raw)

    assert webhook.event == 'crawler_finished'
    assert webhook.state.urls_visited == 3


def test_crawler_webhook_rejects_missing_signature():
    raw = wire(CRAWLER_PAYLOAD)

    with pytest.raises(WebhookSignatureMissMatch):
        webhook_from_payload(CRAWLER_PAYLOAD, signing_secrets=(SECRET,), signature=None, raw_body=raw)


def test_crawler_webhook_rejects_wrong_signature():
    raw = wire(CRAWLER_PAYLOAD)

    with pytest.raises(WebhookSignatureMissMatch):
        webhook_from_payload(CRAWLER_PAYLOAD, signing_secrets=(SECRET,), signature='DEAD', raw_body=raw)


def test_crawler_webhook_refuses_to_verify_without_raw_body():
    """Verification is impossible without the wire bytes; fail loudly instead of guessing an encoding."""
    with pytest.raises(ValueError, match='raw_body'):
        webhook_from_payload(CRAWLER_PAYLOAD, signing_secrets=(SECRET,), signature=sign(wire(CRAWLER_PAYLOAD)))


def test_compressed_body_verifies_against_its_decompressed_bytes(server):
    """Signing happens before Content-Encoding, so the digest covers the inflated body."""
    body = wire({'result': {'content': 'legit'}})
    assert server(body, content_encoding='gzip', on_wire=gzip.compress(body)) == (200, True)


def test_lowercase_signature_header_is_accepted(server):
    """The digest is sent under both header spellings."""
    body = wire({'result': {'content': 'legit'}})
    assert server(body, signature_header='X-Scrapfly-Webhook-Signature-Lowercase') == (200, True)


def test_undecodable_body_is_rejected_without_a_500(server):
    """Decoding runs ahead of verification, so its failures are reachable unauthenticated."""
    assert server(b'not-gzip-at-all', content_encoding='gzip', signature=None) == (400, False)


def test_decompression_bomb_is_refused(server):
    """A small unauthenticated body must not buy an arbitrary allocation."""
    bomb = zlib.compress(b'\0' * (600 * 1024 * 1024))
    status, delivered = server(b'', content_encoding='deflate', signature=None, on_wire=bomb)
    assert (status, delivered) == (400, False)


MIB = 1024 * 1024

ENCODINGS = ('gzip', 'deflate', 'br', 'zstd')


def zstd():
    if sys.version_info >= (3, 14):
        from compression import zstd

        return zstd

    return pytest.importorskip('backports.zstd')


def encoder(encoding: str):
    """The one-shot compressor Scrapfly applies for `encoding`."""
    if encoding == 'br':
        return pytest.importorskip('brotli').compress

    if encoding == 'zstd':
        return zstd().compress

    return {'gzip': gzip.compress, 'deflate': zlib.compress}[encoding]


def zeros_stream(encoding: str, size: int) -> bytes:
    """`size` bytes of zeros compressed a MiB at a time, so the test never holds them."""
    if encoding == 'br':
        compressor = pytest.importorskip('brotli').Compressor(quality=5)
        feed, end = compressor.process, compressor.finish
    elif encoding == 'zstd':
        compressor = zstd().ZstdCompressor()
        feed, end = compressor.compress, compressor.flush
    else:
        compressor = zlib.compressobj(9, zlib.DEFLATED, 16 + zlib.MAX_WBITS if encoding == 'gzip' else zlib.MAX_WBITS)
        feed, end = compressor.compress, compressor.flush

    return b''.join(feed(b'\0' * MIB) for _ in range(size // MIB)) + end()


@pytest.mark.parametrize('encoding', ENCODINGS)
def test_body_spanning_many_chunks_round_trips(encoding):
    """Google's brotli still holds output once all input is in: a short body never shows it."""
    body = os.urandom(MIB).hex().encode() + b'\0' * (4 * MIB)
    assert decompress(encoder(encoding)(body), encoding) == body


@pytest.mark.parametrize('encoding', ENCODINGS)
def test_bomb_is_refused_a_chunk_at_a_time(encoding, monkeypatch):
    """The ceiling holds only if no single decoder call inflates far past the chunk size."""
    sizes = []
    bounded = api_response._bounded

    def recorded(chunks, limit):
        def each():
            for chunk in chunks:
                sizes.append(len(chunk))
                yield chunk

        return bounded(each(), limit)

    monkeypatch.setattr(api_response, '_bounded', recorded)

    with pytest.raises(WebhookBodyTooLarge):
        decompress(zeros_stream(encoding, 64 * MIB), encoding, limit=8 * MIB)

    # Google's brotli returns up to about twice output_buffer_limit.
    assert max(sizes) <= 2 * api_response._DECOMPRESS_CHUNK


@pytest.mark.parametrize('encoding', ENCODINGS)
def test_truncated_stream_is_refused(encoding):
    on_wire = encoder(encoding)(os.urandom(64 * 1024).hex().encode())

    with pytest.raises(ValueError):
        decompress(on_wire[:len(on_wire) // 2], encoding)


@pytest.mark.parametrize('encoding', ENCODINGS)
def test_trailing_data_is_refused(encoding):
    """brotlicffi 1.2.0.x neither raises on trailing bytes nor hands them back: a drain loop on them never ends."""
    with pytest.raises(Exception):
        decompress(encoder(encoding)(b'{}') + b'X', encoding)


def test_brotli_body_verifies_against_its_decompressed_bytes(server):
    """Past one output chunk, where Google's brotli came back cut short."""
    body = wire({'result': {'content': os.urandom(MIB).hex()}})
    assert server(body, content_encoding='br', on_wire=encoder('br')(body)) == (200, True)


def test_brotli_bomb_is_refused(server):
    """1 GiB of zeros is under 2 KB of brotli: one input chunk holds the whole bomb."""
    status, delivered = server(b'', content_encoding='br', signature=None, on_wire=zeros_stream('br', 300 * MIB))
    assert (status, delivered) == (400, False)


def test_brotli_decoder_without_output_cap_still_decodes(monkeypatch):
    """pip leaves brotlipy behind on upgrade, and its decoder has decompress() and no output cap."""
    brotli = pytest.importorskip('brotli')

    class Brotlipy:
        def __init__(self):
            self._decoder = brotli.Decompressor()

        def decompress(self, data):
            return self._decoder.process(data)

    monkeypatch.setattr(api_response, '_brotli_decoder', Brotlipy)
    body = os.urandom(MIB).hex().encode()

    with pytest.warns(UserWarning, match='brotlipy'):
        assert decompress(brotli.compress(body), 'br') == body


def test_capped_brotli_decoder_wins_over_a_stale_one(monkeypatch):
    """A brotlicffi older than 1.2, imported first, must not hide a brotli that caps its output."""
    pytest.importorskip('brotli')
    stale = types.ModuleType('brotlicffi')
    stale.Decompressor = type('Decompressor', (), {'decompress': lambda self, data: data})
    monkeypatch.setitem(sys.modules, 'brotlicffi', stale)

    assert hasattr(api_response._brotli_decoder(), 'can_accept_more_data')


def test_decodes_past_the_cap_wait_then_get_503(monkeypatch):
    """Each body decoded before its signature check can cost max_body_size: concurrency bounds the total."""
    pytest.importorskip('flask')
    from scrapfly import webhook

    holding, release = threading.Event(), threading.Event()

    def read(self, **kwargs):
        holding.set()
        release.wait(5)
        return {}

    monkeypatch.setattr(webhook, 'DECODE_WAIT_SECONDS', 0.1)
    monkeypatch.setattr(ResponseBodyHandler, 'read', read)
    app = create_server(signing_secrets=(SECRET,), callback=lambda *args: None, max_concurrent_decodes=1)
    headers = {'X-Scrapfly-Webhook-Resource-Type': 'scrape', 'X-Scrapfly-Webhook-Signature': 'DEAD'}
    first = threading.Thread(target=app.test_client().post, args=('/webhook',), kwargs={'data': b'{}', 'headers': headers})
    first.start()
    holding.wait(5)

    try:
        assert app.test_client().post('/webhook', data=b'{}', headers=headers).status_code == 503
    finally:
        release.set()
        first.join()

    assert app.test_client().post('/webhook', data=b'{}', headers=headers).status_code == 200


def test_missing_content_type_does_not_crash(server):
    """Content-Type is optional on the wire; its absence is not a server error."""
    body = wire({'result': {}})
    headers = {'X-Scrapfly-Webhook-Resource-Type': 'scrape', 'X-Scrapfly-Webhook-Signature': sign(body)}
    pytest.importorskip('flask')
    received = []
    app = create_server(signing_secrets=(SECRET,), callback=lambda data, kind, request: received.append(data))
    assert app.test_client().post('/webhook', data=body, headers=headers).status_code == 200


def test_create_server_refuses_to_run_unverified():
    """A falsy secret must not silently degrade to an unauthenticated endpoint."""
    pytest.importorskip('flask')

    for secrets in ((), None, ''):
        with pytest.raises(ValueError):
            create_server(signing_secrets=secrets, callback=lambda *args: None)


def test_a_bare_string_secret_is_one_secret_not_one_per_character():
    """Iterating a str would yield single-character HMAC keys an attacker can guess."""
    handler = ResponseBodyHandler(signing_secrets=SECRET)
    body = wire({'forged': True})

    assert handler.verify(body, sign(body)) is True
    assert handler.verify(body, hmac.new(b'p', body, hashlib.sha256).hexdigest().upper()) is False


@pytest.mark.parametrize('secrets', [('',), (123,), (None,)])
def test_unusable_secrets_are_rejected(secrets):
    with pytest.raises(ValueError):
        ResponseBodyHandler(signing_secrets=secrets)


def test_verify_answers_instead_of_raising():
    """verify() is public API: an absent header is a failed check, not a crash."""
    handler = ResponseBodyHandler(signing_secrets=(SECRET,))

    assert handler.verify(b'x', None) is False

    with pytest.raises(ValueError):
        ResponseBodyHandler().verify(b'x', 'AA')


def test_crawler_webhook_verifies_a_compressed_body():
    raw = wire(CRAWLER_PAYLOAD)
    webhook = webhook_from_payload(
        signing_secrets=(SECRET,),
        signature=sign(raw),
        raw_body=gzip.compress(raw),
        content_encoding='gzip',
    )

    assert webhook.event == 'crawler_finished'


def test_crawler_webhook_ignores_an_unsigned_payload_argument():
    """The result must come from the verified bytes, or verification is decorative."""
    raw = wire(CRAWLER_PAYLOAD)
    tampered = json.loads(json.dumps(CRAWLER_PAYLOAD))
    tampered['payload']['state']['api_credit_used'] = 999999

    webhook = webhook_from_payload(tampered, signing_secrets=(SECRET,), signature=sign(raw), raw_body=raw)

    assert webhook.state.api_credit_used == 42


ALERT_BODY = {'event_id': 'evt-1', 'alert': {'name': 'credit-low'}}


def alert_headers(timestamp, body):
    return {
        'X-Scrapfly-Webhook-Resource-Type': 'alert',
        'Content-Type': 'application/json',
        'X-Scrapfly-Webhook-Timestamp': str(timestamp),
        'X-Scrapfly-Webhook-Signature': sign(('%s.' % timestamp).encode('utf-8') + body),
    }


@pytest.fixture
def alert_client():
    pytest.importorskip('flask')

    received = []
    app = create_server(signing_secrets=(SECRET,), callback=lambda data, kind, request: received.append(data))

    def post(headers, body):
        before = len(received)
        response = app.test_client().post('/webhook', data=body, headers=headers)

        return response.status_code, len(received) > before

    return post


def test_alert_is_verified_over_timestamp_and_body(alert_client):
    """Alert webhooks sign `<timestamp>.<body>`, not the body alone."""
    body = wire(ALERT_BODY)

    assert alert_client(alert_headers(int(time.time()), body), body) == (200, True)


def test_alert_signed_over_the_body_alone_is_rejected(alert_client):
    body = wire(ALERT_BODY)
    headers = alert_headers(int(time.time()), body)
    headers['X-Scrapfly-Webhook-Signature'] = sign(body)

    assert alert_client(headers, body) == (401, False)


def test_alert_without_a_timestamp_is_rejected(alert_client):
    body = wire(ALERT_BODY)
    headers = alert_headers(int(time.time()), body)
    del headers['X-Scrapfly-Webhook-Timestamp']

    assert alert_client(headers, body) == (401, False)


@pytest.mark.parametrize('timestamp', [0, 'not-a-number'])
def test_alert_replay_or_garbage_timestamp_is_rejected(alert_client, timestamp):
    """A captured delivery must stop verifying once it falls outside the replay window."""
    body = wire(ALERT_BODY)

    assert alert_client(alert_headers(timestamp, body), body) == (401, False)
