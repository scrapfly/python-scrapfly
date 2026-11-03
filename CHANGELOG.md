# Changelog

## 1.0.0 (unreleased)

### Breaking

- Python 3.12 or newer is required.
- The `speedups` and `webhook-server` extras install `brotli>=1.2.0` on CPython and `brotlicffi>=1.2.0.0`
  elsewhere, in place of the archived `brotlipy`. pip does not remove `brotlipy` on upgrade, and it shadows
  `brotli` under the same import name: run `pip uninstall brotlipy`.
- `speedups` installs `backports.zstd` below Python 3.14 in place of `zstandard`, the zstd module urllib3 uses.
- Webhook bodies decode strictly: a single gzip member, no bytes after the compressed stream, no truncated stream.
- `scrapfly.polyfill` is removed.

### Fixed

- Brotli webhooks decode with Google's `brotli`, and bodies past about 480 KB are no longer cut short.
- Every webhook encoding is bounded per decoder call. A few KB of brotli or zstd could allocate gigabytes
  before the size limit applied, and crafted deflate or gzip bodies cost seconds of CPU, all before the
  signature is checked.
- The client no longer decodes a second time a body urllib3 already decompressed.

### Added

- `AsyncScrapflyClient`: every method of `ScrapflyClient` as a coroutine over httpx, `scrape_batch` and
  `crawl_prompt` as async iterators, a native `concurrent_scrape`. Both clients run the same operations
  (`scrapfly/api.py`): a call written once works in both. `httpx` is now a dependency, `backoff` no longer is.
- `create_server(max_concurrent_decodes=2)`: bodies decoded at once, so unauthenticated requests cannot
  stack `max_body_size` allocations. A delivery waiting longer than 30 s gets a 503 the sender retries.
- `webhook_from_payload(max_body_size=...)`.
