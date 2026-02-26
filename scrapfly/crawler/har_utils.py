"""
HAR (HTTP Archive) Format Utilities

HAR is a JSON-based format for recording HTTP transactions.
Spec: http://www.softwareishard.com/blog/har-12-spec/

Structure:
{
  "log": {
    "version": "1.2",
    "creator": {...},
    "pages": [{...}],
    "entries": [
      {
        "startedDateTime": "2025-01-01T00:00:00.000Z",
        "request": {
          "method": "GET",
          "url": "https://example.com",
          "headers": [...],
          ...
        },
        "response": {
          "status": 200,
          "statusText": "OK",
          "headers": [...],
          "content": {
            "size": 1234,
            "mimeType": "text/html",
            "text": "..."
          },
          ...
        },
        ...
      }
    ]
  }
}
"""

import json
import gzip
from typing import Dict, List, Any, Optional, Iterator
from io import BytesIO


class HarEntry:
    """Represents a single HAR entry (HTTP request/response pair)"""

    def __init__(self, entry_data: Dict[str, Any]):
        """
        Initialize from HAR entry dict

        Args:
            entry_data: HAR entry dictionary
        """
        self._data = entry_data
        self._request = entry_data.get('request', {})
        self._response = entry_data.get('response', {})

    @property
    def url(self) -> str:
        """Get request URL"""
        return self._request.get('url', '')

    @property
    def method(self) -> str:
        """Get HTTP method"""
        return self._request.get('method', 'GET')

    @property
    def status_code(self) -> int:
        """Get response status code"""
        # Handle case where response doesn't exist or status is missing
        if not self._response:
            return 0
        status = self._response.get('status')
        if status is None:
            return 0
        # Ensure it's an int (HAR data might have status as string)
        try:
            return int(status)
        except (ValueError, TypeError):
            return 0

    @property
    def status_text(self) -> str:
        """Get response status text"""
        return self._response.get('statusText', '')

    @property
    def request_headers(self) -> Dict[str, str]:
        """Get request headers as dict"""
        headers = {}
        for header in self._request.get('headers', []):
            headers[header['name']] = header['value']
        return headers

    @property
    def response_headers(self) -> Dict[str, str]:
        """Get response headers as dict"""
        headers = {}
        for header in self._response.get('headers', []):
            headers[header['name']] = header['value']
        return headers

    @property
    def content(self) -> bytes:
        """Get response content as bytes"""
        content_data = self._response.get('content', {})
        text = content_data.get('text', '')

        # Handle base64 encoding if present
        encoding = content_data.get('encoding', '')
        if encoding == 'base64':
            import base64
            return base64.b64decode(text)

        # Return as UTF-8 bytes
        if isinstance(text, str):
            return text.encode('utf-8')
        return text

    @property
    def content_type(self) -> str:
        """Get response content type"""
        return self._response.get('content', {}).get('mimeType', '')

    @property
    def content_size(self) -> int:
        """Get response content size"""
        return self._response.get('content', {}).get('size', 0)

    @property
    def started_datetime(self) -> str:
        """Get when request was started (ISO 8601 format)"""
        return self._data.get('startedDateTime', '')

    @property
    def time(self) -> float:
        """Get total elapsed time in milliseconds"""
        return self._data.get('time', 0.0)

    @property
    def timings(self) -> Dict[str, float]:
        """Get detailed timing information"""
        return self._data.get('timings', {})

    def __repr__(self) -> str:
        return f"<HarEntry {self.method} {self.url} [{self.status_code}]>"


class HarArchive:
    """Parser and accessor for HAR (HTTP Archive) format data"""

    def __init__(self, har_data: bytes):
        """
        Initialize HAR archive from bytes

        Args:
            har_data: HAR file content as bytes (JSON format, may be gzipped)
        """
        # Decompress if gzipped
        if isinstance(har_data, bytes):
            if har_data[:2] == b'\x1f\x8b':  # gzip magic number
                har_data = gzip.decompress(har_data)
            har_data = har_data.decode('utf-8')

        # Parse the special format: {"log":{...,"entries":[]}}{"entry1"}{"entry2"}...
        # First object is HAR log structure, subsequent objects are individual entries
        objects = []
        decoder = json.JSONDecoder()
        idx = 0
        while idx < len(har_data):
            har_data_stripped = har_data[idx:].lstrip()
            if not har_data_stripped:
                break
            try:
                obj, end_idx = decoder.raw_decode(har_data_stripped)
                objects.append(obj)
                idx += len(har_data[idx:]) - len(har_data_stripped) + end_idx
            except json.JSONDecodeError:
                break

        # First object should be the HAR log structure
        if objects and 'log' in objects[0]:
            self._data = objects[0]
            self._log = self._data.get('log', {})
            # Remaining objects are the entries
            self._entries = objects[1:] if len(objects) > 1 else []
        else:
            # Fallback: standard HAR format
            self._data = json.loads(har_data) if isinstance(har_data, str) else {}
            self._log = self._data.get('log', {})
            self._entries = self._log.get('entries', [])

    @property
    def version(self) -> str:
        """Get HAR version"""
        return self._log.get('version', '')

    @property
    def creator(self) -> Dict[str, Any]:
        """Get creator information"""
        return self._log.get('creator', {})

    @property
    def pages(self) -> List[Dict[str, Any]]:
        """Get pages list"""
        return self._log.get('pages', [])

    def get_entries(self) -> List[HarEntry]:
        """
        Get all entries as list

        Returns:
            List of HarEntry objects
        """
        return [HarEntry(entry) for entry in self._entries]

    def iter_entries(self) -> Iterator[HarEntry]:
        """
        Iterate through all HAR entries

        Yields:
            HarEntry objects
        """
        for entry in self._entries:
            yield HarEntry(entry)

    def get_urls(self) -> List[str]:
        """
        Get all URLs in the archive

        Returns:
            List of unique URLs
        """
        urls = []
        for entry in self._entries:
            url = entry.get('request', {}).get('url', '')
            if url and url not in urls:
                urls.append(url)
        return urls

    def find_by_url(self, url: str) -> Optional[HarEntry]:
        """
        Find entry by exact URL match

        Args:
            url: URL to search for

        Returns:
            First matching HarEntry or None
        """
        for entry in self.iter_entries():
            if entry.url == url:
                return entry
        return None

    def filter_by_status(self, status_code: int) -> List[HarEntry]:
        """
        Filter entries by status code

        Args:
            status_code: HTTP status code to filter by

        Returns:
            List of matching HarEntry objects
        """
        return [entry for entry in self.iter_entries()
                if entry.status_code == status_code]

    def filter_by_content_type(self, content_type: str) -> List[HarEntry]:
        """
        Filter entries by content type (substring match)

        Args:
            content_type: Content type to filter by (e.g., 'text/html')

        Returns:
            List of matching HarEntry objects
        """
        return [entry for entry in self.iter_entries()
                if content_type.lower() in entry.content_type.lower()]

    def __len__(self) -> int:
        """Get number of entries"""
        return len(self._entries)

    def __repr__(self) -> str:
        return f"<HarArchive {len(self._entries)} entries>"
