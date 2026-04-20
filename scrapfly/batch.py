"""
Streaming multipart/mixed parser for the POST /scrape/batch endpoint.

The API emits one part per scrape result as each scrape completes;
the client must consume parts as they arrive (not after the whole
response lands) to get the end-to-end streaming benefit.

Design notes:
- Pure-Python parser (no new deps). Reuses `requests` streaming iter_content.
- Works uniformly for JSON and msgpack part bodies — the negotiated
  part content-type is surfaced to the caller in the yielded tuple.
- Does NOT perform decompression itself — `requests` already handles
  Content-Encoding gzip/zstd at the envelope level when `stream=True`
  is set with `decode_content=True` (default on requests Response).
"""

from __future__ import annotations

from typing import Dict, Iterator, Tuple


_CRLF = b"\r\n"


class _BufferedMultipartReader:
    """Incremental boundary-delimited reader over a byte chunk iterator."""

    def __init__(self, chunks: Iterator[bytes], boundary: bytes):
        self._chunks = chunks
        self._boundary = boundary
        self._buffer = bytearray()
        self._eof = False

    def _read_more(self) -> bool:
        """Pull one more chunk into the internal buffer. Returns True if data landed."""
        try:
            chunk = next(self._chunks)
        except StopIteration:
            self._eof = True

            return False

        if chunk:
            self._buffer.extend(chunk)

        return True

    def read_until(self, delimiter: bytes) -> bytes:
        """Read until `delimiter` appears in the buffer. The delimiter is consumed and NOT returned."""
        while True:
            idx = self._buffer.find(delimiter)

            if idx != -1:
                out = bytes(self._buffer[:idx])
                del self._buffer[: idx + len(delimiter)]

                return out

            if self._eof:
                # No more data and no delimiter — return whatever we have.
                out = bytes(self._buffer)
                self._buffer.clear()

                return out

            if not self._read_more() and self._eof:
                out = bytes(self._buffer)
                self._buffer.clear()

                return out

    def read_exact(self, n: int) -> bytes:
        """Read exactly n bytes from the stream (or fewer if EOF hits first)."""
        while len(self._buffer) < n and not self._eof:
            self._read_more()

        out = bytes(self._buffer[:n])
        del self._buffer[:n]

        return out

    def discard_prefix(self) -> None:
        """Discard everything up to and including the first boundary."""
        self.read_until(b"--" + self._boundary)


def _parse_content_type(header_value: str) -> Tuple[str, Dict[str, str]]:
    """Split a Content-Type header value into (mime, params)."""
    if ";" not in header_value:
        return header_value.strip().lower(), {}

    head, _, tail = header_value.partition(";")
    params: Dict[str, str] = {}

    for piece in tail.split(";"):
        piece = piece.strip()

        if "=" not in piece:
            continue

        k, _, v = piece.partition("=")
        params[k.strip().lower()] = v.strip().strip('"')

    return head.strip().lower(), params


def iter_batch_parts(
    response,  # requests.Response — duck-typed to avoid circular imports
) -> Iterator[Tuple[Dict[str, str], bytes]]:
    """
    Iterate (part_headers, part_body) tuples from a streaming
    multipart/mixed response. The per-part Content-Type is in
    `part_headers['content-type']` (lowercased key), and the
    correlation_id is in `part_headers['x-scrapfly-correlation-id']`.

    The caller is responsible for decoding `part_body` based on the
    part's Content-Type (JSON vs msgpack).

    Raises ValueError if the outer Content-Type is not multipart/mixed
    or if the boundary parameter is missing.
    """

    envelope_ct = response.headers.get("Content-Type", "")
    mime, params = _parse_content_type(envelope_ct)

    if mime != "multipart/mixed":
        raise ValueError(
            f"scrape_batch: expected Content-Type multipart/mixed, got {envelope_ct!r}"
        )

    boundary_str = params.get("boundary")

    if not boundary_str:
        raise ValueError(
            f"scrape_batch: Content-Type multipart/mixed is missing boundary parameter: {envelope_ct!r}"
        )

    boundary = boundary_str.encode("ascii")

    chunks = response.iter_content(chunk_size=8 * 1024)
    reader = _BufferedMultipartReader(chunks, boundary)

    # Skip anything before the first --boundary.
    reader.discard_prefix()

    while True:
        # After each --boundary we expect either CRLF (more parts) or
        # `--` (terminator). RFC 2046 mandates CRLF; any server
        # deviating from that is broken — return cleanly rather than
        # try to guess a framing variant.
        suffix = reader.read_exact(2)

        if suffix == b"--":
            # Final boundary. Drain CRLF and any epilogue.
            return

        if suffix != _CRLF:
            return

        # Read headers up to the blank line.
        header_block = reader.read_until(_CRLF + _CRLF)
        headers: Dict[str, str] = {}

        for line in header_block.split(_CRLF):
            if not line or b":" not in line:
                continue

            k, _, v = line.partition(b":")
            headers[k.decode("ascii", errors="replace").strip().lower()] = (
                v.decode("ascii", errors="replace").strip()
            )

        # Body framing: prefer Content-Length (we always emit it
        # server-side), fall back to boundary-delimited scan.
        cl_raw = headers.get("content-length")
        body: bytes

        if cl_raw and cl_raw.isdigit():
            body = reader.read_exact(int(cl_raw))
        else:
            # Read until next boundary marker. The "\r\n--<boundary>"
            # sequence is the canonical delimiter per RFC 2046.
            body = reader.read_until(_CRLF + b"--" + boundary)

        yield headers, body

        # If we used Content-Length, we still need to consume the
        # trailing "\r\n--<boundary>" that starts the next boundary.
        if cl_raw and cl_raw.isdigit():
            reader.read_until(_CRLF + b"--" + boundary)


