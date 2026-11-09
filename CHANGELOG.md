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
- The `scrapy` extra requires Scrapy 2.11.1 or newer. Scrapy 2.11 and 2.12 themselves need `Twisted<24.7`.

### Fixed

- A large object (`format` `clob` or `blob`) whose body is JSON no longer raises `AttributeError: 'dict' object has
  no attribute 'decode'`, or a `TypeError` for a blob: the API body handler parsed it as an envelope. A large object
  is the scraped page itself, so only its compression is undone. Large objects are first resolved in 0.8.18; 0.8.17
  and earlier return the large-object URL string unresolved, with no warning.
- A large object the API answers with an error status raises its `ScrapflyError`, or an `HTTPError` when the answer
  carries no API error, instead of being returned as the page.
- Brotli webhooks decode with Google's `brotli`, and bodies past about 480 KB are no longer cut short.
- Every webhook encoding is bounded per decoder call. A few KB of brotli or zstd could allocate gigabytes
  before the size limit applied, and crafted deflate or gzip bodies cost seconds of CPU, all before the
  signature is checked.
- The client no longer decodes a second time a body urllib3 already decompressed.
- `scrape_batch` reads a batch-level error answered in msgpack: its message was lost.
- A connection error no longer prints the API key: requests put the request URL, `key` included, in its message
  and in the urllib3 errors chained to it, and an `HTTPError` from an error status printed it too. The key now
  reads `key=REDACTED`.
- An API error raised from an error status no longer chains the `HTTPError` it came from, whose URL carries the API
  key: a traceback, `logger.exception` or Sentry printed the key. The chained error reads `key=REDACTED`.
- `ScrapflySpider` crawls again on Scrapy 2.16 and later: it now defines `start()`, which Scrapy reads in place
  of `start_requests()` (Scrapy 2.19 no longer calls `start_requests()` at all).
- The Scrapy integration emits no deprecation warning from Scrapy 2.11 to 2.20: the middlewares no longer
  require the `spider` argument, the download handler is a coroutine on Scrapy 2.14+, retries are coroutines.
- `ScrapflySpider` crawls on Scrapy 2.20: the download handler no longer writes Scrapy's private handler tables,
  whose shape 2.20 changed. Every request failed with `NotSupported: Unsupported URL scheme 'https'`.
- A crawl reaching a second URL scheme (an `http://` page after `https://` ones, or a plain Scrapy `Request`) no
  longer fails with `NotSupported: Unsupported URL scheme 'http'`: building the download handler of the first
  scheme removed the `http` and `https` entries from the crawler's own `DOWNLOAD_HANDLERS`.

### Added

- `AsyncScrapflyClient`: every method of `ScrapflyClient` as a coroutine over httpx, `scrape_batch` and
  `crawl_prompt` as async iterators, a native `concurrent_scrape`. Both clients run the same operations
  (`scrapfly/api.py`): a call written once works in both. `httpx` is now a dependency, `backoff` no longer is.
- `create_server(max_concurrent_decodes=2)`: bodies decoded at once, so unauthenticated requests cannot
  stack `max_body_size` allocations. A delivery waiting longer than 30 s gets a 503 the sender retries.
- `webhook_from_payload(max_body_size=...)`.
- `crawl_extract(crawl_ids, prompt, schema)` and `Crawl.extract(prompt, schema)`: `POST /crawl/extract`, an
  object shaped by a JSON Schema, built from the content of one or more crawls (`CrawlerExtractResponse`).
- Scrapy: when an asyncio loop drives Scrapy (`AsyncioSelectorReactor`, or no reactor at all with
  `TWISTED_REACTOR_ENABLED = False` on Scrapy 2.15+), Scrapfly requests go through `AsyncScrapflyClient`, one
  connection pool per crawl. Other reactors keep Twisted's HTTP client. Tested on every Scrapy release from 2.11
  to 2.20 and every reactor mode each one supports.
