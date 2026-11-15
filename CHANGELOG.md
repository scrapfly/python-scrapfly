# Changelog

## 1.0.0 (2026-11-15)

### Breaking changes

- Python 3.12 or newer is required. pip keeps Python 3.11 and older on 0.12.0.
  To do: upgrade Python, or pin `scrapfly-sdk<1`.
- `httpx>=0.27` is a dependency and `backoff` no longer is.
  To do: if you pin `httpx` below 0.27, raise the pin. If your code imports `backoff`, install it yourself.
- The `speedups` and `webhook-server` extras install `brotli>=1.2.0` on CPython and `brotlicffi>=1.2.0.0`
  elsewhere, in place of the archived `brotlipy`. pip does not remove `brotlipy` on upgrade, and it takes the
  `brotli` import name. Brotli webhooks still decode with it, without the per-call output cap, and with a
  `UserWarning` that says to uninstall it.
  To do: `pip uninstall brotlipy`, then `pip install -U "scrapfly-sdk[speedups]"`.
- `speedups` installs `backports.zstd` below Python 3.14 in place of `zstandard`. When neither `compression.zstd`
  nor `backports.zstd` imports, the SDK uses `zstandard` to compress zstd extraction documents and to decode zstd
  webhooks.
  To do: nothing. `pip install -U "scrapfly-sdk[speedups]"` installs the backport.
- Webhook bodies decode strictly: one gzip member, one zstd frame, no bytes after the compressed stream, no
  truncated stream. Such a body raises `ValueError`, and `create_server` answers it with a 400.
  To do: nothing for webhooks Scrapfly sends. A body you compress yourself must be one complete stream.
- `create_server` decodes 2 bodies at a time (`max_concurrent_decodes=2`). A delivery that waits more than 30 s
  for its turn is answered 503, and Scrapfly sends it again.
  To do: pass `max_concurrent_decodes=N` to decode more bodies at once.
- `screenshot()` and `extract()` are sent once when the read times out. 0.12 sent them up to 5 times, and every
  call the API ran was billed. A dropped connection is still retried. `scrape()` is unchanged.
  To do: retry a `ReadTimeout` yourself if you need to.
- An error answer of the Screenshot or Extraction API that carries no API error body (a `502` text page, a `404`
  HTML page) raises `ApiHttpServerError` for a 5xx, and `ScreenshotAPIError` or `ExtractionAPIError` for a 4xx.
  All three are `ScrapflyError`s. 0.12 returned the page as the screenshot `image` or the extraction `data`,
  with `screenshot_success` true. With `no_raise=True` the response is returned with `screenshot_success` or
  `extraction_success` false and `error` set. A screenshot with `raise_on_upstream_error=False` raises too,
  since the answer is not the website's.
  To do: catch `ScrapflyError` around `screenshot()` and `extract()`, or pass `no_raise=True` and check the
  success flag.
- `extraction_prompt` reaches the model as written (see Fixed). A prompt extraction can now return a different
  result.
  To do: remove any workaround that encoded or decoded the prompt.
- Scrapy integration:
  - `ScrapflyMiddleware.process_exception` is a coroutine.
    To do: in a subclass, override it with `async def` and `await super().process_exception(...)`.
  - `ScrapflyMiddleware` is built by `from_crawler(crawler)` and its `__init__` takes `crawler`.
    To do: a subclass `__init__` takes `crawler=None` and calls `super().__init__(crawler)`.
  - On Scrapy 2.13+, `ScrapflyRefererMiddleware` overrides `get_processed_request` in place of
    `process_spider_output`. It has no `request_scheduled` on Scrapy 2.19+, where Scrapy dropped it.
    To do: a subclass overrides the same method.
  - When an asyncio loop drives Scrapy (`AsyncioSelectorReactor`, Scrapy's default since 2.13, or no reactor
    with `TWISTED_REACTOR_ENABLED = False` on Scrapy 2.15+), Scrapfly requests go through
    `AsyncScrapflyClient`, one connection pool per crawl. Other reactors keep Twisted's HTTP client.
    To do: nothing. Tested on every Scrapy release from 2.11 to 2.20 in every reactor mode each one supports.
  - `SCRAPFLY_DISTRIBUTED_MODE` is no longer read.
    To do: remove the setting.
  - The `scrapy` extra requires Scrapy 2.11.1 or newer. Scrapy 2.11 and 2.12 need `Twisted<24.7`.
    To do: upgrade Scrapy.