def decode_part_body(
    headers: Dict[str, str],
    body: bytes,
    body_handler,
):
    """
    Decode one part body according to its Content-Type header.
    Delegates to the existing ResponseBodyHandler for msgpack/json
    symmetry with single /scrape responses.
    """

    content_type = headers.get("content-type", "application/json")

    # body_handler.__call__ takes (content, content_type) and returns
    # a parsed dict. It handles both JSON and msgpack.
    return body_handler(content=body, content_type=content_type)


# Header key prefix used by the server to forward upstream response
# headers on a proxified batch part (avoids collision with the
# multipart envelope's own headers).
_UPSTREAM_PREFIX = "x-scrapfly-upstream-"


def _build_proxified_response_from_part(headers, body, originating_request):
    """Synthesize a requests.Response from a proxified batch part.

    The part body is the raw upstream bytes and the part carries:
      * `Content-Type` — the upstream's content-type
      * `X-Scrapfly-Scrape-Status` — the upstream's HTTP status
      * `X-Scrapfly-Upstream-<Name>` — upstream response headers
      * `X-Scrapfly-Log-Uuid`, `X-Scrapfly-Content-Format` — scrapfly metadata

    We return a requests.Response with those values restored so the
    caller gets the same shape as a single proxified scrape.
    """
    from requests import Response
    from urllib3.response import HTTPResponse
    from io import BytesIO

    response = Response()
    response.status_code = _safe_int(headers.get("x-scrapfly-scrape-status"), 200)

    # Attach the upstream content-type + any Scrapfly metadata
    # (Api-Cost, Log, Content-Format) as the "visible" headers, and
    # expose the upstream response headers via the same interface by
    # stripping the X-Scrapfly-Upstream- prefix.
    for key, value in headers.items():
        lower = key.lower()
        if lower == "content-type":
            response.headers["Content-Type"] = value
        elif lower.startswith(_UPSTREAM_PREFIX):
            upstream_key = key[len(_UPSTREAM_PREFIX):]
            response.headers[upstream_key] = value
        elif lower.startswith("x-scrapfly-"):
            # Keep every Scrapfly metadata header visible on the
            # Response object (X-Scrapfly-Api-Cost, X-Scrapfly-Log,
            # X-Scrapfly-Content-Format, X-Scrapfly-Log-Uuid, etc.).
            response.headers[key] = value

    # The single-scrape proxified path exposes the log UUID on
    # `X-Scrapfly-Log` — normalize from `X-Scrapfly-Log-Uuid` so batch
    # consumers don't need a separate conditional.
    if "X-Scrapfly-Log" not in response.headers and "X-Scrapfly-Log-Uuid" in response.headers:
        response.headers["X-Scrapfly-Log"] = response.headers["X-Scrapfly-Log-Uuid"]

    # Wire the raw body. Using urllib3.HTTPResponse gives us the
    # same .content / .text / .iter_content() surface as a real
    # streamed requests.Response.
    response.raw = HTTPResponse(
        body=BytesIO(body),
        headers=dict(response.headers),
        status=response.status_code,
        preload_content=False,
    )
    response._content = body
    response._content_consumed = True

    if originating_request is not None:
        response.request = originating_request

    return response


def _safe_int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
