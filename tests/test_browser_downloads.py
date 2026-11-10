import asyncio
import base64
import hashlib
import os

import pytest

from scrapfly import AsyncCloudBrowserDownloads, BrowserConfig, BrowserDownloadError, CloudBrowserDownloads
from scrapfly.browser_downloads import MAX_CHUNK_SIZE, parse_downloads

SMALL = b'%PDF-1.7 small inline file'
# Not a multiple of 3 bytes, so its base64 ends with padding and the last chunk is short.
LARGE = os.urandom(3 * 1024 * 1024 + 7)


def b64(raw):
    return base64.b64encode(raw).decode()


class FakeBrowser:
    """The Cloud Browser's side of the download commands, as a CDP session answers them."""

    def __init__(self, streamed=True, orphans=None):
        self.streamed = streamed
        self.orphans = orphans or {}
        self.calls = []
        self.metadata_polls = 0
        self.ready_after = 0
        self.streams = {}

    def answer(self, method, params):
        self.calls.append((method, params))
        if method == 'ScrapiumBrowser.getDownloadsMetadatas':
            self.metadata_polls += 1
            if self.metadata_polls <= self.ready_after:
                return {'metadata': {}}
            return {'metadata': {'small.pdf': len(SMALL), 'large.bin': len(LARGE)}}
        if method == 'ScrapiumBrowser.getDownloads':
            return self.get_downloads()
        if method == 'IO.read':
            return self.read(params)
        if method == 'IO.close':
            self.streams.pop(params['handle'], None)
            return {}
        raise AssertionError('unexpected command %s' % method)

    def get_downloads(self):
        files = {'small.pdf': b64(SMALL), 'large.bin': b64(LARGE)}
        if not self.streamed:
            return {'files': files, 'files_by_guid': {'GUID-SMALL': files['small.pdf'], 'GUID-LARGE': files['large.bin']}}
        self.streams['scrapfly-download:1'] = {'data': files['large.bin'], 'off': 0}
        return {
            'files': {name: b64(raw) for name, raw in self.orphans.items()},
            'files_by_guid': {'GUID-SMALL': files['small.pdf']},
            'guid_names': {'GUID-SMALL': 'small.pdf', 'GUID-LARGE': 'large.bin'},
            'streams': {'GUID-LARGE': {'stream': 'scrapfly-download:1', 'size': len(LARGE), 'name': 'large.bin'}},
        }

    def read(self, params):
        if 'offset' in params:
            raise RuntimeError('download streams are sequential: IO.read offset is not supported')
        stream = self.streams.get(params['handle'])
        if stream is None:
            raise RuntimeError('Invalid stream handle: %s' % params['handle'])
        size = params.get('size') or 4 * 1024 * 1024
        size = min(size, MAX_CHUNK_SIZE)
        size -= size % 4
        start = stream['off']
        end = min(start + size, len(stream['data']))
        stream['off'] = end
        eof = end >= len(stream['data'])
        chunk = stream['data'][start:end]
        if eof:
            del self.streams[params['handle']]
        return {'data': chunk, 'base64Encoded': True, 'eof': eof}

    def reads(self):
        return [params for method, params in self.calls if method == 'IO.read']

    def closes(self):
        return [params['handle'] for method, params in self.calls if method == 'IO.close']


class SyncSession:
    """Shaped like Playwright's sync CDPSession: send(method, params) returns the result."""

    def __init__(self, browser):
        self.browser = browser

    def send(self, method, params=None):
        return self.browser.answer(method, params or {})


class AsyncSession:
    """Shaped like Playwright's async CDPSession: send(method, params) is a coroutine."""

    def __init__(self, browser):
        self.browser = browser

    async def send(self, method, params=None):
        await asyncio.sleep(0)
        return self.browser.answer(method, params or {})


def test_downloads_stream_is_sent_on_the_websocket_url():
    url = BrowserConfig(downloads_stream=True).websocket_url('key')
    assert 'downloads_stream=true' in url
    assert 'downloads_stream' not in BrowserConfig().websocket_url('key')
    assert BrowserConfig.from_dict(BrowserConfig(downloads_stream=True).to_dict()).downloads_stream is True


def test_streamed_shape_lists_small_files_inline_and_large_ones_as_handles():
    downloads = parse_downloads(FakeBrowser(orphans={'early.txt': b'before attach'}).get_downloads())
    by_name = {download.name: download for download in downloads}
    assert sorted(by_name) == ['early.txt', 'large.bin', 'small.pdf']
    assert by_name['small.pdf'].streamed is False
    assert by_name['small.pdf'].size == len(SMALL)
    assert by_name['small.pdf'].guid == 'GUID-SMALL'
    assert by_name['large.bin'].stream == 'scrapfly-download:1'
    assert by_name['large.bin'].size == len(LARGE)
    assert by_name['early.txt'].guid is None
    assert by_name['early.txt'].size == len(b'before attach')


def test_default_shape_lists_each_file_once():
    downloads = parse_downloads(FakeBrowser(streamed=False).get_downloads())
    assert sorted(download.name for download in downloads) == ['large.bin', 'small.pdf']
    assert all(not download.streamed for download in downloads)