### Changed

- The default read timeouts are longer: `screenshot_api_read_timeout` 130 s (was 60 s) and
  `extraction_api_read_timeout` 165 s (was 35 s), each longer than the longest timeout its API accepts.
  To keep the old values, pass them to `ScrapflyClient`.
- `ScrapeConfig(session_sticky_proxy=None)` is the default (was `True`). Unset, the SDK sends no
  `session_sticky_proxy` and the API keeps the proxy sticky when `session` is set, as before. A scrape without a
  session no longer logs that the parameter is ignored.
- `proxy_pool` of the Web Scraping API and the crawler accepts `public_datacenter_pool` (the default),
  `public_residential_pool` and `public_tor_pool` (`ScrapeConfig.PUBLIC_DATACENTER_POOL`, ...).
  `ScrapeConfig.BASIC`, `ScrapeConfig.UNBLOCKER`, `ScrapeConfig.UNBLOCKER_ULTRA` and `ScrapeConfig.AUTO` name
  pools the API does not accept yet: a request naming one fails with `ERR::PROXY::POOL_NOT_FOUND`.
- `BrowserConfig(unblock=..., unblock_timeout=...)` emits a `DeprecationWarning`: the Cloud Browser does not read
  them. Use `ScrapflyClient.cloud_browser_unblock(url)` and connect to the `ws_url` it returns.

### Added

- `AsyncScrapflyClient`: every method of `ScrapflyClient` as a coroutine over httpx, `scrape_batch` and
  `crawl_prompt` as async iterators, a native `concurrent_scrape`. Both clients run the same operations
  (`scrapfly/api.py`): a call written once works in both. `ScrapflyClient.async_scrape`, `async_screenshot`,
  `async_extraction` and `concurrent_scrape` work as before.
- Cloud Browser vault linked services: `cloud_browser_vault_service_link`, `cloud_browser_vault_service_update`,
  `cloud_browser_vault_service_unlink`, `cloud_browser_vault_service_sync` and `cloud_browser_vault_service_test`,
  with the `LinkedService` enum (`LinkedService.ONE_PASSWORD`; a plain string is accepted too).
- Cloud Browser downloads: `CloudBrowserDownloads` and `AsyncCloudBrowserDownloads` list, wait for, read and save
  the files a session downloaded, a chunk at a time with `BrowserConfig(downloads_stream=True)`
  (`BrowserDownload`, `BrowserDownloadError`).
- `ScreenshotConfig(proxy_pool=...)`, sent as `proxy_pool`. The Screenshot API picks its pool itself and ignores
  it.
- `crawl_extract(crawl_ids, prompt, schema)` and `Crawl.extract(prompt, schema)`: `POST /crawl/extract`, an
  object shaped by a JSON Schema, built from the content of one or more crawls (`CrawlerExtractResponse`).
- `create_server(max_concurrent_decodes=2)`: bodies decoded at once, so unauthenticated requests cannot
  stack `max_body_size` allocations.
- `webhook_from_payload(max_body_size=...)`.
- The `scrapfly` package on PyPI, an alias of `scrapfly-sdk`: `pip install scrapfly` installs the SDK.

### Fixed

- `extraction_prompt` is sent as written. 0.12 URL-encoded it before the HTTP client encoded it again, so the
  model read `What%27s+the+price%3F` in place of `What's the price?`, on the Web Scraping API and the
  Extraction API.
- `scrape_batch` sends each config's `method` and `body`: a POST config ran as a GET with no body.
- `ScrapflySpider.retry(request, reason)` without a `delay` crawls the request again: it built a callback that
  never ran, so the retry was never scheduled.
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
- Documentation: the README and the docstrings name the proxy pools the API accepts, and the README and the
  Unblocker example scrape `web-scraping.dev`. The README shows how 0.12 code runs scrapes as coroutines (`async_scrape`,
  `concurrent_scrape`). `list_schedules` and its variants list the schedules of the API key's project and
  environment. The crawler example reads `status.state.urls_visited` and `status.state.urls_extracted`.
