"""
WARC Parsing Utilities

This module provides utilities for parsing WARC (Web ARChive) format files.
WARC is a standard format for storing web crawl data.

The module provides automatic gzip decompression, record iteration, and
high-level interfaces for extracting page data.
"""

import gzip
import re
from typing import Iterator, List, Dict, Optional, BinaryIO, Union
from dataclasses import dataclass
from io import BytesIO


@dataclass
class WarcRecord:
    """
    Represents a single WARC record

    A WARC file contains multiple records, each representing a captured
    HTTP transaction or metadata.
    """
    record_type: str  # Type of record (response, request, metadata, etc.)
    url: str  # Associated URL
    headers: Dict[str, str]  # HTTP headers
    content: bytes  # Response body/content
    status_code: Optional[int]  # HTTP status code (for response records)
    warc_headers: Dict[str, str]  # WARC-specific headers

    def __repr__(self):
        return f"WarcRecord(type={self.record_type}, url={self.url}, status={self.status_code})"


class WarcParser:
    """
    Parser for WARC files with automatic decompression

    Provides methods to iterate through WARC records and extract page data.

    Example:
        ```python
        # From bytes
        parser = WarcParser(warc_bytes)

        # Iterate all records
        for record in parser.iter_records():
            print(f"{record.url}: {record.status_code}")

        # Get only HTTP responses
        for record in parser.iter_responses():
            print(f"Page: {record.url}")
            html = record.content.decode('utf-8')

        # Get all pages as simple dicts
        pages = parser.get_pages()
        for page in pages:
            print(f"{page['url']}: {page['status_code']}")
        ```
    """

    def __init__(self, warc_data: Union[bytes, BinaryIO]):
        """
        Initialize WARC parser

        Args:
            warc_data: WARC data as bytes or file-like object
                      (supports both gzip-compressed and uncompressed)
        """
        if isinstance(warc_data, bytes):
            # Try to decompress if gzipped
            if warc_data[:2] == b'\x1f\x8b':  # gzip magic number
                try:
                    warc_data = gzip.decompress(warc_data)
                except Exception:
                    pass  # Not gzipped or decompression failed
            self._data = BytesIO(warc_data)
        else:
            self._data = warc_data

    def iter_records(self) -> Iterator[WarcRecord]:
        """
        Iterate through all WARC records

        Yields:
            WarcRecord: Each record in the WARC file
        """
        self._data.seek(0)

        while True:
            # Read WARC version line
            version_line = self._read_line()
            if not version_line or not version_line.startswith(b'WARC/'):
                break

            # Read WARC headers
            warc_headers = self._read_headers()
            if not warc_headers:
                break

            # Get content length
            content_length = int(warc_headers.get('Content-Length', 0))

            # Read content block
            content_block = self._data.read(content_length)

            # Skip trailing newlines
            self._read_line()
            self._read_line()

            # Parse the record
            record = self._parse_record(warc_headers, content_block)
            if record:
                yield record

    def iter_responses(self) -> Iterator[WarcRecord]:
        """
        Iterate through HTTP response records only

        Filters out non-response records (requests, metadata, etc.)

        Yields:
            WarcRecord: HTTP response records only
        """
        for record in self.iter_records():
            if record.record_type == 'response' and record.status_code:
                yield record

    def get_pages(self) -> List[Dict]:
        """
        Get all crawled pages as simple dictionaries

        This is the easiest way to access crawl results without dealing
        with WARC format details.

        Returns:
            List of dicts with keys: url, status_code, headers, content

        Example:
            ```python
            pages = parser.get_pages()
            for page in pages:
                print(f"{page['url']}: {len(page['content'])} bytes")
                html = page['content'].decode('utf-8')
            ```
        """
        pages = []
        for record in self.iter_responses():
            pages.append({
                'url': record.url,
                'status_code': record.status_code,
                'headers': record.headers,
                'content': record.content
            })
        return pages

    def _read_line(self) -> bytes:
        """Read a single line from the WARC file"""
        line = self._data.readline()
        return line.rstrip(b'\r\n')

    def _read_headers(self) -> Dict[str, str]:
        """Read headers until empty line"""
        headers = {}
        while True:
            line = self._read_line()
            if not line:
                break

            # Parse header line
            if b':' in line:
                key, value = line.split(b':', 1)
                headers[key.decode('utf-8').strip()] = value.decode('utf-8').strip()

        return headers

    def _parse_record(self, warc_headers: Dict[str, str], content_block: bytes) -> Optional[WarcRecord]:
        """Parse a WARC record from headers and content"""
        record_type = warc_headers.get('WARC-Type', '')
        url = warc_headers.get('WARC-Target-URI', '')

        if record_type == 'response':
            # Parse HTTP response
            http_headers, body = self._parse_http_response(content_block)
            status_code = self._extract_status_code(content_block)

            return WarcRecord(
                record_type=record_type,
                url=url,
                headers=http_headers,
                content=body,
                status_code=status_code,
                warc_headers=warc_headers
            )
        elif record_type in ['request', 'metadata', 'warcinfo']:
            # Other record types - store raw content
            return WarcRecord(
                record_type=record_type,
                url=url,
                headers={},
                content=content_block,
                status_code=None,
                warc_headers=warc_headers
            )

        return None

    def _parse_http_response(self, content_block: bytes) -> tuple:
        """Parse HTTP response into headers and body"""
        try:
            # Split on double newline (end of headers)
            parts = content_block.split(b'\r\n\r\n', 1)
            if len(parts) < 2:
                parts = content_block.split(b'\n\n', 1)

            if len(parts) == 2:
                header_section, body = parts
            else:
                header_section, body = content_block, b''

            # Parse headers
            headers = {}
            lines = header_section.split(b'\r\n') if b'\r\n' in header_section else header_section.split(b'\n')

            # Skip status line
            for line in lines[1:]:
                if b':' in line:
                    key, value = line.split(b':', 1)
                    headers[key.decode('utf-8', errors='ignore').strip()] = value.decode('utf-8', errors='ignore').strip()

            return headers, body

        except Exception:
            return {}, content_block

    def _extract_status_code(self, content_block: bytes) -> Optional[int]:
        """Extract HTTP status code from response"""
        try:
            # Look for HTTP status line (e.g., "HTTP/1.1 200 OK")
            first_line = content_block.split(b'\r\n', 1)[0] if b'\r\n' in content_block else content_block.split(b'\n', 1)[0]
            match = re.match(rb'HTTP/\d\.\d (\d+)', first_line)
            if match:
                return int(match.group(1))
        except Exception:
            pass
        return None


def parse_warc(warc_data: Union[bytes, BinaryIO]) -> WarcParser:
    """
    Convenience function to create a WARC parser

    Args:
        warc_data: WARC data as bytes or file-like object

    Returns:
        WarcParser: Parser instance

    Example:
        ```python
        from scrapfly import parse_warc

        # Quick way to get all pages
        pages = parse_warc(warc_bytes).get_pages()
        for page in pages:
            print(f"{page['url']}: {page['status_code']}")
        ```
    """
    return WarcParser(warc_data)
