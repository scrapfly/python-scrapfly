"""Retrieve the files a Cloud Browser session downloaded.

Connect with `BrowserConfig(downloads_stream=True)`: `ScrapiumBrowser.getDownloads` then returns
each small file inline and each large one as an IO stream handle, which these helpers read in
chunks with `IO.read`, so no CDP message is larger than one chunk. Without the option every file
comes back inline, and the helpers read that shape too.

A session is any object with a `send(method, params)` method answering the CDP result as a dict,
or such a callable: Playwright's `CDPSession` (sync API for `CloudBrowserDownloads`, async API for
`AsyncCloudBrowserDownloads`), or your own client over the WebSocket.

    downloads = CloudBrowserDownloads(page.context.new_cdp_session(page))
    downloads.wait_for('report.pdf')
    for path in downloads.save_all('downloads'):
        print(path)
"""
import asyncio
import base64
import os
import time
from dataclasses import dataclass
from typing import Any, AsyncGenerator, Awaitable, Callable, Dict, Generator, List, Optional

# Base64 characters per IO.read: an 8 MiB message carrying 6 MiB of the file.
DEFAULT_CHUNK_SIZE = 8 * 1024 * 1024

# The largest chunk the Cloud Browser serves per IO.read.
MAX_CHUNK_SIZE = 32 * 1024 * 1024

DEFAULT_WAIT_TIMEOUT = 60.0
DEFAULT_WAIT_INTERVAL = 0.5


class BrowserDownloadError(Exception):
    """A download could not be read whole."""


@dataclass
class BrowserDownload:
    """One file of the session's download directory.

    A small file carries its base64 content in `data`. A large one, with `downloads_stream`,
    carries the IO handle to read in `stream` instead, and its size in bytes in `size`.
    """

    name: str
    guid: Optional[str] = None
    size: Optional[int] = None
    data: Optional[str] = None
    stream: Optional[str] = None

    @property
    def streamed(self) -> bool:
        return self.stream is not None


def parse_downloads(result: Dict[str, Any]) -> List[BrowserDownload]:
    """The downloads of a `ScrapiumBrowser.getDownloads` result, in either of its shapes."""
    downloads = []
    if 'guid_names' in result or 'streams' in result:
        guid_names = result.get('guid_names') or {}
        for guid, data in (result.get('files_by_guid') or {}).items():
            name = guid_names.get(guid) or guid
            downloads.append(BrowserDownload(name=name, guid=guid, size=_decoded_size(data), data=data))
        for guid, entry in (result.get('streams') or {}).items():
            name = entry.get('name') or guid_names.get(guid) or guid
            downloads.append(BrowserDownload(name=name, guid=guid, size=entry.get('size'), stream=entry['stream']))
        # A file on disk with no download GUID, such as one finished before this session attached.
        for name, data in (result.get('files') or {}).items():
            downloads.append(BrowserDownload(name=name, size=_decoded_size(data), data=data))
        return downloads

    # Without downloads_stream every file is inline under `files`, and again under
    # `files_by_guid` with no name: `files` alone holds each file once.
    for name, data in (result.get('files') or {}).items():
        downloads.append(BrowserDownload(name=name, size=_decoded_size(data), data=data))
    return downloads


def _decoded_size(data: str) -> int:
    padding = 0
    if data.endswith('=='):
        padding = 2
    elif data.endswith('='):
        padding = 1
    return len(data) // 4 * 3 - padding


def _check_chunk_size(chunk_size: int) -> int:
    if chunk_size < 4 or chunk_size > MAX_CHUNK_SIZE:
        raise ValueError('chunk_size must be between 4 and %d base64 characters' % MAX_CHUNK_SIZE)
    return chunk_size - chunk_size % 4


def _sender(session: Any) -> Callable[[str, Dict[str, Any]], Any]:
    # A CDP session object (Playwright's CDPSession) is not callable: its send method is the sender.
    if callable(session):
        return session
    return session.send


def _target_path(download: BrowserDownload, path: Optional[str]) -> str:
    # The name comes from the remote browser: keep its last component only.
    name = os.path.basename(download.name.replace('\\', '/')) or (download.guid or 'download')
    if path is None:
        return name
    if os.path.isdir(path):
        return os.path.join(path, name)
    return path


def _decode_chunk(reply: Dict[str, Any]) -> bytes:
    data = reply.get('data') or ''
    if not data:
        return b''
    if reply.get('base64Encoded', True):
        return base64.b64decode(data)
    return data.encode()


