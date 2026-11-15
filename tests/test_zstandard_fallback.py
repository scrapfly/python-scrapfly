"""zstd without compression.zstd or backports.zstd: zstandard compresses extraction documents and decodes webhooks."""
import hashlib
import hmac
import json
import os
import sys

import pytest

from scrapfly import api_response
from scrapfly.api_response import ResponseBodyHandler, WebhookBodyTooLarge, decompress
from scrapfly.extraction_config import CompressionFormat, ExtractionConfig, ExtractionConfigError

pytestmark = pytest.mark.unit

zstandard = pytest.importorskip('zstandard')

MIB = 1024 * 1024
SECRET = 'probe-signing-secret'
DOCUMENT = '<html><body><h1>web-scraping.dev</h1></body></html>'


def standard_zstd():
    """compression.zstd or backports.zstd, the decoder the fallback must agree with."""
    if sys.version_info >= (3, 14):
        from compression import zstd

        return zstd

    return pytest.importorskip('backports.zstd')


def hide_module(monkeypatch, package: str, name: str):
    """`from package import name` raises ImportError, as when the module is not installed."""
    monkeypatch.setitem(sys.modules, f'{package}.{name}', None)
    loaded = sys.modules.get(package)

    if loaded is not None:
        monkeypatch.delattr(loaded, name, raising=False)


@pytest.fixture
def without_standard_zstd(monkeypatch):
    hide_module(monkeypatch, 'compression', 'zstd')
    hide_module(monkeypatch, 'backports', 'zstd')


def frames() -> dict:
    """Bodies and the zstd frames they compress to: raw, RLE and compressed blocks, with and without a checksum."""
    hex_body = os.urandom(64 * 1024).hex().encode()
    random_body = os.urandom(300 * 1024)
    mixed_body = os.urandom(MIB).hex().encode() + b'\0' * (2 * MIB)
    streamed = zstandard.ZstdCompressor(write_content_size=False).compressobj()

    return {
        'json': (b'{}', zstandard.ZstdCompressor().compress(b'{}')),
        'hex': (hex_body, zstandard.ZstdCompressor(level=19).compress(hex_body)),
        'random': (random_body, zstandard.ZstdCompressor().compress(random_body)),
        'zeros': (b'\0' * (4 * MIB), zstandard.ZstdCompressor().compress(b'\0' * (4 * MIB))),
        'checksum': (mixed_body, zstandard.ZstdCompressor(write_checksum=True).compress(mixed_body)),
        'streamed': (hex_body, streamed.compress(hex_body) + streamed.flush()),
    }


def test_extraction_document_is_compressed_with_zstandard(without_standard_zstd):
    config = ExtractionConfig(body=DOCUMENT, content_type='text/html', extraction_prompt='title',
                              document_compression_format=CompressionFormat.ZSTD)

    assert config.body != DOCUMENT.encode()
    assert zstandard.ZstdDecompressor().decompressobj().decompress(config.body) == DOCUMENT.encode()


def test_compressed_extraction_document_is_exported_decompressed(without_standard_zstd):
    config = ExtractionConfig(body=zstandard.compress(DOCUMENT.encode()), content_type='text/html',
                              extraction_prompt='title', document_compression_format=CompressionFormat.ZSTD)

    assert config.to_dict()['body'] == DOCUMENT


def test_extraction_without_any_zstd_module_names_what_to_install(without_standard_zstd, monkeypatch):
    monkeypatch.setitem(sys.modules, 'zstandard', None)

    with pytest.raises(ExtractionConfigError, match='zstandard'):
        ExtractionConfig(body=DOCUMENT, content_type='text/html', extraction_prompt='title',
                         document_compression_format=CompressionFormat.ZSTD)


@pytest.mark.parametrize('name', frames().keys())
def test_webhook_body_decodes_as_with_the_standard_module(name, without_standard_zstd):
    body, frame = frames()[name]

    assert decompress(frame, 'zstd') == body


def test_the_standard_module_reads_the_same_frames():
    zstd = standard_zstd()

    for body, frame in frames().values():
        assert zstd.decompress(frame) == body


def test_every_truncation_of_a_frame_is_refused(without_standard_zstd):
    """Cut in the magic number, the frame header, a block header, a block, or the checksum."""
    frame = zstandard.ZstdCompressor(write_checksum=True).compress(os.urandom(4 * 1024).hex().encode() * 40)

    for size in range(1, len(frame)):
        with pytest.raises((ValueError, zstandard.ZstdError)):
            decompress(frame[:size], 'zstd')


@pytest.mark.parametrize('extra', [b'X', zstandard.ZstdCompressor().compress(b'{}')], ids=['byte', 'second-frame'])
def test_data_after_the_frame_is_refused(extra, without_standard_zstd):
    with pytest.raises(ValueError, match='trailing data'):
        decompress(zstandard.ZstdCompressor().compress(b'{}') + extra, 'zstd')


def test_a_body_that_is_not_zstd_is_refused(without_standard_zstd):
    with pytest.raises(ValueError):
        decompress(b'not zstd at all', 'zstd')


def test_bomb_is_refused_a_chunk_at_a_time(without_standard_zstd, monkeypatch):
    sizes = []
    bounded = api_response._bounded

    def recorded(chunks, limit):
        def each():
            for chunk in chunks:
                sizes.append(len(chunk))
                yield chunk

        return bounded(each(), limit)

    monkeypatch.setattr(api_response, '_bounded', recorded)
    compressor = zstandard.ZstdCompressor().compressobj()
    bomb = b''.join(compressor.compress(b'\0' * MIB) for _ in range(64)) + compressor.flush()

    with pytest.raises(WebhookBodyTooLarge):
        decompress(bomb, 'zstd', limit=8 * MIB)

    assert max(sizes) <= api_response._DECOMPRESS_CHUNK
    assert sum(sizes) <= 8 * MIB + api_response._DECOMPRESS_CHUNK


def test_signed_webhook_verifies_against_its_decoded_body(without_standard_zstd):
    body = json.dumps({'result': {'content': 'web-scraping.dev'}}).encode()
    signature = hmac.new(SECRET.encode(), body, hashlib.sha256).hexdigest().upper()
    handler = ResponseBodyHandler(signing_secrets=(SECRET,))

    payload = handler.read(zstandard.ZstdCompressor().compress(body), 'zstd', 'application/json', signature)

    assert payload == {'result': {'content': 'web-scraping.dev'}}


def test_without_any_zstd_module_decoding_names_what_to_install(without_standard_zstd, monkeypatch):
    monkeypatch.setitem(sys.modules, 'zstandard', None)

    with pytest.raises(ImportError, match='zstandard'):
        decompress(b'\x28\xb5\x2f\xfd', 'zstd')