def test_save_all_writes_every_file_and_reads_a_handle_in_chunks(tmp_path):
    browser = FakeBrowser(orphans={'early.txt': b'before attach'})
    downloads = CloudBrowserDownloads(SyncSession(browser), chunk_size=1024 * 1024)

    paths = downloads.save_all(str(tmp_path))

    assert sorted(os.path.basename(path) for path in paths) == ['early.txt', 'large.bin', 'small.pdf']
    assert (tmp_path / 'small.pdf').read_bytes() == SMALL
    assert (tmp_path / 'early.txt').read_bytes() == b'before attach'
    assert hashlib.sha256((tmp_path / 'large.bin').read_bytes()).digest() == hashlib.sha256(LARGE).digest()
    reads = browser.reads()
    assert len(reads) == -(-len(b64(LARGE)) // (1024 * 1024))
    assert all(read == {'handle': 'scrapfly-download:1', 'size': 1024 * 1024} for read in reads)
    assert browser.closes() == ['scrapfly-download:1']


def test_a_chunk_size_off_the_base64_grid_is_rounded_down():
    browser = FakeBrowser()
    downloads = CloudBrowserDownloads(SyncSession(browser), chunk_size=1000003)
    large = [download for download in downloads.list() if download.streamed][0]
    assert downloads.read(large) == LARGE
    assert {read['size'] for read in browser.reads()} == {1000000}


def test_chunk_size_outside_the_served_range_is_refused():
    with pytest.raises(ValueError):
        CloudBrowserDownloads(SyncSession(FakeBrowser()), chunk_size=MAX_CHUNK_SIZE + 4)
    with pytest.raises(ValueError):
        CloudBrowserDownloads(SyncSession(FakeBrowser()), chunk_size=2)


def test_default_shape_saves_without_any_io_read(tmp_path):
    browser = FakeBrowser(streamed=False)
    CloudBrowserDownloads(SyncSession(browser)).save_all(str(tmp_path))
    assert (tmp_path / 'large.bin').read_bytes() == LARGE
    assert browser.reads() == []


def test_a_short_stream_raises_and_still_closes_the_handle():
    browser = FakeBrowser()
    downloads = CloudBrowserDownloads(SyncSession(browser))
    large = [download for download in downloads.list() if download.streamed][0]
    large.size = len(LARGE) + 1
    with pytest.raises(BrowserDownloadError):
        downloads.read(large)
    assert browser.closes() == ['scrapfly-download:1']


def test_a_failed_read_still_closes_the_handle():
    browser = FakeBrowser()
    downloads = CloudBrowserDownloads(SyncSession(browser))
    large = [download for download in downloads.list() if download.streamed][0]
    large.stream = 'scrapfly-download:404'
    with pytest.raises(RuntimeError):
        downloads.read(large)
    assert browser.closes() == ['scrapfly-download:404']


def test_stopping_early_closes_the_handle():
    browser = FakeBrowser()
    downloads = CloudBrowserDownloads(SyncSession(browser), chunk_size=1024 * 1024)
    large = [download for download in downloads.list() if download.streamed][0]
    chunks = downloads.iter_chunks(large)
    next(chunks)
    chunks.close()
    assert browser.closes() == ['scrapfly-download:1']


def test_a_remote_name_cannot_leave_the_target_directory(tmp_path):
    browser = FakeBrowser(orphans={'../../escape.txt': b'x'})
    paths = CloudBrowserDownloads(SyncSession(browser)).save_all(str(tmp_path))
    assert os.path.join(str(tmp_path), 'escape.txt') in paths
    assert not (tmp_path.parent / 'escape.txt').exists()


def test_save_to_an_explicit_file(tmp_path):
    browser = FakeBrowser()
    downloads = CloudBrowserDownloads(SyncSession(browser))
    small = [download for download in downloads.list() if download.name == 'small.pdf'][0]
    target = str(tmp_path / 'renamed.pdf')
    assert downloads.save(small, target) == target
    assert (tmp_path / 'renamed.pdf').read_bytes() == SMALL


def test_wait_for_returns_once_the_size_settles():
    browser = FakeBrowser()
    browser.ready_after = 2
    size = CloudBrowserDownloads(SyncSession(browser)).wait_for('large.bin', timeout=5, interval=0)
    assert size == len(LARGE)
    assert browser.metadata_polls == 4


def test_wait_for_times_out_on_a_file_never_listed():
    with pytest.raises(TimeoutError):
        CloudBrowserDownloads(SyncSession(FakeBrowser())).wait_for('missing.bin', timeout=0.05, interval=0.01)


def test_a_plain_callable_is_a_session():
    browser = FakeBrowser()
    downloads = CloudBrowserDownloads(lambda method, params: browser.answer(method, params))
    assert {download.name for download in downloads.list()} == {'small.pdf', 'large.bin'}


def test_async_save_all_reads_a_handle_in_chunks(tmp_path):
    browser = FakeBrowser()

    async def run():
        downloads = AsyncCloudBrowserDownloads(AsyncSession(browser), chunk_size=1024 * 1024)
        await downloads.wait_for('large.bin', timeout=5, interval=0)
        return await downloads.save_all(str(tmp_path))

    paths = asyncio.run(run())
    assert sorted(os.path.basename(path) for path in paths) == ['large.bin', 'small.pdf']
    assert (tmp_path / 'large.bin').read_bytes() == LARGE
    assert (tmp_path / 'small.pdf').read_bytes() == SMALL
    assert browser.closes() == ['scrapfly-download:1']


def test_async_a_short_stream_raises_and_still_closes_the_handle():
    browser = FakeBrowser()

    async def run():
        downloads = AsyncCloudBrowserDownloads(AsyncSession(browser))
        large = [download for download in await downloads.list() if download.streamed][0]
        large.size = len(LARGE) - 1
        await downloads.read(large)

    with pytest.raises(BrowserDownloadError):
        asyncio.run(run())
    assert browser.closes() == ['scrapfly-download:1']


def test_async_plain_coroutine_function_is_a_session():
    browser = FakeBrowser()

    async def send(method, params):
        return browser.answer(method, params)

    async def run():
        downloads = AsyncCloudBrowserDownloads(send)
        large = [download for download in await downloads.list() if download.streamed][0]
        return await downloads.read(large)

    assert asyncio.run(run()) == LARGE