class CloudBrowserDownloads:
    """Download helpers over a synchronous CDP session (Playwright's sync `CDPSession`)."""

    def __init__(self, session: Any, chunk_size: int = DEFAULT_CHUNK_SIZE):
        self._send = _sender(session)
        self.chunk_size = _check_chunk_size(chunk_size)

    def metadata(self) -> Dict[str, int]:
        """The size in bytes of every completed download, by filename."""
        return self._send('ScrapiumBrowser.getDownloadsMetadatas', {}).get('metadata') or {}

    def wait_for(self, filename: str, timeout: float = DEFAULT_WAIT_TIMEOUT, interval: float = DEFAULT_WAIT_INTERVAL) -> int:
        """Wait until `filename` is listed with the same size twice in a row, and return that size."""
        deadline = time.monotonic() + timeout
        last = -1
        while time.monotonic() < deadline:
            size = self.metadata().get(filename, -1)
            if size >= 0 and size == last:
                return size
            last = size
            time.sleep(interval)
        raise TimeoutError('%s did not finish downloading in %gs' % (filename, timeout))

    def list(self) -> List[BrowserDownload]:
        """Every download of the session: small ones with their content, large ones as handles."""
        return parse_downloads(self._send('ScrapiumBrowser.getDownloads', {}))

    def iter_chunks(self, download: BrowserDownload) -> Generator[bytes, None, None]:
        """The bytes of a download, one decoded chunk at a time. A stream handle is read once."""
        if not download.streamed:
            yield base64.b64decode(download.data or '')
            return
        written = 0
        try:
            while True:
                reply = self._send('IO.read', {'handle': download.stream, 'size': self.chunk_size})
                chunk = _decode_chunk(reply)
                written += len(chunk)
                if chunk:
                    yield chunk
                if reply.get('eof'):
                    break
        finally:
            self._send('IO.close', {'handle': download.stream})
        if download.size is not None and written != download.size:
            raise BrowserDownloadError('%s: read %d bytes, expected %d' % (download.name, written, download.size))

    def read(self, download: BrowserDownload) -> bytes:
        """The whole content of a download, in memory."""
        return b''.join(self.iter_chunks(download))

    def save(self, download: BrowserDownload, path: Optional[str] = None) -> str:
        """Write a download to `path` (a file or a directory, the current one by default) chunk by chunk."""
        target = _target_path(download, path)
        with open(target, 'wb') as out:
            for chunk in self.iter_chunks(download):
                out.write(chunk)
        return target

    def save_all(self, directory: str = '.') -> List[str]:
        """Write every download of the session into `directory` and return their paths."""
        os.makedirs(directory, exist_ok=True)
        paths = []
        for download in self.list():
            paths.append(self.save(download, directory))
        return paths


class AsyncCloudBrowserDownloads:
    """Download helpers over an asynchronous CDP session (Playwright's async `CDPSession`)."""

    def __init__(self, session: Any, chunk_size: int = DEFAULT_CHUNK_SIZE):
        self._send: Callable[[str, Dict[str, Any]], Awaitable[Dict[str, Any]]] = _sender(session)
        self.chunk_size = _check_chunk_size(chunk_size)

    async def metadata(self) -> Dict[str, int]:
        """The size in bytes of every completed download, by filename."""
        reply = await self._send('ScrapiumBrowser.getDownloadsMetadatas', {})
        return reply.get('metadata') or {}

    async def wait_for(self, filename: str, timeout: float = DEFAULT_WAIT_TIMEOUT, interval: float = DEFAULT_WAIT_INTERVAL) -> int:
        """Wait until `filename` is listed with the same size twice in a row, and return that size."""
        deadline = time.monotonic() + timeout
        last = -1
        while time.monotonic() < deadline:
            size = (await self.metadata()).get(filename, -1)
            if size >= 0 and size == last:
                return size
            last = size
            await asyncio.sleep(interval)
        raise TimeoutError('%s did not finish downloading in %gs' % (filename, timeout))

    async def list(self) -> List[BrowserDownload]:
        """Every download of the session: small ones with their content, large ones as handles."""
        return parse_downloads(await self._send('ScrapiumBrowser.getDownloads', {}))

    async def iter_chunks(self, download: BrowserDownload) -> AsyncGenerator[bytes, None]:
        """The bytes of a download, one decoded chunk at a time. A stream handle is read once."""
        if not download.streamed:
            yield base64.b64decode(download.data or '')
            return
        written = 0
        try:
            while True:
                reply = await self._send('IO.read', {'handle': download.stream, 'size': self.chunk_size})
                chunk = _decode_chunk(reply)
                written += len(chunk)
                if chunk:
                    yield chunk
                if reply.get('eof'):
                    break
        finally:
            await self._send('IO.close', {'handle': download.stream})
        if download.size is not None and written != download.size:
            raise BrowserDownloadError('%s: read %d bytes, expected %d' % (download.name, written, download.size))

    async def read(self, download: BrowserDownload) -> bytes:
        """The whole content of a download, in memory."""
        chunks = []
        async for chunk in self.iter_chunks(download):
            chunks.append(chunk)
        return b''.join(chunks)

    async def save(self, download: BrowserDownload, path: Optional[str] = None) -> str:
        """Write a download to `path` (a file or a directory, the current one by default) chunk by chunk."""
        target = _target_path(download, path)
        with open(target, 'wb') as out:
            async for chunk in self.iter_chunks(download):
                out.write(chunk)
        return target

    async def save_all(self, directory: str = '.') -> List[str]:
        """Write every download of the session into `directory` and return their paths."""
        os.makedirs(directory, exist_ok=True)
        paths = []
        for download in await self.list():
            paths.append(await self.save(download, directory))
        return paths
