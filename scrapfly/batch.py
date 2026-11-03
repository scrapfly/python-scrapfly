"""
Streaming multipart/mixed decoder for the POST /scrape/batch endpoint.

The API emits one part per scrape result as each scrape completes, so parts
are decoded as their bytes arrive. MultipartDecoder is pushed chunks, which
lets the sync and the async client share it. Content-Encoding is undone by the
HTTP client before the bytes reach it.
"""

from __future__ import annotations

from typing import Dict, Iterator, List, Optional, Tuple


_CRLF = b"\r\n"

Part = Tuple[Dict[str, str], bytes]


class MultipartDecoder:
    """Push decoder of a multipart/mixed body: feed() returns the parts it completed."""

    def __init__(self, content_type: str):
        mime, params = _parse_content_type(content_type)

        if mime != "multipart/mixed":
            raise ValueError(f"scrape_batch: expected Content-Type multipart/mixed, got {content_type!r}")

        boundary = params.get("boundary")

        if not boundary:
            raise ValueError(f"scrape_batch: Content-Type multipart/mixed is missing boundary parameter: {content_type!r}")

        self._delimiter = b"--" + boundary.encode("ascii")
        self._buffer = bytearray()
        self._state = self._preamble
        self._headers: Optional[Dict[str, str]] = None
        self._length = 0
        self.done = False

    def feed(self, chunk: bytes) -> List[Part]:
        self._buffer += chunk
        parts: List[Part] = []

        while not self.done and self._state(parts):
            pass

        return parts

    def close(self) -> List[Part]:
        """The part the end of the stream cut short, if any."""
        if self.done or self._headers is None:
            return []

        return [(self._headers, bytes(self._buffer))]

    def _take(self, size: int, skip: int = 0) -> bytes:
        out = bytes(self._buffer[:size])
        del self._buffer[:size + skip]

        return out

    def _preamble(self, parts: List[Part]) -> bool:
        at = self._buffer.find(self._delimiter)

        if at == -1:
            return False

        self._take(at, len(self._delimiter))
        self._state = self._after_boundary

        return True

    def _after_boundary(self, parts: List[Part]) -> bool:
        if len(self._buffer) < 2:
            return False

        # RFC 2046: CRLF before another part, "--" after the last one. Anything else is broken framing.
        if self._take(2) != _CRLF:
            self.done = True

            return False

        self._state = self._part_headers

        return True

    def _part_headers(self, parts: List[Part]) -> bool:
        at = self._buffer.find(_CRLF + _CRLF)

        if at == -1:
            return False

        self._headers = {}

        for line in self._take(at, 4).split(_CRLF):
            if b":" in line:
                key, _, value = line.partition(b":")
                self._headers[key.decode("ascii", errors="replace").strip().lower()] = value.decode("ascii", errors="replace").strip()

        # Content-Length when the server sends it (it always does), the next boundary otherwise.
        length = self._headers.get("content-length", "")

        if length.isdigit():
            self._length = int(length)
            self._state = self._sized_body
        else:
            self._state = self._delimited_body

        return True

    def _sized_body(self, parts: List[Part]) -> bool:
        if len(self._buffer) < self._length:
            return False

        parts.append((self._headers, self._take(self._length)))
        self._headers = None
        self._state = self._next_boundary

        return True

    def _next_boundary(self, parts: List[Part]) -> bool:
        at = self._buffer.find(_CRLF + self._delimiter)

        if at == -1:
            return False

        self._take(at, 2 + len(self._delimiter))
        self._state = self._after_boundary

        return True

    def _delimited_body(self, parts: List[Part]) -> bool:
        at = self._buffer.find(_CRLF + self._delimiter)

        if at == -1:
            return False

        parts.append((self._headers, self._take(at, 2 + len(self._delimiter))))
        self._headers = None
        self._state = self._after_boundary

        return True


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


def iter_batch_parts(response) -> Iterator[Part]:
    """(part_headers, part_body) of a streamed requests.Response, header keys lowercased."""
    decoder = MultipartDecoder(response.headers.get("Content-Type", ""))

    for chunk in response.iter_content(chunk_size=8 * 1024):
        yield from decoder.feed(chunk)

        if decoder.done:
            return

    yield from decoder.close()


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


def is_api_error_part(parsed, headers: Dict[str, str]) -> bool:
    """Detect an API-generated error part (status >= 400, no scrape envelope)."""

    if _safe_int(headers.get("x-scrapfly-scrape-status"), 0) < 400:
        return False

    return isinstance(parsed, dict) and "result" not in parsed and "config" not in parsed


def error_from_api_error_part(parsed: Dict, headers: Dict[str, str], request):
    """Build the typed per-part error for an API-generated error body."""
    from .errors import ApiHttpClientError, ApiHttpServerError, ErrorFactory, api_error_args

    # A part has no HTTP status of its own, so the envelope decode falls back
    # to the status the multipart header carries for this part.
    args = api_error_args(parsed, http_status_code=_safe_int(headers.get("x-scrapfly-scrape-status"), 500))
    resource = args["resource"]
    http_code = args["http_status_code"]

    is_scraper_resource = resource in ErrorFactory.RESOURCE_TO_ERROR

    if http_code in ErrorFactory.HTTP_STATUS_TO_ERROR and not is_scraper_resource:
        error_class = ErrorFactory.HTTP_STATUS_TO_ERROR[http_code]
    elif is_scraper_resource:
        error_class = ErrorFactory.RESOURCE_TO_ERROR[resource]
    else:
        error_class = ApiHttpServerError if http_code >= 500 else ApiHttpClientError

    return error_class(
        request=request,
        response=_synthesize_part_response(request, http_code, parsed.get("reason")),
        **args,
    )


def _synthesize_part_response(request, http_code: int, reason):
    """Minimal Response reflecting the part's own status (a part has no HTTP response)."""
    from requests import Response
    from http.client import responses as status_reasons

    response = Response()
    response.status_code = http_code
    response.reason = reason if isinstance(reason, str) else status_reasons.get(http_code, "")
    response.request = request

    return response


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
