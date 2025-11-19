# Getting Started with Scrapfly Crawler API

 The **Scrapfly Crawler API** enables recursive website crawling at scale. We leverage [WARC](https://scrapfly.home/docs/crawler-api/warc-format), Parquet format for large scale scraping and you can easily visualize using HAR artifact. Crawl entire websites with configurable limits, extract content in multiple formats simultaneously, and retrieve results as industry-standard artifacts.

  **Early Access Feature**The Crawler API is currently in early access. Features and API may evolve based on user feedback.

 

## Quick Start: Choose Your Workflow  

 The Crawler API supports two integration patterns. Choose the approach that best fits your use case:

    Polling Workflow Poll status endpoint    Real-Time Webhooks Instant notifications  

 ###   Polling Workflow

 Schedule a crawl, poll the status endpoint to monitor progress, and retrieve results when complete. **Best for batch processing, testing, and simple integrations.**

  

1. **Schedule Crawl**Create a crawler with a single API call. The API returns immediately with a crawler UUID:
    
     ```
    curl -X POST "https://api.scrapfly.home/crawl?key=scp-live-d8ac176c2f9d48b993b58675bdf71615" \
      -H 'Content-Type: application/json' \
      -d '{
        "url": "https://example.com",
        "page_limit": 100
      }'
    ```
    
     
    
       
    
     
    
     
    
     
    
    Response includes crawler UUID and status:
    
     ```
    {"uuid": "550e8400-e29b-41d4-a716-446655440000", "status": "PENDING"}
    ```
2. **Monitor Progress**Poll the status endpoint to track crawl progress:
    
     ```
    curl https://api.scrapfly.home/crawl/{uuid}/status?key=scp-live-d8ac176c2f9d48b993b58675bdf71615
    ```
    
     
    
       
    
     
    
     
    
     
    
    Status response shows real-time progress:
    
     ```
    {
      "crawler_uuid": "550e8400-e29b-41d4-a716-446655440000",
      "status": "RUNNING",
      "is_finished": false,
      "is_success": null,
      "state": {
        "urls_visited": 847,
        "urls_extracted": 1523,
        "urls_failed": 12,
        "urls_skipped": 34,
        "urls_to_crawl": 676,
        "api_credit_used": 8470,
        "duration": 145,
        "stop_reason": null
      }
    }
    ```
    
     
    
       
    
     
    
     
    
     
    
    #### Understanding the Status Response
    
     | Field | Values | Description |
    |---|---|---|
    | `status` | `PENDING`  `RUNNING`  `DONE`  `CANCELLED` | Current crawler state - actively running or completed |
    | `is_finished` | `true` / `false` | Whether crawler has stopped (regardless of success/failure) |
    | `is_success` | `true` - Success  `false` - Failed  `null` - Running | Outcome of the crawl (only set when finished) |
    | `stop_reason` | See table below | Why the crawler stopped (only set when finished) |
    
     **Stop Reasons:**
    
     | Stop Reason | Description |
    |---|---|
    | `no_more_urls` | All discovered URLs have been crawled - **normal completion** |
    | `page_limit` | Reached the configured `page_limit` |
    | `max_duration` | Exceeded the `max_duration` time limit |
    | `max_api_credit` | Reached the `max_api_credit` limit |
    | `seed_url_failed` | The starting URL failed to crawl - **no URLs visited** |
    | `user_cancelled` | User manually cancelled the crawl via API |
    | `crawler_error` | Internal crawler error occurred |
    | `no_api_credit_left` | Account ran out of API credits during crawl |
3. **Retrieve Results**Once `is_finished: true`, download artifacts or query content:
    
     ```
    # Download WARC artifact (recommended for large crawls)
    curl https://api.scrapfly.home/crawl/{uuid}/artifact?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&type=warc -o crawl.warc.gz
    
    # Query specific URL content
    curl https://api.scrapfly.home/crawl/{uuid}/contents?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&url=https://example.com/page&format=markdown
    
    # Or batch retrieve multiple URLs (max 100 per request)
    curl -X POST https://api.scrapfly.home/crawl/{uuid}/contents/batch?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&formats=markdown \
      -H 'Content-Type: text/plain' \
      -d 'https://example.com/page1
    https://example.com/page2
    https://example.com/page3'
    ```
    
     
    
       
    
     
    
     
    
     
    
      For comprehensive retrieval options, see [Retrieving Crawler Results](https://scrapfly.home/docs/crawler-api/results).
 
 

###   Real-Time Webhook Workflow

 Schedule a crawl with webhook configuration, receive instant HTTP callbacks as events occur, and process results in real-time. **Best for real-time data ingestion, streaming pipelines, and event-driven architectures.**

  

  **Webhook Setup Required** Before using webhooks, you must [configure a webhook](https://scrapfly.home/dashboard/webhook) in your dashboard with your endpoint URL and authentication. Then reference it by name in your API call.

 

1. **Schedule Crawl with Webhook**Create a crawler and specify the webhook name configured in your dashboard:
    
     ```
    curl -X POST "https://api.scrapfly.home/crawl?key=scp-live-d8ac176c2f9d48b993b58675bdf71615" \
      -H 'Content-Type: application/json' \
      -d '{
        "url": "https://example.com",
        "page_limit": 100,
        "webhook_name": "my-crawler-webhook",
        "webhook_events": [
          "crawler_started",
          "crawler_url_visited",
          "crawler_finished"
        ]
      }'
    ```
    
     
    
       
    
     
    
     
    
     
    
    Response includes crawler UUID:
    
     ```
    {"uuid": "550e8400-e29b-41d4-a716-446655440000", "status": "PENDING"}
    ```
2. **Receive Real-Time Webhooks**Your endpoint receives HTTP POST callbacks as events occur during the crawl:
    
     ```
    {
      "event": "crawler_url_visited",
      "payload": {
        "crawler_uuid": "550e8400-e29b-41d4-a716-446655440000",
        "url": "https://example.com/page",
        "status_code": 200,
        "depth": 1,
        "state": {
          "urls_visited": 42,
          "urls_to_crawl": 158,
          "api_credit_used": 420
        }
      }
    }
    ```
    
     
    
       
    
     
    
     
    
     
    
     **Webhook Headers:**
    
     | Header | Purpose |
    |---|---|
    | `X-Scrapfly-Crawl-Event-Name` | Event type (e.g., `crawler_url_visited`) for fast routing |
    | `X-Scrapfly-Webhook-Job-Id` | Crawler UUID for tracking |
    | `X-Scrapfly-Webhook-Signature` | HMAC-SHA256 signature for verification |
3. **Process Events in Real-Time**Handle webhook callbacks to stream data to your database, trigger pipelines, or process results:
    
     ```
    # Example: Python webhook handler
    @app.post('/webhooks/crawler')
    def handle_crawler_webhook(request):
        event = request.headers['X-Scrapfly-Crawl-Event-Name']
        payload = request.json()['payload']
    
        if event == 'crawler_url_visited':
            # Stream scraped content to database
            save_to_database(payload['url'], payload['content'])
    
        elif event == 'crawler_finished':
            # Trigger downstream processing
            trigger_data_pipeline(payload['crawler_uuid'])
    
        return {'status': 'ok'}
    ```
 
  For detailed webhook documentation and all available events, see [Crawler Webhook Documentation](https://scrapfly.home/docs/crawler-api/webhook).

 

 

## Error Handling  

 Crawler API uses standard HTTP response codes and provides detailed error information:

 | `200` - OK | Request successful |
|---|---|
| `201` - Created | Crawler job created successfully |
| `400` - Bad Request | Invalid parameters or configuration |
| `401` - Unauthorized | Invalid or missing API key |
| `404` - Not Found | Crawler job not found |
| `429` - Too Many Requests | Rate limit or concurrency limit exceeded |
| `500` - Server Error | Internal server error |
| See the [full error list](https://scrapfly.home/docs/crawler-api/errors) for more details. |

 

 

 

 

---

## API Specification

   ### Create Crawler Job

 POST `https://api.scrapfly.home/crawl` 

 Create a new crawler job with custom configuration. The API returns immediately with a crawler UUID that you can use to monitor progress and retrieve results.

####  Query Parameters (Authentication) 

 These parameters must be passed in the **URL query string**, not in the request body.

Parameter

Description

Example

 

 [key](#api_param_key)    

required

 

 Your Scrapfly API key for authentication. You can find your key on your [dashboard](https://scrapfly.home/docs/project#api-keys). 

 Query Parameter Only **Must be passed as a URL query parameter** (e.g., `?key=YOUR_KEY`), **never in the POST request body**. This applies to all Crawler API endpoints. 

 `?key=16eae084cff64841be193a95fc8fa67d` 
 Append to endpoint URL 

 

####  Request Body (Crawler Configuration) 

 These parameters configure the crawler behavior and must be sent in the **JSON request body**.

Parameter

Description

Example

 

  

 [url](#api_param_url)    

required

 

 Starting URL for the crawl. Must be a valid HTTP/HTTPS URL. The crawler will begin discovering and crawling linked pages from this seed URL. [ Must be URL encoded  ](https://scrapfly.home/web-scraping-tools/urlencode) 

 `url=https://example.com` `url=https://example.com/blog` 

 

 [page\_limit](#api_param_page_limit)    

popular

 default: 0 (unlimited) 

 

 Maximum number of pages to crawl. Must be non-negative. Set to `0` for unlimited (subject to subscription limits). Use this to limit crawl scope and control costs. 

- `page_limit=100`
- `page_limit=1000`
- `page_limit=0` (unlimited)
 
 

 

 [max\_depth](#api_param_max_depth)    

popular

 default: 0 (unlimited) 

 

 Maximum link depth from starting URL. Must be non-negative. Depth 0 is the starting URL, depth 1 is links from the starting page, etc. Set to `0` for unlimited depth. Use lower values for focused crawls, higher values for comprehensive site crawling. 

- `max_depth=2`
- `max_depth=5`
- `max_depth=0` (unlimited)
 
 

 

 [exclude\_paths](#api_param_exclude_paths)    

popular

 default: [] 

 

 Exclude URLs matching these path patterns. Supports wildcards (`*`). **Maximum 100 paths.** Mutually exclusive with `include_only_paths`. Useful for skipping admin pages, authentication flows, or irrelevant sections. 

- `exclude_paths=["/admin/*"]`
- `exclude_paths=["*/login", "*/signup"]`
- `exclude_paths=["/api/*", "/assets/*"]`
 
 

 

 [include\_only\_paths](#api_param_include_only_paths)    

popular

 default: [] 

 

 Only crawl URLs matching these path patterns. Supports wildcards (`*`). **Maximum 100 paths.** Mutually exclusive with `exclude_paths`. Useful for focusing on specific sections like blogs or product pages. 

- `include_only_paths=["/blog/*"]`
- `include_only_paths=["/blog/*", "/articles/*"]`
- `include_only_paths=["/products/*/reviews"]`
 
 

 

   Show Advanced Crawl Configuration (domain restrictions, delays, headers, sitemaps...)  [ignore\_base\_path\_restriction](#api_param_ignore_base_path_restriction)    

 default: false 

 

 By default, the crawler only follows links within the same base path as the starting URL. For example, starting from `https://example.com/blog` restricts crawling to `/blog/*`. Enable this to allow crawling any path on the same domain. 

- `ignore_base_path_restriction=true`
- `ignore_base_path_restriction=false`
 
 

 

 [follow\_external\_links](#api_param_follow_external_links)    

 default: false 

 

 Allow the crawler to follow links to external domains. By default, crawling is restricted to the starting domain. 

  **Important: External Link Behavior** When `follow_external_links=true`:

- **Default (no domains specified):** The crawler will follow links to ANY external domain (except social media URLs)
- **With `allowed_external_domains`:** Only domains matching the specified patterns will be followed
 
 **External page scraping behavior:**

- External pages ARE scraped (content is extracted, credits are consumed)
- Links from external pages are NOT followed (crawling goes only "one hop" into external domains)
 
 

 

- `follow_external_links=true` Follow ANY external domain (except social media)
- `follow_external_links=false` Stay within starting domain only
 
 

 

 [allowed\_external\_domains](#api_param_allowed_external_domains)    

 default: [] 

 

 Whitelist of external domains to crawl when `follow_external_links=true`. **Maximum 250 domains.** Supports fnmatch-style wildcards (`*`) for flexible pattern matching. 

 **Pattern Matching Examples:**- `*.example.com` - Matches all subdomains of example.com
- `specific.org` - Exact domain match only
- `blog.*.com` - Matches blog.anything.com
 
  **Scraping vs. Crawling External Pages** When a page contains a link to an allowed external domain: 
 **The crawler WILL:** Scrape the external page (extract content, consume credits) 
 **The crawler WILL NOT:** Follow links found on that external page 

 *Example:* Crawling `example.com` with `allowed_external_domains=["*.wikipedia.org"]` will scrape Wikipedia pages linked from example.com, but will NOT crawl additional links discovered on Wikipedia.

 

 

- `allowed_external_domains=["cdn.example.com"]` Only follow links to cdn.example.com
- `allowed_external_domains=["*.example.com"]` Follow all subdomains of example.com
- `allowed_external_domains=["blog.example.com", "docs.example.com"]` Follow multiple specific domains
 
 

 

 [rendering\_delay](#api_param_rendering_delay)    

 

 Wait time in milliseconds after page load before extraction. Set to `0` to disable browser rendering (HTTP-only mode). Range: **0 or 1-25000ms (max 25 seconds)**. Only applies when browser rendering is enabled. Use this for pages that load content dynamically. 

- `rendering_delay=0` (no rendering)
- `rendering_delay=2000`
- `rendering_delay=5000`
- `rendering_delay=25000` (maximum)
 
 

 

 [max\_concurrency](#api_param_max_concurrency)    

 default: account limit 

 

 Maximum number of concurrent scrape requests. Controls crawl speed and resource usage. Limited by your account's concurrency limit. Set to `0` to use account/project default. 

- `max_concurrency=5`
- `max_concurrency=10`
- `max_concurrency=0` (use account limit)
 
 

 

 [headers](#api_param_headers)    

 default: {} 

 

 Custom HTTP headers to send with each request. Pass as JSON object. [ Must be URL encoded  ](https://scrapfly.home/web-scraping-tools/urlencode) 

 `headers={"Authorization": "Bearer token"}` 

 `headers={"Referer": "https://example.com"}` 

 

 

 [delay](#api_param_delay)    

 default: "0" 

 

 Add a delay between requests in milliseconds. Range: **0-15000ms (max 15 seconds)**. Use this to be polite to target servers and avoid overwhelming them with requests. Value must be provided as a string. 

- `delay="1000"` (1 second)
- `delay="5000"` (5 seconds)
- `delay="15000"` (maximum)
 
 

 

 [user\_agent](#api_param_user_agent)    

 default: null 

 

 Custom User-Agent string to use for all requests. If not specified, Scrapfly will use appropriate User-Agent headers automatically. This is a shorthand for setting the `User-Agent` header. 

  **Important: ASP Compatibility** When `asp=true` (Anti-Scraping Protection is enabled), this parameter is **ignored**. ASP manages User-Agent headers automatically for optimal bypass performance. 

 **Choose one approach:**

- **Use ASP** (`asp=true`) - Automatic User-Agent management with advanced bypass
- **Use custom User-Agent** (`user_agent=...`) - Manual control, ASP disabled
 
 

 

 `user_agent=MyBot/1.0 (+https://example.com/bot)` 

 

 [use\_sitemaps](#api_param_use_sitemaps)    

 default: false 

 

 Use sitemap.xml for URL discovery if available. When enabled, the crawler will check for `/sitemap.xml` and use it to discover additional URLs to crawl. 

- `use_sitemaps=true`
- `use_sitemaps=false`
 
 

 

 [respect\_robots\_txt](#api_param_respect_robots_txt)    

 default: true 

 

 Respect robots.txt rules. When enabled, the crawler will honor `Disallow` directives from the target site's robots.txt file. 

- `respect_robots_txt=true`
- `respect_robots_txt=false`
 
 

 

 [cache](#api_param_cache)    

popular

 default: false 

 

 Enable the cache layer for crawled pages. If a page is already cached and not expired, the cached version will be used instead of re-crawling. 

- `cache=true`
- `cache=false`
 
 

 

 [cache\_ttl](#api_param_cache_ttl)    

 default: default TTL 

 

 Cache time-to-live in seconds. Range: **0-604800 seconds (max 7 days)**. Only applies when `cache=true`. Set to `0` to use default TTL. After this duration, cached pages will be considered stale and re-crawled. 

- `cache_ttl=3600`
- `cache_ttl=86400`
- `cache_ttl=604800`
 
 

 

 [cache\_clear](#api_param_cache_clear)    

 default: false 

 

 Force refresh of cached pages. When enabled, all pages will be re-crawled even if valid cache entries exist. 

- `cache_clear=true`
- `cache_clear=false`
 
 

 

 [ignore\_no\_follow](#api_param_ignore_no_follow)    

 default: false 

 

 Ignore `rel="nofollow"` attributes on links. By default, links with `nofollow` are not crawled. Enable this to crawl all links regardless of the nofollow attribute. 

- `ignore_no_follow=true`
- `ignore_no_follow=false`
 
 

 

 

  [content\_formats](#api_param_content_formats)    

popular

 default: ["html"] 

 

 List of content formats to extract from each crawled page. You can specify multiple formats to extract different representations simultaneously. Extracted content is available via the `/contents` endpoint or in downloaded artifacts. 

 **Available formats:**- `html` - Raw HTML content
- `clean_html` - HTML with boilerplate removed
- `markdown` - Markdown format (ideal for LLM training)
- `text` - Plain text only
- `json` - Structured JSON representation
- `extracted_data` - AI-extracted structured data
- `page_metadata` - Page metadata (title, description, etc.)
 
 

- `content_formats=["html"]`
- `content_formats=["markdown"]`  LLM Ready
- `content_formats=["markdown", "extracted_data"]`
- `content_formats=["html", "text", "page_metadata"]`
 
 

 

 [max\_duration](#api_param_max_duration)    

 default: 900 (15 minutes) 

 

 Maximum crawl duration in seconds. Range: **15-10800 seconds (15s to 3 hours)**. The crawler will stop after this time limit is reached, even if there are more pages to crawl. Use this to prevent long-running crawls. 

- `max_duration=900`
- `max_duration=3600`
- `max_duration=10800`
 
 

 

 [max\_api\_credit](#api_param_max_api_credit)    

 default: 0 (no limit) 

 

 Maximum API credits to spend on this crawl. Must be non-negative. The crawler will stop when this credit limit is reached. Set to `0` for no credit limit. Useful for controlling costs on large crawls. 

- `max_api_credit=1000`
- `max_api_credit=5000`
- `max_api_credit=0` (no limit)
 
 

 

 [extraction\_rules](#api_param_extraction_rules)    

 default: null 

 

 Extraction rules to extract structured data from each page. **Maximum 100 rules.** Each rule maps a URL pattern (max 1000 chars) to an extraction config with type and value. 

 **Supported types:**- `prompt` - AI extraction prompt (max 10000 chars)
- `model` - Pre-defined extraction model
- `template` - Extraction template (name or JSON)
 
  **Comprehensive Guide:** See the [Extraction Rules documentation](https://scrapfly.home/docs/crawler-api/extraction-rules) for detailed examples, pattern matching rules, and best practices. 

 

 `extraction_rules={"/products/*": {"type": "prompt", "value": "Extract product details"}}` `extraction_rules={"/blog/*": {"type": "model", "value": "article"}}` 

 

 [webhook\_name](#api_param_webhook_name)    

popular

 default: null 

 

 **Name reference** to a webhook configured in your [dashboard](https://scrapfly.home/dashboard/webhook). This is **NOT a URL** - it is the name you assigned when creating the webhook. 

 **Two-step process:**1. **Create webhook in dashboard** - Configure URL, authentication, and events
2. **Reference by name** - Use the webhook name in your API call
 
 The webhook must exist in the same project and environment as your crawler. The webhook name is converted to lowercase. 

 `webhook_name=my-crawler-webhook` (references a webhook named "my-crawler-webhook") 

 

 [webhook\_events](#api_param_webhook_events)    

 basic events if webhook_name provided 

 

 List of webhook events to subscribe to. If webhook name is provided but events list is empty, defaults to basic events: `crawler_started`, `crawler_stopped`, `crawler_cancelled`, `crawler_finished`. 

 **Available events:**- `crawler_started` - Crawler job started
- `crawler_url_visited` - Individual URL successfully crawled
- `crawler_url_skipped` - URL skipped (already crawled, excluded, etc.)
- `crawler_url_discovered` - New URL discovered
- `crawler_url_failed` - URL crawl failed
- `crawler_stopped` - Crawler job stopped
- `crawler_cancelled` - Crawler job cancelled
- `crawler_finished` - Crawler job finished
 
 

- `webhook_events=["crawler_finished"]`
- `webhook_events=["crawler_started", "crawler_finished"]`
- `webhook_events=["crawler_url_visited", "crawler_url_failed"]`
 
 

 

 [proxy\_pool](#api_param_proxy_pool)    

popular

 public_datacenter_pool 

 

 Select the proxy pool. A proxy pool is a network of proxies grouped by quality range and network type. The price varies based on the pool used. See [proxy dashboard](https://scrapfly.home/dashboard/proxy) for available pools. 

- `proxy_pool=public_datacenter_pool`
- `proxy_pool=public_residential_pool`
 
 

 

 [country](#api_param_country)    

popular

 default: random 

 

 Proxy country location in ISO 3166-1 alpha-2 (2 letters) country codes. The available countries are listed on your [proxy dashboard](https://scrapfly.home/dashboard/proxy). Supports exclusions (minus prefix) and weighted distribution (colon suffix with weight 0-255). 

- `country=us`
- `country=us,ca,mx` (random distribution)
- `country=us:10,gb:5` (weighted, 0-255)
- `country=-gb` (exclude GB)
 
 

 

 [asp](#api_param_asp)    

 popular

 default: false 

 

 [Anti Scraping Protection](https://scrapfly.home/docs/scrape-api/anti-scraping-protection) - Enable advanced anti-bot bypass features including browser rendering, fingerprinting, and automatic retry with upgraded configurations. When enabled, the crawler will automatically use headless browsers and adapt to bypass protections. 

 Note When ASP is enabled, any custom `user_agent` parameter is ignored. ASP manages User-Agent headers automatically for optimal bypass performance. 

- `asp=true`
- `asp=false`
 
 

 

 

 

## Get Crawler Status  

 Retrieve the current status and progress of a crawler job. Use this endpoint to poll for updates while the crawler is running.

 GET `https://api.scrapfly.home/crawl/{uuid}/status` 

 ```
curl "https://api.scrapfly.home/crawl/{uuid}/status?key=scp-live-d8ac176c2f9d48b993b58675bdf71615"
```

 

   

 

 

 

 **Response includes:**

- `status` - Current status (PENDING, RUNNING, COMPLETED, FAILED, CANCELLED)
- `state.urls_discovered` - Total URLs discovered
- `state.urls_crawled` - URLs successfully crawled
- `state.urls_pending` - URLs waiting to be crawled
- `state.urls_failed` - URLs that failed to crawl
- `state.api_credits_used` - Total API credits consumed
 
## Get Crawled URLs  

 Retrieve a list of all URLs discovered and crawled during the job, with metadata about each URL.

 GET `https://api.scrapfly.home/crawl/{uuid}/urls` 

 ```
# Get all visited URLs
curl "https://api.scrapfly.home/crawl/{uuid}/urls?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&status=visited"

# Get failed URLs with pagination
curl "https://api.scrapfly.home/crawl/{uuid}/urls?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&status=failed&page=1&per_page=100"
```

 

   

 

 

 

 **Query Parameters:**

- `key` - Your API key (required)
- `status` - Filter by URL status: `visited`, `pending`, `failed`
- `page` - Page number for pagination (default: 1)
- `per_page` - Results per page (default: 100, max: 1000)
 
## Get Content  

 Retrieve extracted content from crawled pages in the format(s) specified in your crawl configuration.

### Single URL or All Pages (GET)

 GET `https://api.scrapfly.home/crawl/{uuid}/contents` 

 ```
# Get all content in markdown format
curl "https://api.scrapfly.home/crawl/{uuid}/contents?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&format=markdown"

# Get content for a specific URL
curl "https://api.scrapfly.home/crawl/{uuid}/contents?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&format=html&url=https://example.com/page"
```

 

   

 

 

 

 **Query Parameters:**

- `key` - Your API key (required)
- `format` - Content format to retrieve (must be one of the formats specified in crawl config)
- `url` - Optional: Retrieve content for a specific URL only
 
### Batch Content Retrieval (POST)

 POST `https://api.scrapfly.home/crawl/{uuid}/contents/batch` 

 Retrieve content for multiple specific URLs in a single request. More efficient than making individual GET requests for each URL. **Maximum 100 URLs per request.**

 ```
# Batch retrieve content for multiple URLs
curl -X POST "https://api.scrapfly.home/crawl/{uuid}/contents/batch?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&formats=markdown,text" \
  -H "Content-Type: text/plain" \
  -d "https://example.com/page1
https://example.com/page2
https://example.com/page3"
```

 

   

 

 

 

 **Query Parameters:**

- `key` - Your API key (required)
- `formats` - Comma-separated list of formats (e.g., `markdown,text,html`)
 
 **Request Body:**

- `Content-Type: text/plain` - Plain text with URLs separated by newlines
- **Maximum 100 URLs per request**
 
 **Response Format:**

- `Content-Type: multipart/related` - Standard HTTP multipart format (RFC 2387)
- `X-Scrapfly-Requested-URLs` header - Number of URLs in the request
- `X-Scrapfly-Found-URLs` header - Number of URLs found in the crawl results
- Each part contains `Content-Type` and `Content-Location` headers identifying the format and URL
 
  **Efficient Streaming Format** The multipart format eliminates JSON escaping overhead, providing **~50% bandwidth savings** for text content and constant memory usage during streaming. See the [Results documentation](https://scrapfly.home/docs/crawler-api/results#query-content) for parsing examples in Python, JavaScript, and Go.

 

## Download Artifact  

 Download industry-standard archive files containing all crawled data, including HTTP requests, responses, headers, and extracted content. Perfect for storing bulk crawl results offline or in object storage (S3, Google Cloud Storage).

 GET `https://api.scrapfly.home/crawl/{uuid}/artifact` 

 ```
# Download WARC artifact (gzip compressed, recommended for large crawls)
curl "https://api.scrapfly.home/crawl/{uuid}/artifact?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&type=warc" -o crawl.warc.gz

# Download HAR artifact (JSON format)
curl "https://api.scrapfly.home/crawl/{uuid}/artifact?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&type=har" -o crawl.har
```

 

   

 

 

 

 **Query Parameters:**

- `key` - Your API key (required)
- `type` - Artifact type: 
    - `warc` - Web ARChive format (gzip compressed, industry standard)
    - `har` - HTTP Archive format (JSON, browser-compatible)
 
## Billing  

 Crawler API billing is simple: **the cost equals the sum of all Web Scraping API calls** made during the crawl. Each page crawled consumes credits based on enabled features (browser rendering, anti-scraping protection, proxy type, etc.).

 For detailed billing information, see [Crawler API Billing](https://scrapfly.home/docs/crawler-api/billing).

 # Retrieving Crawler Results

 Once your crawler has completed, you have multiple options for retrieving the results. Choose the method that best fits your use case: individual URLs, content queries, or complete artifacts.

  **Near-Realtime Results** Results become available in **near-realtime** as pages are crawled. You can query content immediately while the crawler is `RUNNING`. Artifacts (WARC/HAR) are only finalized when `is_finished: true`. Poll the `/crawl/{uuid}/status` endpoint to monitor progress and check `is_success` to determine the outcome.

 

## Choosing the Right Method

 Select the retrieval method that best matches your use case. Consider your crawl size, processing needs, and infrastructure.

 

   

##### List URLs

  **Best for:**

- URL discovery & mapping
- Failed URL analysis
- Sitemap generation
- Crawl auditing
 
  **Scale:** Any size

 

 

 

   

##### Query Specific

  **Best for:**

- Selective retrieval
- Real-time processing
- On-demand access
- API integration
 
  **Scale:** Any size (per-page)

 

 

 

   

##### Get All Content

  **Best for:**

- Small crawls
- Testing & development
- Quick prototyping
- Simple integration
 
  **Scale:** Best for <100 pages

 

 

 

   Recommended 

##### Download Artifacts

  **Best for:**

- Large crawls (100s-1000s+)
- Long-term archival
- Offline processing
- Data pipelines
 
  **Scale:** Unlimited

 

 

 

 

 

## Retrieval Methods  

 The Crawler API provides four complementary methods for accessing your crawled data. Choose the method that best fits your use case:

    List URLs URL metadata    Query Specific Single page content    Get All Content All pages via API    Download Artifacts WARC/HAR files Recommended   

 ###   List Crawled URLs

 Get a comprehensive list of all URLs discovered and crawled during the job, with detailed metadata for each URL including status codes, depth, and timestamps.

 ```
curl https://api.scrapfly.home/crawl/{uuid}/urls?key=scp-live-d8ac176c2f9d48b993b58675bdf71615
```

 

   

 

 

 

 **Filter by status:**

 ```
# Get all visited URLs
curl https://api.scrapfly.home/crawl/{uuid}/urls?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&status=visited

# Get all failed URLs
curl https://api.scrapfly.home/crawl/{uuid}/urls?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&status=failed
```

 

   

 

 

 

Response includes URL metadata:

 ```
{
  "urls": [
    {
      "url": "https://example.com",
      "status": "visited",
      "depth": 0,
      "status_code": 200,
      "crawled_at": "2025-01-15T10:30:20Z"
    },
    {
      "url": "https://example.com/about",
      "status": "visited",
      "depth": 1,
      "status_code": 200,
      "crawled_at": "2025-01-15T10:30:45Z"
    }
  ],
  "total": 847,
  "page": 1,
  "per_page": 100
}
```

 

   

 

 

 

 **Use case:** Audit which pages were crawled, identify failed URLs, or build a sitemap.

  **HTTP Caching Optimization** For completed crawlers (`is_finished: true`), all retrieval endpoints return `Cache-Control: public, max-age=3600, immutable` headers. This enables:

- **Browser caching:** Automatically cache responses for 1 hour
- **CDN acceleration:** Content can be cached by intermediate proxies
- **Reduced API calls:** Repeat requests served from cache without counting against limits
- **Immutable guarantee:** Content won't change, safe to cache aggressively
 
 

 

###   Query Specific Page Content

 Retrieve extracted content for specific URLs from the crawl. Perfect for selective content retrieval without downloading the entire dataset.

#### Single URL Query

Retrieve content for one specific URL using the `url` query parameter:

 ```
curl https://api.scrapfly.home/crawl/{uuid}/contents?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&url=https://example.com/page&format=markdown
```

 

   

 

 

 

Response contains the extracted content for the specified URL:

 ```
# Homepage

Welcome to our site! We provide the best products and services for your needs.

## Our Services

- Web Development
- Mobile Apps
- Cloud Solutions

Contact us today to get started!
```

 

   

 

 

 

##### Plain Mode Efficient

Return raw content directly without JSON wrapper by adding `plain=true`. Perfect for shell scripts and direct file piping:

 ```
# Get raw markdown content (no JSON wrapper)
curl https://api.scrapfly.home/crawl/{uuid}/contents?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&url=https://example.com&formats=markdown&plain=true

# Direct output - pure markdown, no JSON parsing needed:
# Homepage
#
# Welcome to our site...

# Pipe directly to file
curl https://api.scrapfly.home/crawl/{uuid}/contents?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&url=https://example.com&formats=markdown&plain=true > page.md
```

 

   

 

 

 

  **Plain Mode Requirements**- Must specify `url` parameter (single URL only)
- Must specify exactly one format in `formats` parameter
- Response Content-Type matches format (e.g., `text/markdown`, `text/html`)
- No JSON parsing needed - raw content in response body
 
 

##### Multipart Response Format

Request a multipart response for single URLs by setting the `Accept` header. Same efficiency benefits as batch queries:

 ```
# Request multipart format for single URL
curl "https://api.scrapfly.home/crawl/{uuid}/contents?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&url=https://example.com&formats=markdown,text" \
  -H "Accept: multipart/related; boundary=custom123"
```

 

   

 

 

 

Response returns multiple formats for the same URL as separate parts:

 ```
HTTP/1.1 200 OK
Content-Type: multipart/related; boundary=custom123
Content-Location: https://example.com

--custom123
Content-Type: text/markdown

# Homepage

Welcome to our site...
--custom123
Content-Type: text/plain

Homepage

Welcome to our site...
--custom123--
```

 

   

 

 

 

  **Use Cases for Single URL Multipart**- **Multiple formats efficiently:** Get markdown + text + HTML for the same URL without JSON escaping overhead
- **Streaming processing:** Process formats as they arrive in the multipart stream
- **Bandwidth savings:** ~50% smaller than JSON for text content due to no escaping
 
 

#### Batch URL Query Efficient

Retrieve content for multiple URLs in a single request. Maximum **100 URLs per request**.

 ```
curl -X POST "https://api.scrapfly.home/crawl/{uuid}/contents/batch?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&formats=markdown,text" \
  -H "Content-Type: text/plain" \
  -d "https://example.com/page1
https://example.com/page2
https://example.com/page3"
```

 

   

 

 

 

**Response format:** `multipart/related` (RFC 2387) - Each URL's content is returned as a separate part in the multipart response.

 ```
HTTP/1.1 200 OK
Content-Type: multipart/related; boundary=abc123
X-Scrapfly-Requested-URLs: 3
X-Scrapfly-Found-URLs: 3

--abc123
Content-Type: text/markdown
Content-Location: https://example.com/page1

# Page 1

Content here...
--abc123
Content-Type: text/plain
Content-Location: https://example.com/page1

Page 1 Content here...
--abc123
Content-Type: text/markdown
Content-Location: https://example.com/page2

# Page 2

Different content...
--abc123--
```

 

   

 

 

 

  **Performance & Efficiency** The multipart format provides **~50% bandwidth savings** compared to JSON for text content by eliminating JSON escaping overhead. The response streams efficiently with constant memory usage, making it ideal for large content batches.

 

##### Parsing Multipart Responses

Use standard HTTP multipart libraries to parse the response:

    Python    JavaScript    Go  

  ```
from email import message_from_bytes
from email.policy import HTTP
import requests

response = requests.post(
    f"https://api.scrapfly.home/crawl/{uuid}/contents/batch",
    params={"key": api_key, "formats": "markdown,text"},
    headers={"Content-Type": "text/plain"},
    data="https://example.com/page1\nhttps://example.com/page2"
)

# Parse multipart response
msg = message_from_bytes(
    f"Content-Type: {response.headers['Content-Type']}\r\n\r\n".encode() + response.content,
    policy=HTTP
)

# Iterate through parts
for part in msg.iter_parts():
    url = part['Content-Location']
    content_type = part['Content-Type']
    content = part.get_content()

    print(f"{url} ({content_type}): {len(content)} bytes")

    # Store content by URL and format
    if content_type == "text/markdown":
        save_markdown(url, content)
    elif content_type == "text/plain":
        save_text(url, content)
```

 

   

 

 

 

 

 ```
// Node.js with node-fetch and mailparser
import fetch from 'node-fetch';
import { simpleParser } from 'mailparser';

const response = await fetch(
    `https://api.scrapfly.home/crawl/{uuid}/contents/batch?key=${apiKey}&formats=markdown,text`,
    {
        method: 'POST',
        headers: { 'Content-Type': 'text/plain' },
        body: 'https://example.com/page1\nhttps://example.com/page2'
    }
);

const contentType = response.headers.get('content-type');
const buffer = await response.buffer();

// Parse multipart
const parsed = await simpleParser(
    `Content-Type: ${contentType}\r\n\r\n${buffer.toString('binary')}`
);

// Process each attachment (part)
for (const attachment of parsed.attachments) {
    const url = attachment.headers.get('content-location');
    const contentType = attachment.contentType;
    const content = attachment.content.toString();

    console.log(`${url} (${contentType}): ${content.length} bytes`);
}
```

 

   

 

 

 

 

 ```
package main

import (
    "io"
    "mime"
    "mime/multipart"
    "net/http"
    "strings"
)

func fetchBatchContents(crawlerUUID, apiKey string, urls []string) error {
    body := strings.Join(urls, "\n")

    resp, err := http.Post(
        "https://api.scrapfly.home/crawl/" + crawlerUUID + "/contents/batch?key=" + apiKey + "&formats=markdown,text",
        "text/plain",
        strings.NewReader(body),
    )
    if err != nil {
        return err
    }
    defer resp.Body.Close()

    // Parse multipart boundary
    mediaType, params, err := mime.ParseMediaType(resp.Header.Get("Content-Type"))
    if err != nil || !strings.HasPrefix(mediaType, "multipart/") {
        return err
    }

    // Read multipart parts
    mr := multipart.NewReader(resp.Body, params["boundary"])
    for {
        part, err := mr.NextPart()
        if err == io.EOF {
            break
        }
        if err != nil {
            return err
        }

        url := part.Header.Get("Content-Location")
        contentType := part.Header.Get("Content-Type")
        content, _ := io.ReadAll(part)

        // Process content
        println(url, contentType, len(content), "bytes")
    }

    return nil
}
```

 

   

 

 

 

 

 

#### Batch Query Parameters

 | Parameter | Type | Description |
|---|---|---|
| `key` | Query Param | Your API key (required) |
| `formats` | Query Param | Comma-separated list of formats for batch query (e.g., `markdown,text,html`) |
| Request Body | Plain Text | URLs separated by newlines (for batch query, max 100 URLs) |

##### Response Headers

 | Header | Description |
|---|---|
| `Content-Type` | `multipart/related; boundary=` - Standard HTTP multipart format (RFC 2387) |
| `X-Scrapfly-Requested-URLs` | Number of URLs in your request |
| `X-Scrapfly-Found-URLs` | Number of URLs found in crawl results (may be less if some URLs were not crawled) |

##### Multipart Part Headers

Each part in the multipart response contains:

 | Header | Description |
|---|---|
| `Content-Type` | MIME type of the content (e.g., `text/markdown`, `text/plain`, `text/html`) |
| `Content-Location` | The URL this content belongs to |

 **Available formats:**

- `html` - Raw HTML content
- `clean_html` - HTML with boilerplate removed
- `markdown` - Markdown format (ideal for LLM training data)
- `text` - Plain text only
- `json` - Structured JSON representation
- `extracted_data` - AI-extracted structured data
- `page_metadata` - Page metadata (title, description, etc.)
 
 **Use cases:**

- **Single query:** Fetch content for individual pages via API for real-time processing
- **Batch query:** Efficiently retrieve content for multiple specific URLs (e.g., product pages, article URLs)
 
 

###   Get All Crawled Contents

 Retrieve all extracted contents in the specified format. Returns a JSON object mapping URLs to their extracted content in your chosen format.

 ```
curl https://api.scrapfly.home/crawl/{uuid}/contents?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&format=markdown
```

 

   

 

 

 

Response contains contents mapped by URL:

 ```
{
  "contents": {
    "https://example.com": "# Homepage\n\nWelcome to our site...",
    "https://example.com/about": "# About Us\n\nWe are a company...",
    "https://example.com/contact": "# Contact\n\nReach us at..."
  }
}
```

 

   

 

 

 

 **Available formats:**

- `html` - Raw HTML content
- `clean_html` - HTML with boilerplate removed
- `markdown` - Markdown format (ideal for LLM training data)
- `text` - Plain text only
- `json` - Structured JSON representation
- `extracted_data` - AI-extracted structured data
- `page_metadata` - Page metadata (title, description, etc.)
 
  **Large Crawls** For crawls with hundreds or thousands of pages, this endpoint may return large responses. Consider using artifacts or querying specific URLs instead.

 

 **Use case:** Small to medium crawls where you need all content via API, or testing/development.

 

###   Download Artifacts (Recommended for Large Crawls)

 Download industry-standard archive formats containing all crawled data. This is the **most efficient method** for large crawls, avoiding multiple API calls and handling huge datasets with ease.

#### Why Use Artifacts?

- **Massive Scale** - Handle crawls with thousands or millions of pages efficiently
- **Single Download** - Get the entire crawl in one compressed file, avoiding pagination and rate limits
- **Offline Processing** - Query and analyze data locally without additional API calls
- **Cost Effective** - One-time download instead of per-page API requests
- **Flexible Storage** - Store artifacts in S3, object storage, or local disk for long-term archival
- **Industry Standard** - WARC and HAR formats are universally supported by analysis tools
 
#### Available Artifact Types

##### WARC (Web ARChive Format)

 Industry-standard format for web archiving. Contains complete HTTP request/response pairs, headers, and extracted content. Compressed with gzip for efficient storage.

 ```
curl https://api.scrapfly.home/crawl/{uuid}/artifact?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&type=warc -o crawl.warc.gz
```

 

   

 

 

 

 **Use case:** Long-term archival, offline analysis with standard tools, research datasets.

  **Learn More About WARC Format** See our [complete WARC format guide](https://scrapfly.home/docs/crawler-api/warc-format) for custom headers, reading libraries in multiple languages, and code examples.

 

##### HAR (HTTP Archive Format)

 JSON-based format with detailed HTTP transaction data. Ideal for performance analysis, debugging, and browser replay tools.

 ```
curl https://api.scrapfly.home/crawl/{uuid}/artifact?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&type=har -o crawl.har
```

 

   

 

 

 

 **Use case:** Performance analysis, browser DevTools import, debugging HTTP transactions.

 

  

 ## Complete Retrieval Workflow

 Here's a complete example showing how to wait for completion and retrieve results:

    Bash Shell script    Python Using requests    JavaScript Using fetch API  

  ```
#!/bin/bash

# Step 1: Create crawler
RESPONSE=$(curl -X POST https://api.scrapfly.home/crawl?key=scp-live-d8ac176c2f9d48b993b58675bdf71615 \
  -H 'Content-Type: application/json' \
  -d '{
    "url": "https://web-scraping.dev/products",
    "page_limit": 25
  }')

# Extract crawler UUID
UUID=$(echo $RESPONSE | jq -r '.crawler_uuid')
echo "Crawler UUID: $UUID"

# Step 2: Poll status until complete
while true; do
  RESPONSE=$(curl -s https://api.scrapfly.home/crawl/$UUID/status?key=scp-live-d8ac176c2f9d48b993b58675bdf71615)
  IS_FINISHED=$(echo $RESPONSE | jq -r '.is_finished')
  IS_SUCCESS=$(echo $RESPONSE | jq -r '.is_success')

  echo "Status check: is_finished=$IS_FINISHED, is_success=$IS_SUCCESS"

  if [ "$IS_FINISHED" = "true" ]; then
    if [ "$IS_SUCCESS" = "true" ]; then
      echo "Crawler completed successfully!"
      break
    else
      echo "Crawler failed!"
      exit 1
    fi
  fi

  sleep 5
done

# Step 3: Download results
echo "Downloading WARC artifact..."
curl https://api.scrapfly.home/crawl/$UUID/artifact?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&type=warc -o crawl.warc.gz

echo "Getting markdown content..."
curl https://api.scrapfly.home/crawl/$UUID/contents?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&format=markdown > content.json

echo "Done!"
```

 

   

 

 

 

 

 ```
import requests
import time

API_KEY = "scp-live-d8ac176c2f9d48b993b58675bdf71615"
BASE_URL = "https://api.scrapfly.home"

# Step 1: Create crawler
response = requests.post(
    f"{BASE_URL}/crawl",
    params={"key": API_KEY},
    json={
        "url": "https://web-scraping.dev/products",
        "page_limit": 25
    }
)
crawler_data = response.json()
uuid = crawler_data["crawler_uuid"]
print(f"Crawler UUID: {uuid}")

# Step 2: Poll status until complete
while True:
    response = requests.get(
        f"{BASE_URL}/crawl/{uuid}/status",
        params={"key": API_KEY}
    )
    status = response.json()

    is_finished = status.get("is_finished", False)
    is_success = status.get("is_success", False)

    print(f"Status check: is_finished={is_finished}, is_success={is_success}")

    if is_finished:
        if is_success:
            print("Crawler completed successfully!")
            break
        else:
            print("Crawler failed!")
            exit(1)

    time.sleep(5)

# Step 3: Download results
print("Downloading WARC artifact...")
warc_response = requests.get(
    f"{BASE_URL}/crawl/{uuid}/artifact",
    params={"key": API_KEY, "type": "warc"}
)
with open("crawl.warc.gz", "wb") as f:
    f.write(warc_response.content)

print("Getting markdown content...")
content_response = requests.get(
    f"{BASE_URL}/crawl/{uuid}/contents",
    params={"key": API_KEY, "format": "markdown"}
)
with open("content.json", "w") as f:
    f.write(content_response.text)

print("Done!")
```

 

   

 

 

 

 

 ```
const API_KEY = "scp-live-d8ac176c2f9d48b993b58675bdf71615";
const BASE_URL = "https://api.scrapfly.home";

async function runCrawler() {
    // Step 1: Create crawler
    const createResponse = await fetch(`${BASE_URL}/crawl?key=${API_KEY}`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json"
        },
        body: JSON.stringify({
            url: "https://web-scraping.dev/products",
            page_limit: 25
        })
    });

    const crawlerData = await createResponse.json();
    const uuid = crawlerData.crawler_uuid;
    console.log(`Crawler UUID: ${uuid}`);

    // Step 2: Poll status until complete
    while (true) {
        const statusResponse = await fetch(
            `${BASE_URL}/crawl/${uuid}/status?key=${API_KEY}`
        );
        const status = await statusResponse.json();

        const isFinished = status.is_finished || false;
        const isSuccess = status.is_success || false;

        console.log(`Status check: is_finished=${isFinished}, is_success=${isSuccess}`);

        if (isFinished) {
            if (isSuccess) {
                console.log("Crawler completed successfully!");
                break;
            } else {
                console.log("Crawler failed!");
                process.exit(1);
            }
        }

        await new Promise(resolve => setTimeout(resolve, 5000));
    }

    // Step 3: Download results
    console.log("Downloading WARC artifact...");
    const warcResponse = await fetch(
        `${BASE_URL}/crawl/${uuid}/artifact?key=${API_KEY}&type=warc`
    );
    const warcBlob = await warcResponse.blob();
    // In Node.js, use fs.writeFileSync to save
    // In browser, use URL.createObjectURL to download

    console.log("Getting markdown content...");
    const contentResponse = await fetch(
        `${BASE_URL}/crawl/${uuid}/contents?key=${API_KEY}&format=markdown`
    );
    const content = await contentResponse.json();
    // Save content.json to file

    console.log("Done!");
}

runCrawler().catch(console.error);
```

 

   

 

 

 

 

 

## Next Steps

- Learn about [webhook integration](https://scrapfly.home/docs/crawler-api/webhook) for real-time notifications
- Understand [billing and costs](https://scrapfly.home/docs/crawler-api/billing)
- Review the [full API specification](https://scrapfly.home/docs/crawler-api/getting-started#spec)

# WARC Format Reference

 The WARC (Web ARChive) format is an industry-standard file format for archiving web content. Scrapfly Crawler API uses WARC files to provide you with complete, archival-quality snapshots of your crawled data.

  **Recommended for Large Crawls** WARC files are the **most efficient** way to retrieve and archive crawled data, especially for large crawls (100s-1000s+ pages). They provide complete HTTP transaction data in a compressed, industry-standard format that can be processed offline without additional API calls.

 

## What is WARC?

 WARC (Web ARChive) is an ISO standard (ISO 28500:2017) for archiving web content. It captures complete HTTP request/response pairs, including headers, status codes, and response bodies.

### Key Benefits

- **Complete Data** - Captures full HTTP transactions (request + response)
- **Industry Standard** - Universally supported by archival and analysis tools
- **Compressed Storage** - Gzip compression for efficient storage
- **Offline Processing** - Query and analyze data without API calls
- **Long-term Archival** - Format designed for preservation
- **Tool Ecosystem** - Many libraries and tools available
 
## WARC File Structure

 A WARC file contains a series of **records**. Each record has:

- **WARC Headers** - Metadata about the record (record type, IDs, timestamps)
- **HTTP Headers** - HTTP request or response headers (if applicable)
- **Payload** - The actual content (HTML, JSON, binary data, etc.)
 
### Record Types

 | Record Type | Description | Content |
|---|---|---|
| `warcinfo` | File metadata and crawl information | Crawler version, settings, timestamps |
| `request` | HTTP request sent to the server | Request method, URL, headers, body |
| `response` | HTTP response received from server | Status code, headers, response body (HTML, JSON, etc.) |
| `conversion` | Extracted/converted content | Markdown, text, or clean HTML extracted from response |

 

 

## Scrapfly Custom WARC Headers

 In addition to standard WARC headers, Scrapfly adds custom metadata to help you analyze and process your crawled data more effectively.

### Custom Headers for All Records

 | Header | Type | Description |
|---|---|---|
| `WARC-Scrape-Log-Id` | String | Unique identifier for the scraping log entry. Use this to: - Track individual page scrapes - Look up detailed logs in dashboard - Cross-reference with billing data |
| `WARC-Scrape-Country` | String (ISO 3166) | ISO 3166-1 alpha-2 country code of the proxy used (e.g., `US`, `GB`, `FR`). Useful for analyzing geo-specific content variations. |

 

 

### Custom Headers for Response Records

 | Header | Type | Description |
|---|---|---|
| `WARC-Scrape-Duration` | Float (seconds) | Time taken to complete the HTTP request in seconds (e.g., `1.234`). Useful for performance analysis and identifying slow pages. |
| `WARC-Scrape-Retry` | Integer | Number of retry attempts for this request (`0` means first attempt succeeded). Helps identify problematic URLs that required retries. |

 

 

### Example WARC Record with Custom Headers

 ```
WARC/1.0
WARC-Type: response
WARC-Record-ID: 
WARC-Date: 2025-01-15T10:30:45Z
WARC-Target-URI: https://web-scraping.dev/products/page/1
Content-Type: application/http; msgtype=response
Content-Length: 15234

# Custom Scrapfly Headers
WARC-Scrape-Log-Id: abcd1234-5678-90ef-ghij-klmnopqrstuv
WARC-Scrape-Country: US
WARC-Scrape-Duration: 1.234
WARC-Scrape-Retry: 0

HTTP/2.0 200 OK
Content-Type: text/html; charset=utf-8
Content-Length: 15000
Date: Wed, 15 Jan 2025 10:30:45 GMT



...
```

 

   

 

 

 

## Downloading WARC Files

 WARC files are available once your crawler completes (`is_finished: true`).

 ```
curl https://api.scrapfly.home/crawl/{uuid}/artifact?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&type=warc -o crawl.warc.gz
```

 

   

 

 

 

The file is returned as `crawl.warc.gz` (gzip-compressed for efficient transfer).

## Reading WARC Files

 WARC files can be read using various tools and libraries in different programming languages.

    Python    JavaScript    Java    Go    Rust    C++    PHP    CLI Tools  

 ### Python - warcio Library

 [warcio](https://github.com/webrecorder/warcio) is the recommended Python library for reading WARC files.

#### Installation

 ```
pip install warcio
```

 

   

 

 

 

#### Reading WARC Files

 ```
import gzip
from warcio.archiveiterator import ArchiveIterator

# Open and decompress WARC file
with gzip.open('crawl.warc.gz', 'rb') as warc_file:
    # Iterate through all records
    for record in ArchiveIterator(warc_file):
        # Get record type
        record_type = record.rec_type

        # Get WARC headers
        warc_headers = record.rec_headers

        # Access standard WARC headers
        record_id = warc_headers.get_header('WARC-Record-ID')
        target_uri = warc_headers.get_header('WARC-Target-URI')
        date = warc_headers.get_header('WARC-Date')

        # Access Scrapfly custom headers
        log_id = warc_headers.get_header('WARC-Scrape-Log-Id')
        country = warc_headers.get_header('WARC-Scrape-Country')
        duration = warc_headers.get_header('WARC-Scrape-Duration')
        retry = warc_headers.get_header('WARC-Scrape-Retry')

        # Read record content
        content = record.content_stream().read()

        # Process different record types
        if record_type == 'response':
            # Get HTTP status code
            http_headers = record.http_headers
            status = http_headers.get_statuscode()

            print(f"URL: {target_uri}")
            print(f"Status: {status}")
            print(f"Country: {country}")
            print(f"Duration: {duration}s")
            print(f"Log ID: {log_id}")
            print(f"Content length: {len(content)} bytes")
            print("---")

        elif record_type == 'conversion':
            # Extracted content (markdown, text, etc.)
            content_type = warc_headers.get_header('Content-Type')
            print(f"Conversion: {content_type}")
            print(f"Refers to: {warc_headers.get_header('WARC-Refers-To')}")

```

 

   

 

 

 

#### Filtering Specific Records

 ```
import gzip
from warcio.archiveiterator import ArchiveIterator

with gzip.open('crawl.warc.gz', 'rb') as warc_file:
    for record in ArchiveIterator(warc_file):
        # Only process successful responses
        if record.rec_type == 'response':
            status = record.http_headers.get_statuscode()

            if status == '200':
                url = record.rec_headers.get_header('WARC-Target-URI')
                content = record.content_stream().read()

                # Process successful page
                print(f"Processing: {url}")
                # ... your processing logic here

```

 

   

 

 

 

 

### JavaScript/Node.js - node-warc

 [node-warc](https://github.com/N0taN3rd/node-warc) provides WARC parsing for Node.js applications.

#### Installation

 ```
npm install node-warc
```

 

   

 

 

 

#### Reading WARC Files

 ```
const WARCStreamTransform = require('node-warc');
const fs = require('fs');
const zlib = require('zlib');

// Create gunzip and WARC parser streams
const gunzip = zlib.createGunzip();
const parser = new WARCStreamTransform();

// Read compressed WARC file
fs.createReadStream('crawl.warc.gz')
    .pipe(gunzip)
    .pipe(parser)
    .on('data', (record) => {
        const recordType = record.warcType;
        const targetURI = record.warcTargetURI;

        // Access custom Scrapfly headers
        const logId = record.warcHeader('WARC-Scrape-Log-Id');
        const country = record.warcHeader('WARC-Scrape-Country');
        const duration = record.warcHeader('WARC-Scrape-Duration');

        if (recordType === 'response') {
            console.log(`URL: ${targetURI}`);
            console.log(`Country: ${country}`);
            console.log(`Duration: ${duration}s`);

            // Access HTTP headers
            const statusCode = record.httpHeaders.statusCode;
            const contentType = record.httpHeaders.headers.get('content-type');

            // Get response body
            const content = record.content.toString('utf8');
        }
    })
    .on('end', () => {
        console.log('Finished reading WARC file');
    });

```

 

   

 

 

 

 

### Java - jwat

 [JWAT](https://github.com/netarchivesuite/jwat) is a Java library for reading and writing WARC files.

#### Maven Dependency

 ```

    org.jwat
    jwat-warc
    1.1.1

```

 

   

 

 

 

#### Reading WARC Files

 ```
import org.jwat.warc.*;
import java.io.*;
import java.util.zip.GZIPInputStream;

public class WarcReader {
    public static void main(String[] args) throws IOException {
        // Open compressed WARC file
        FileInputStream fis = new FileInputStream("crawl.warc.gz");
        GZIPInputStream gzis = new GZIPInputStream(fis);

        // Create WARC reader
        WarcReader reader = WarcReaderFactory.getReader(gzis);
        WarcRecord record;

        // Iterate through records
        while ((record = reader.getNextRecord()) != null) {
            // Get WARC headers
            WarcHeader header = record.header;
            String recordType = header.warcTypeStr;
            String targetUri = header.warcTargetUriStr;

            // Access custom Scrapfly headers
            String logId = header.getHeader("WARC-Scrape-Log-Id").value;
            String country = header.getHeader("WARC-Scrape-Country").value;

            if ("response".equals(recordType)) {
                // Get HTTP status
                HttpHeader httpHeader = record.getHttpHeader();
                String statusCode = httpHeader.statusCode;

                System.out.println("URL: " + targetUri);
                System.out.println("Status: " + statusCode);
                System.out.println("Country: " + country);
            }

            record.close();
        }

        reader.close();
    }
}
```

 

   

 

 

 

 

### Go - go-warc

 [gowarc](https://github.com/nlnwa/gowarc) is a Go library for reading and writing WARC files.

#### Installation

 ```
go get github.com/nlnwa/gowarc
```

 

   

 

 

 

#### Reading WARC Files

 ```
package main

import (
    "compress/gzip"
    "fmt"
    "github.com/nlnwa/gowarc"
    "os"
)

func main() {
    // Open compressed WARC file
    f, err := os.Open("crawl.warc.gz")
    if err != nil {
        panic(err)
    }
    defer f.close()

    // Decompress
    gz, err := gzip.NewReader(f)
    if err != nil {
        panic(err)
    }
    defer gz.Close()

    // Create WARC reader
    reader := gowarc.NewReader(gz)

    // Iterate through records
    for {
        record, err := reader.Next()
        if err != nil {
            break
        }

        // Get WARC headers
        recordType := record.Type()
        targetURI := record.WarcHeader().Get("WARC-Target-URI")

        // Access custom Scrapfly headers
        logID := record.WarcHeader().Get("WARC-Scrape-Log-Id")
        country := record.WarcHeader().Get("WARC-Scrape-Country")
        duration := record.WarcHeader().Get("WARC-Scrape-Duration")

        if recordType == gowarc.Response {
            fmt.Printf("URL: %s\n", targetURI)
            fmt.Printf("Country: %s\n", country)
            fmt.Printf("Duration: %ss\n", duration)
        }
    }
}
```

 

   

 

 

 

 

### Rust - warc\_parser

 [warc\_parser](https://github.com/commoncrawl/warc_parser) is a high-performance Rust library for reading WARC files, originally developed for Common Crawl.

#### Installation

 ```
# Add to Cargo.toml
[dependencies]
warc_parser = "2.0"
flate2 = "1.0"  # For gzip decompression
```

 

   

 

 

 

#### Reading WARC Files

 ```
use std::fs::File;
use std::io::{BufReader, Read};
use flate2::read::GzDecoder;
use warc_parser::{WarcReader, RecordType};

fn main() -> Result<(), Box> {
    // Open compressed WARC file
    let file = File::open("crawl.warc.gz")?;
    let gz = GzDecoder::new(file);
    let buf_reader = BufReader::new(gz);

    // Create WARC reader
    let mut warc_reader = WarcReader::new(buf_reader);

    // Iterate through records
    while let Some(record) = warc_reader.next_item()? {
        // Get WARC headers
        let headers = &record.warc_headers;

        // Access standard WARC headers
        let record_type = headers.get("WARC-Type");
        let target_uri = headers.get("WARC-Target-URI");
        let record_id = headers.get("WARC-Record-ID");

        // Access Scrapfly custom headers
        let log_id = headers.get("WARC-Scrape-Log-Id");
        let country = headers.get("WARC-Scrape-Country");
        let duration = headers.get("WARC-Scrape-Duration");
        let retry = headers.get("WARC-Scrape-Retry");

        // Read record body
        let body = record.body;

        // Process different record types
        if record_type == Some("response") {
            println!("URL: {:?}", target_uri);
            println!("Country: {:?}", country);
            println!("Duration: {:?}s", duration);
            println!("Log ID: {:?}", log_id);
            println!("Body size: {} bytes", body.len());
            println!("---");
        }
    }

    Ok(())
}
```

 

   

 

 

 

#### Performance Filtering

Rust\\'s performance makes it ideal for processing large WARC archives efficiently.

 ```
use std::fs::File;
use std::io::BufReader;
use flate2::read::GzDecoder;
use warc_parser::WarcReader;

fn main() -> Result<(), Box> {
    let file = File::open("crawl.warc.gz")?;
    let gz = GzDecoder::new(file);
    let buf_reader = BufReader::new(gz);
    let mut warc_reader = WarcReader::new(buf_reader);

    let mut success_count = 0;
    let mut error_count = 0;

    while let Some(record) = warc_reader.next_item()? {
        let headers = &record.warc_headers;

        if headers.get("WARC-Type") == Some("response") {
            // Parse HTTP status from body (simplified)
            let body_str = String::from_utf8_lossy(&record.body);

            if body_str.contains("HTTP/1.1 200") || body_str.contains("HTTP/2 200") {
                success_count += 1;

                // Process successful responses
                let url = headers.get("WARC-Target-URI").unwrap_or("");
                let country = headers.get("WARC-Scrape-Country").unwrap_or("unknown");

                println!("✓ {} (from {})", url, country);
            } else {
                error_count += 1;
            }
        }
    }

    println!("\nStats:");
    println!("  Successful: {}", success_count);
    println!("  Errors: {}", error_count);

    Ok(())
}
```

 

   

 

 

 

 

### C++ - warcpp

 [warcpp](https://github.com/pisa-engine/warcpp) is a single-header C++ parser for WARC files with modern error handling using std::variant.

#### Installation

 ```
git clone https://github.com/pisa-engine/warcpp.git
cd warcpp
mkdir build && cd build
cmake ..
make
```

 

   

 

 

 

#### Reading WARC Files

 ```
#include 
#include 
#include 
#include 

using warcpp::match;
using warcpp::Record;
using warcpp::Error;

int main() {
    // Open compressed WARC file
    std::ifstream file("crawl.warc.gz", std::ios::binary);

    // Process records with pattern matching
    while (file) {
        auto result = warcpp::read_subsequent_record(file);

        match(
            result,
            [](const Record& record) {
                // Access WARC headers
                auto warc_type = record.header("WARC-Type");
                auto target_uri = record.header("WARC-Target-URI");
                auto record_id = record.header("WARC-Record-ID");

                // Access Scrapfly custom headers
                auto log_id = record.header("WARC-Scrape-Log-Id");
                auto country = record.header("WARC-Scrape-Country");
                auto duration = record.header("WARC-Scrape-Duration");
                auto retry = record.header("WARC-Scrape-Retry");

                if (warc_type == "response") {
                    std::cout << "URL: " << target_uri << std::endl;
                    std::cout << "Country: " << country << std::endl;
                    std::cout << "Duration: " << duration << "s" << std::endl;
                    std::cout << "Log ID: " << log_id << std::endl;
                    std::cout << "Content length: " << record.content_length() << " bytes" << std::endl;
                    std::cout << "---" << std::endl;
                }
            },
            [](const Error& err) {
                // Handle parsing errors
                std::cerr << "Error reading record" << std::endl;
            }
        );
    }

    return 0;
}
```

 

   

 

 

 

#### Efficient Error Handling

warcpp uses std::variant for type-safe error handling without exceptions.

 ```
#include 
#include 

int main() {
    std::ifstream file("crawl.warc.gz", std::ios::binary);

    // Extract specific data with error handling
    auto size = match(
        warcpp::read_subsequent_record(file),
        [](const Record& rec) {
            // Successfully read record
            return rec.content_length();
        },
        [](const Error& err) {
            // Error occurred, return default
            return 0u;
        }
    );

    std::cout << "Record size: " << size << " bytes" << std::endl;
    return 0;
}
```

 

   

 

 

 

 

### PHP - Mixnode WARC Reader

 [mixnode-warcreader-php](https://github.com/Mixnode/mixnode-warcreader-php) provides native PHP support for reading WARC files, both raw and gzipped.

#### Installation

 ```
composer require mixnode/mixnode-warcreader-php
```

 

   

 

 

 

#### Reading WARC Files

 ```
nextRecord()) !== FALSE) {
    // Access WARC headers
    $headers = $record['header'];
    $content = $record['content'];

    // Get standard WARC fields
    $warc_type = $headers['WARC-Type'] ?? null;
    $target_uri = $headers['WARC-Target-URI'] ?? null;
    $record_id = $headers['WARC-Record-ID'] ?? null;

    // Access Scrapfly custom headers
    $log_id = $headers['WARC-Scrape-Log-Id'] ?? null;
    $country = $headers['WARC-Scrape-Country'] ?? null;
    $duration = $headers['WARC-Scrape-Duration'] ?? null;
    $retry = $headers['WARC-Scrape-Retry'] ?? null;

    // Process response records
    if ($warc_type === 'response') {
        echo "URL: $target_uri\n";
        echo "Country: $country\n";
        echo "Duration: {$duration}s\n";
        echo "Log ID: $log_id\n";
        echo "Content size: " . strlen($content) . " bytes\n";
        echo "---\n";
    }
}
```

 

   

 

 

 

#### Filtering Specific Records

 ```
nextRecord()) !== FALSE) {
    $headers = $record['header'];
    $content = $record['content'];

    // Only process responses
    if (($headers['WARC-Type'] ?? null) === 'response') {
        // Check HTTP status in content
        if (preg_match('/^HTTP\/[12](?:\.[01])? (\d{3})/', $content, $matches)) {
            $status_code = (int)$matches[1];

            if ($status_code === 200) {
                $successful_urls[] = [
                    'url' => $headers['WARC-Target-URI'] ?? null,
                    'country' => $headers['WARC-Scrape-Country'] ?? null,
                    'duration' => $headers['WARC-Scrape-Duration'] ?? null,
                ];
            } else {
                $error_count++;
            }
        }
    }
}

echo "Found " . count($successful_urls) . " successful requests\n";
echo "Errors: $error_count\n";

// Process successful URLs
foreach ($successful_urls as $url_data) {
    echo "✓ {$url_data['url']} (from {$url_data['country']})\n";
}
```

 

   

 

 

 

 

### Command-Line Tools

#### warcio (Python CLI)

Extract and inspect WARC files from the command line.

 ```
# Install warcio
pip install warcio

# List all records
warcio index crawl.warc.gz

# Extract all HTML responses
warcio extract --type response crawl.warc.gz > responses.txt

# Filter by URL pattern
warcio index crawl.warc.gz | grep "products"

```

 

   

 

 

 

#### zgrep - Search Compressed WARC

Search for specific content without decompressing.

 ```
# Search for specific URL
zgrep "WARC-Target-URI: https://example.com" crawl.warc.gz

# Search for specific log ID
zgrep "WARC-Scrape-Log-Id: abc123" crawl.warc.gz

# Search for requests from specific country
zgrep "WARC-Scrape-Country: US" crawl.warc.gz

```

 

   

 

 

 

#### gunzip - Decompress WARC

 ```
# Decompress WARC file
gunzip crawl.warc.gz

# Now you have crawl.warc (uncompressed)
# Can use standard text tools like grep, awk, etc.
grep "WARC-Type: response" crawl.warc

```

 

   

 

 

 

 

 

## Common Use Cases

#####   Long-term Archival 

 Store complete snapshots of websites for historical preservation, compliance, or research purposes using an industry-standard format.

 

 

 

#####   Offline Analysis 

 Download once and analyze locally without additional API calls. Perfect for data science, ML training sets, or bulk processing.

 

 

 

#####   Performance Monitoring 

 Use `WARC-Scrape-Duration` and `WARC-Scrape-Retry` to identify slow pages, analyze performance patterns, and optimize crawling strategies.

 

 

 

#####   Geo-specific Analysis 

 Compare content variations across regions using `WARC-Scrape-Country`. Analyze geo-blocking, localized pricing, or regional content differences.

 

 

 

 

## Converting WARC to Parquet

 Convert WARC archives to Apache Parquet format for efficient querying, analytics, and long-term storage. Parquet's columnar format with bloom filter indexing enables lightning-fast URL lookups and SQL-based analysis.

#####   Why Parquet?

- **Columnar storage**: Query only the columns you need (URL, status, country) without reading entire records
- **Bloom filters**: O(1) URL lookups instead of scanning entire archives
- **Compression**: 5-10x better compression than gzipped WARC
- **SQL queries**: Use DuckDB, ClickHouse, or Spark for complex analysis
- **Schema evolution**: Add new columns without rewriting data
 
 

### Python Implementation with Bloom Filters

 This example converts WARC to Parquet with bloom filter indexing on URLs for fast lookups.

#### Installation

 ```
pip install warcio pyarrow pandas
```

 

   

 

 

 

#### Conversion Script

 ```
import gzip
import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from warcio.archiveiterator import ArchiveIterator
from datetime import datetime

def warc_to_parquet(warc_path, parquet_path):
    """
    Convert WARC to Parquet with bloom filter on URL column.

    Bloom filters enable O(1) URL lookups - perfect for checking
    if a specific URL exists without reading the entire file.
    """
    records = []

    with gzip.open(warc_path, 'rb') as warc_file:
        for record in ArchiveIterator(warc_file):
            # Only process response records
            if record.rec_type != 'response':
                continue

            headers = record.rec_headers
            http_headers = record.http_headers

            # Extract data into columnar format
            row = {
                # Standard WARC fields
                'url': headers.get_header('WARC-Target-URI'),
                'record_id': headers.get_header('WARC-Record-ID'),
                'date': headers.get_header('WARC-Date'),

                # HTTP response data
                'status_code': int(http_headers.get_statuscode()) if http_headers else None,
                'content_type': http_headers.get_header('Content-Type') if http_headers else None,
                'content_length': len(record.content_stream().read()),

                # Scrapfly custom headers
                'log_id': headers.get_header('WARC-Scrape-Log-Id'),
                'country': headers.get_header('WARC-Scrape-Country'),
                'duration': float(headers.get_header('WARC-Scrape-Duration', 0)),
                'retry_count': int(headers.get_header('WARC-Scrape-Retry', 0)),
            }

            records.append(row)

    # Convert to DataFrame
    df = pd.DataFrame(records)

    # Define schema with optimized types
    schema = pa.schema([
        ('url', pa.string()),
        ('record_id', pa.string()),
        ('date', pa.timestamp('us')),
        ('status_code', pa.int16()),  # Smaller int for status codes
        ('content_type', pa.string()),
        ('content_length', pa.int32()),
        ('log_id', pa.string()),
        ('country', pa.string()),
        ('duration', pa.float32()),  # 32-bit sufficient for duration
        ('retry_count', pa.int8()),   # Very small int
    ])

    # Convert DataFrame to PyArrow Table
    table = pa.Table.from_pandas(df, schema=schema)

    # Write Parquet with bloom filter on URL column
    pq.write_table(
        table,
        parquet_path,
        compression='zstd',  # Better compression than gzip
        compression_level=9,
        # Enable bloom filter for O(1) URL lookups
        bloom_filter_columns=['url'],
        # Enable statistics for query optimization
        write_statistics=True,
        # Row group size affects query performance
        row_group_size=100000,
    )

    print(f"Converted {len(records)} records to {parquet_path}")
    print(f"Bloom filter enabled on 'url' column for fast lookups")

# Usage
warc_to_parquet('crawl.warc.gz', 'crawl.parquet')

```

 

   

 

 

 

#### Querying Parquet with DuckDB

 Once converted to Parquet, you can query your crawl data with SQL. Bloom filters make URL lookups instant, even on multi-GB files.

 ```
import duckdb

# Connect to DuckDB (in-memory)
con = duckdb.connect()

# Fast URL lookup using bloom filter
result = con.execute("""
    SELECT url, status_code, country, duration
    FROM read_parquet('crawl.parquet')
    WHERE url = 'https://web-scraping.dev/products/1'
""").fetchall()

print("Exact URL match:", result)

# Analytics queries - leveraging columnar format
stats = con.execute("""
    SELECT
        country,
        COUNT(*) as total_requests,
        AVG(duration) as avg_duration,
        COUNT(CASE WHEN status_code = 200 THEN 1 END) as success_count
    FROM read_parquet('crawl.parquet')
    GROUP BY country
    ORDER BY total_requests DESC
""").df()

print("\nStats by country:")
print(stats)

# Find slow requests (queries are FAST thanks to columnar format)
slow_requests = con.execute("""
    SELECT url, duration, retry_count, country
    FROM read_parquet('crawl.parquet')
    WHERE duration > 5.0
    ORDER BY duration DESC
    LIMIT 10
""").df()

print("\nSlowest requests:")
print(slow_requests)

```

 

   

 

 

 

#### Partitioning for Large Crawls

 For crawls with millions of URLs, partition by date or country for even faster queries.

 ```
import pyarrow.dataset as ds

# Write partitioned dataset (by country and date)
df['date'] = pd.to_datetime(df['date'])
df['partition_date'] = df['date'].dt.date

# Convert to PyArrow table
table = pa.Table.from_pandas(df)

# Write partitioned dataset
ds.write_dataset(
    table,
    'crawl_partitioned/',
    format='parquet',
    partitioning=['country', 'partition_date'],
    # Bloom filters on each partition
    parquet_writer_kwargs={
        'compression': 'zstd',
        'bloom_filter_columns': ['url'],
    }
)

# Query specific partition (only reads relevant files)
import duckdb
con = duckdb.connect()

us_results = con.execute("""
    SELECT url, status_code, duration
    FROM read_parquet('crawl_partitioned/country=US/**/*.parquet')
    WHERE status_code = 200
""").df()

print(f"Found {len(us_results)} successful US requests")

```

 

   

 

 

 

#####   Performance Tips

- **Bloom filters**: Always enable on URL column for O(1) lookups
- **Partitioning**: Partition large datasets by country or date to query only relevant files
- **Compression**: Use ZSTD for best balance of speed and compression (better than GZIP)
- **Row groups**: Smaller row groups (50k-100k) improve query selectivity
- **Statistics**: Enable column statistics for query optimization
 
 

## Best Practices

 #####   Recommended Practices 

 

  

 **Keep files compressed** Use `.warc.gz` for storage efficiency (10x+ compression)

 

 

 

  

 **Use streaming readers** Process large files without loading into memory

 

 

 

  

 **Index `WARC-Scrape-Log-Id`** For fast lookups and cross-referencing

 

 

 

  

 **Store original WARC files** For audit trails and reprocessing

 

 

 

  

 **Leverage custom headers** For analytics and debugging

 

 

 

 

 

 

 

 #####   Common Pitfalls 

 

  

 **Don't load entire files into memory** Use streaming iterators instead

 

 

 

  

 **Remember to decompress** Use `gzip.open` before reading

 

 

 

  

 **Multiple records per URL** WARC files may contain retries and redirects

 

 

 

  

 **Custom headers are optional** Check for `None` before using

 

 

 

 

 

 

 

 

## Next Steps

- Learn about [all retrieval methods](https://scrapfly.home/docs/crawler-api/results) available for crawler results
- Understand [crawler billing](https://scrapfly.home/docs/crawler-api/billing) and how WARC downloads are charged
- Explore [crawler configuration options](https://scrapfly.home/docs/crawler-api/getting-started)
- View the complete [crawler API specification](https://scrapfly.home/docs/crawler-api/getting-started#spec)
 
## External Resources

- [ ISO 28500:2017 WARC Standard ](https://www.iso.org/standard/68004.html) - Official WARC specification
- [ warcio (Python) ](https://github.com/webrecorder/warcio) - Recommended Python library
- [ node-warc (JavaScript) ](https://github.com/N0taN3rd/node-warc) - Node.js WARC library
- [ JWAT (Java) ](https://github.com/netarchivesuite/jwat) - Java WARC library
- [ gowarc (Go) ](https://github.com/nlnwa/gowarc) - Go WARC library

#   Extraction Rules 

 Automatically extract structured data from crawled pages by mapping URL patterns to extraction methods. Combine the power of recursive crawling with intelligent data extraction for fully automated web scraping pipelines.

#####  Pattern-Based Extraction

 Extraction rules allow you to apply different extraction strategies to different page types within the same crawl. For example, extract product data from `/products/*` pages and article content from `/blog/*` pages - all in a single crawler configuration.

 

## How Extraction Rules Work

 The `extraction_rules` parameter maps URL patterns to extraction configurations. As the crawler visits each page, it checks if the URL matches any defined patterns and automatically applies the corresponding extraction method.

  

## Configuration Syntax

 The `extraction_rules` parameter accepts a JSON object mapping URL patterns to extraction configurations:

 ```
{
  "extraction_rules": {
    "/products/*": {
      "type": "model",
      "value": "product"
    },
    "/blog/*": {
      "type": "prompt",
      "value": "Extract the article title, author, publish date, and main content"
    },
    "/reviews/*": {
      "type": "template",
      "value": "ephemeral:"
    }
  }
}
```

 

   

 

 

 

### Pattern Format

- **Exact match**: `"/products/special-page"` matches only that specific URL path
- **Wildcard**: `"/products/*"` matches all pages under /products/
- **Multi-level**: `"/category/*/products/*"` matches nested paths
- **Maximum length**: 1000 characters per pattern
 
######  Pattern Matching Rules

- Patterns are matched against the URL path only (not domain or query parameters)
- The **first matching pattern** is used - order matters!
- If no pattern matches, the page is crawled but not extracted
 
 

## Extraction Methods

 Extraction rules support the same three extraction methods available in the [Extraction API](https://scrapfly.home/docs/extraction-api/getting-started):

 

#####   Auto Model 

 `type: "model"`

 Use pre-trained AI models to extract common data types automatically.

 **Value**: Model name (e.g., `"product"`, `"article"`, `"review_list"`)

 [ Auto Model Documentation](https://scrapfly.home/docs/extraction-api/automatic-ai)

 

 

 

#####   LLM Prompt 

 `type: "prompt"`

 Provide natural language instructions for what data to extract.

 **Value**: Prompt text (max 10,000 characters)

 [ LLM Prompt Documentation](https://scrapfly.home/docs/extraction-api/llm-prompt)

 

 

 

#####   Template 

 `type: "template"`

 Define precise extraction rules using CSS, XPath, or regex selectors.

 **Value**: `ephemeral:`

 [ Template Documentation](https://scrapfly.home/docs/extraction-api/rules-and-template)

 

 

 

 

 

## Usage Examples

    E-commerce Site    Blog with LLM    Mixed Methods  

 ### E-commerce Site with Auto Models

 Crawl an e-commerce site and extract structured data from different page types using pre-trained AI models:

 ```
curl -X POST "https://api.scrapfly.home/crawl?key=scp-live-d8ac176c2f9d48b993b58675bdf71615" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://web-scraping.dev/products",
    "page_limit": 10,
    "extraction_rules": {
      "/product/*": {
        "type": "model",
        "value": "product"
      },
      "/products": {
        "type": "model",
        "value": "product_listing"
      }
    }
  }'
```

 

   

 

 

 

#### What This Does

- **Product detail pages** (`/product/*`): Extracts full product data including name, price, variants, description, specifications, reviews, and images
- **Product listing page** (`/products`): Extracts array of products with name, price, image, and link from the paginated catalog
 
  **Example Output:**- Product page extracts: `{"name": "Box of Chocolate Candy", "price": {"amount": "9.99", "currency": "USD"}, "rating": 4.7, ...}`
- Listing page extracts: `{"products": [{"name": "Box of Chocolate...", "price": "$24.99", ...}, ...]}`
 
 

  **Why this works:** Auto models are pre-trained on thousands of e-commerce sites, automatically detecting standard fields like price, name, description without configuration.

 

### Blog with LLM Prompt

 Use LLM prompts to extract blog articles with custom metadata and content analysis:

 ```
curl -X POST "https://api.scrapfly.home/crawl?key=scp-live-d8ac176c2f9d48b993b58675bdf71615" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://scrapfly.io/blog/",
    "page_limit": 10,
    "extraction_rules": {
      "/blog/*": {
        "type": "prompt",
        "value": "Extract the article data as JSON with: title, author_name, publish_date (YYYY-MM-DD format), reading_time_minutes (as number), main_topic, article_summary (max 200 chars), and primary_code_language (if tutorial includes code examples, otherwise null)"
      },
      "/blog/": {
        "type": "model",
        "value": "article"
      }
    }
  }'
```

 

   

 

 

 

#### What This Does

- **Blog articles** (`/blog/*`): Uses LLM prompt to extract article metadata plus custom fields like reading time, topic classification, and code language detection
- **Blog index** (`/blog/`): Uses `article` model for fast extraction of the article list page
 
  **Example Output:** `{"title": "How to Scrape Amazon Product Data", "author_name": "Scrapfly Team", "publish_date": "2024-03-15", "reading_time_minutes": 12, "main_topic": "web scraping tutorial", "article_summary": "Learn how to extract Amazon product data using...", "primary_code_language": "Python"}` 

 

  **Why use prompts:** LLM prompts can extract standard fields, derive new insights (topic classification, reading time), and transform data formats (date normalization) in a single extraction pass.

 

### Mixed Extraction Methods

 Combine auto models for standard pages and templates for complex nested structures:

 ```
curl -X POST "https://api.scrapfly.home/crawl?key=scp-live-d8ac176c2f9d48b993b58675bdf71615" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://web-scraping.dev/products",
    "page_limit": 10,
    "extraction_rules": {
      "/product/*": {
        "type": "template",
        "value": {
          "source": "html",
          "selectors": [
            {
              "name": "name",
              "query": "h3.product-title::text",
              "type": "css"
            },
            {
              "name": "price",
              "query": ".product-price::text",
              "type": "css"
            },
            {
              "name": "image",
              "query": ".product-img::attr(src)",
              "type": "css"
            },
            {
              "name": "specifications",
              "query": ".product-description dl",
              "type": "css",
              "nested": [
                {
                  "name": "key",
                  "query": "dt::text",
                  "type": "css"
                },
                {
                  "name": "value",
                  "query": "dd::text",
                  "type": "css"
                }
              ]
            },
            {
              "name": "variants",
              "query": ".variant-options .variant",
              "type": "css",
              "multiple": true,
              "nested": [
                {
                  "name": "color",
                  "query": ".color-name::text",
                  "type": "css"
                },
                {
                  "name": "size",
                  "query": ".size-value::text",
                  "type": "css"
                },
                {
                  "name": "in_stock",
                  "query": ".stock-status::attr(data-available)",
                  "type": "css"
                }
              ]
            }
          ]
        }
      },
      "/products": {
        "type": "model",
        "value": "product_listing"
      }
    }
  }'
```

 

   

 

 

 

#### What This Does

- **Product pages** (`/product/*`): Uses template to extract product details plus nested specs and variants arrays
- **Product listing** (`/products`): Uses `product_listing` model for fast extraction of list pages
 
  **Example Output:** `{"name": "Box of Chocolate Candy", "price": "$9.99", "specifications": [{"key": "Weight", "value": "500g"}, {"key": "Material", "value": "Chocolate"}], "variants": [{"color": "Dark", "size": "Medium", "in_stock": "true"}]}` 

 

  **Why mix methods:** Templates provide precision for complex nested structures (specs, variants) while models offer speed for simple list pages - optimizing both accuracy and cost.

 

 

## Accessing Extracted Data

 When using extraction rules, extracted data is included in the crawler results alongside the raw HTML content. The extracted data appears in the `extracted_data` field for each matched URL.

### Query Extracted Content via API

 ```
curl "https://api.scrapfly.home/crawl/{crawler_uuid}/contents?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&format=json"
```

 

   

 

 

 

Response example:

 ```
{
  "pages": [
    {
      "url": "https://web-scraping.dev/product/1",
      "status_code": 200,
      "content": "...",
      "extracted_data": {
        "name": "Box of Chocolate Candy",
        "price": "$9.99",
        "image": "https://web-scraping.dev/assets/products/orange-chocolate-box-medium.png",
        "specifications": [
          {"key": "Weight", "value": "500g"},
          {"key": "Material", "value": "Chocolate"}
        ],
        "variants": [
          {
            "color": "Dark",
            "size": "Medium",
            "in_stock": "true"
          }
        ]
      }
    }
  ]
}
```

 

   

 

 

 

### Download as Artifact

 For large crawls, download extracted data as part of the WARC artifact. The extracted data is stored in `conversion` records with `Content-Type: application/json`.

 ```
curl "https://api.scrapfly.home/crawl/{crawler_uuid}/artifact?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&type=warc" -o crawl.warc.gz
```

 

   

 

 

 

  See [WARC Format](https://scrapfly.home/docs/crawler-api/warc-format) documentation for parsing WARC files with extracted data.

## Best Practices

#####  Recommended Practices

- **Order patterns from specific to general**: Place more specific patterns before wildcards 
    Example: `"/products/featured"` before `"/products/*"`
- **Use appropriate extraction methods**: Choose auto models for standard data types, prompts for custom fields, templates for complex structures
- **Test extraction on sample URLs first**: Use the [standalone Extraction API](https://scrapfly.home/docs/extraction-api/getting-started) to validate extraction configs before crawling
- **Keep prompts focused**: Shorter, specific prompts yield better extraction results than lengthy instructions
- **Monitor extraction success**: Check the `extracted_data` field in results to ensure extraction worked as expected
 
 

#####  Common Pitfalls

- **Pattern order matters**: The first matching pattern wins - avoid overlapping patterns where order is ambiguous
- **URL encoding in patterns**: Patterns match decoded URL paths, not encoded ones
- **Extraction adds cost**: Each extracted page uses additional API credits - see [billing documentation](https://scrapfly.home/docs/crawler-api/billing)
- **Template complexity**: Very complex templates may slow down extraction - consider breaking into multiple simpler rules
 
 

## Billing & Credits

 Extraction rules consume additional API credits on top of the base crawling cost:

- **Auto Model**: +5 credits per extracted page
- **LLM Prompt**: +10 credits per extracted page
- **Template**: +1 credit per extracted page
 
  Only pages matching extraction rules incur extraction costs. Non-matched pages are crawled at standard rates. For detailed pricing, see [Crawler API Billing](https://scrapfly.home/docs/crawler-api/billing).

## Limitations

 | Limit | Value | Description |
|---|---|---|
| Max patterns per crawler | 50 | Maximum number of extraction rules |
| Pattern max length | 1000 chars | Maximum characters per URL pattern |
| Prompt max length | 10,000 chars | Maximum characters per LLM prompt |
| Template max size | 100 KB | Maximum size of encoded template |

## Next Steps

- Learn about [Auto Model extraction](https://scrapfly.home/docs/extraction-api/automatic-ai) and available models
- Explore [LLM Prompt extraction](https://scrapfly.home/docs/extraction-api/llm-prompt) for custom data needs
- Master [Template extraction](https://scrapfly.home/docs/extraction-api/rules-and-template) for precise control
- Understand [how to retrieve crawler results](https://scrapfly.home/docs/crawler-api/results) with extracted data
- Check [crawler billing](https://scrapfly.home/docs/crawler-api/billing) to optimize extraction costs
 
## External Resources

- [Guide: Web Scraping with AI and LLMs](https://scrapfly.io/blog/web-scraping-with-ai-and-llms/)
- [Extraction API Documentation](https://scrapfly.home/docs/extraction-api/getting-started)
- [Base64 Encoding Tool](https://scrapfly.io/dashboard/tools/base64) for template encoding

# Webhook

 Scrapfly's [webhook](https://scrapfly.home/docs/crawler-api/getting-started?view=markdown#webhook_name) feature is ideal for managing crawler jobs asynchronously. When webhook is specified through the `webhook_name` parameter, Scrapfly will notify your HTTP endpoint about crawl events in real-time, eliminating the need for polling.

 To start using webhooks, first one must be created using the [webhook web interface](https://scrapfly.home/dashboard/webhook).

    

  

 webhook management page  The webhook will be called for each event you subscribe to during the crawl lifecycle. For reconciliation, you will receive the `crawler_uuid` and `webhook_uuid` in the [response headers](#headers).

    

  

 webhook status report on monitoring log page > **Webhook Queue Size** The webhook queue size indicates the maximum number of queued webhooks that can be scheduled. After the crawler event is processed and your application is notified, the queue size is reduced. This allows you to schedule additional crawler jobs beyond the concurrency limit of your subscription. The scheduler will handle this and ensure that your concurrency limit is met.
> 
>  | ###### FREE   $0.00/mo | ###### DISCOVERY   $30.00/mo | ###### PRO   $100.00/mo | ###### STARTUP   $250.00/mo | ###### ENTERPRISE   $500.00/mo |
> |---|---|---|---|---|
> | 500 | 500 | 2,000 | 5,000 | 10,000 |

 [See in Your Dashboard](https://scrapfly.home/dashboard/webhook)

## Scope

 Webhooks are scoped per Scrapfly [projects](https://scrapfly.home/docs/project?view=markdown) and environments. Make sure to create a webhook for each of your projects and environments (test/live).

## Usage

> Webhooks can be used for multiple purposes. In the context of the Crawler API, to ensure you received a crawler event, you must check the header `X-Scrapfly-Webhook-Resource-Type` and verify the value is `crawler`.

 To enable webhook callbacks, specify the `webhook_name` parameter in your crawler requests and optionally provide a list of `webhook_events` you want to be notified about. Scrapfly will then call your webhook endpoint as crawl events occur.

 Note that your webhook endpoint must respond with a `2xx` status code for the webhook to be considered successful. The `3xx` redirect responses will be followed, and response codes `4xx` and `5xx` are considered failures and will be retried as per the retry policy.

> The below examples assume you have a webhook named **my-crawler-webhook** registered. You can create webhooks via the [web dashboard](https://scrapfly.home/dashboard/webhook).

## Webhook Events & Payloads

 The Crawler API supports multiple webhook events that notify you about different stages of the crawl lifecycle. Each event sends a JSON payload with the crawler state and event-specific data.

> **Default Subscription** If you don't specify `webhook_events`, you'll receive: `crawler_started`, `crawler_stopped`, `crawler_cancelled`, and `crawler_finished`.

### HTTP Headers

 Every webhook request includes these HTTP headers for easy routing and verification:

 | Header | Purpose | Example Value |
|---|---|---|
| `X-Scrapfly-Crawl-Event-Name` | **Fast routing** - Use this to route events without parsing JSON | `crawler_started` |
| `X-Scrapfly-Webhook-Resource-Type` | Resource type (always `crawler` for crawler webhooks) | `crawler` |
| `X-Scrapfly-Webhook-Job-Id` | Crawler UUID for tracking and reconciliation | `550e8400-e29b...` |
| `X-Scrapfly-Webhook-Signature` | HMAC-SHA256 signature for verification | `a3f2b1c...` |

  **Performance Tip** Route webhook events using the `X-Scrapfly-Crawl-Event-Name` header instead of parsing the JSON body. This is significantly faster for high-frequency events like `crawler_url_visited`.

 

### Event Types & Examples

 Click each tab below to see the event description and full JSON payload example:

    crawler\_started    crawler\_url\_visited High Freq    crawler\_url\_failed    crawler\_url\_skipped    crawler\_url\_discovered High Freq    crawler\_finished    crawler\_stopped    crawler\_cancelled  

 #####  crawler\_started

**When:** Crawler execution begins

**Use case:** Track when crawls start, log crawler UUID, initialize tracking systems

**Frequency:** Once per crawl

 **Key Fields:** `crawler_uuid`, `seed_url`, `links.status` 

 ```
{
    "event": "crawler_started",
    "payload": {
        "crawler_uuid": "60cf1121-9de4-43fc-a0c6-7dda1721a65b",
        "project": "default",
        "env": "LIVE",
        "seed_url": "https://web-scraping.dev/products",
        "action": "started",
        "state": {
            "duration": 1,
            "urls_visited": 0,
            "urls_extracted": 0,
            "urls_failed": 0,
            "urls_skipped": 0,
            "urls_to_crawl": 0,
            "api_credit_used": 0,
            "stop_reason": null,
            "start_time": 1762939798,
            "stop_time": 1762939799
        },
        "links": {
            "status": "https://api.scrapfly.io/crawl/60cf1121-9de4-43fc-a0c6-7dda1721a65b/status"
        }
    }
}

```

 

   

 

 

#####  crawler\_url\_visited

**When:** Each URL is successfully crawled

**Use case:** Real-time progress tracking, streaming results, monitoring performance

**Frequency:** High - Fires for every successfully crawled URL (can be thousands per crawl)

  **Performance Warning:** Your endpoint must handle high throughput. Use `X-Scrapfly-Crawl-Event-Name` header for fast routing without parsing JSON body. 

 ```
{
    "event": "crawler_url_visited",
    "payload": {
        "crawler_uuid": "60cf1121-9de4-43fc-a0c6-7dda1721a65b",
        "project": "default",
        "env": "LIVE",
        "url": "https://web-scraping.dev/products",
        "action": "visited",
        "state": {
            "duration": 1,
            "urls_visited": 0,
            "urls_extracted": 0,
            "urls_failed": 0,
            "urls_skipped": 0,
            "urls_to_crawl": 0,
            "api_credit_used": 1,
            "stop_reason": null,
            "start_time": 1762939798,
            "stop_time": 1762939799
        },
        "scrape": {
            "status_code": 200,
            "country": "de",
            "log_uuid": "01K9VPD22494F0ZEX7DGEZQ4ES",
            "log_url": "https://scrapfly.io/dashboard/monitoring/log/01K9VPD22494F0ZEX7DGEZQ4ES",
            "content": {
                "html": "[...]",
                "text": "[...]"
                ...
            }
        }
    }
}

```

 

   

 

 

#####  crawler\_url\_failed

**When:** A URL fails to crawl (network error, timeout, block, etc.)

**Use case:** Error monitoring, retry logic, debugging failed scrapes

**Frequency:** Per failed URL

  **Debugging Features:**- `error` - Error code for classification
- `links.log` - Direct link to scrape log for debugging
- `scrape_config` - Complete configuration to replay the scrape
- `links.scrape` - Ready-to-use retry URL with same configuration
 
 

 ```
{
    "event": "crawler_url_failed",
    "payload": {
        "state": {
            "duration": 3,
            "urls_visited": 0,
            "urls_extracted": 0,
            "urls_failed": 0,
            "urls_skipped": 0,
            "urls_to_crawl": 0,
            "api_credit_used": 0,
            "stop_reason": null,
            "start_time": 1762944028,
            "stop_time": 1762944031
        },
        "action": "failed",
        "crawler_uuid": "5caa5439-03a4-4c74-9a4c-0597e190dd72",
        "project": "default",
        "env": "LIVE",
        "url": "https://web-scraping.dev/products",
        "error": "ERR::SCRAPE::NETWORK_ERROR",
        "scrape_config": {
            "method": "GET",
            "url": "https://web-scraping.dev/products",
            "body": null,
            "project": "default",
            "env": "LIVE",
            "render_js": false,
            "rendering_timeout": 0,
            "asp": false,
            "proxy_pool": null,
            "country": "de",
            "headers": {},
            "format": "raw",
            "retry": true,
            "correlation_id": "5caa5439-03a4-4c74-9a4c-0597e190dd72",
            "tags": [
                "crawler"
            ],
            "wait_for_selector": null,
            "cache": false,
            "cache_ttl": 86400,
            "cache_clear": false,
            "geolocation": null,
            "screenshot_api_cost": 60,
            "screenshot_flags": null,
            "format_options": [],
            "auto_scroll": false,
            "js_scenario": null,
            "screenshots": {},
            "lang": null,
            "os": null,
            "js": null,
            "rendering_stage": "complete",
            "extraction_prompt": null,
            "extraction_model": null,
            "extraction_model_custom_schema": null,
            "extraction_template": null
        },
        "links": {
            "log": "https://api.scrapfly.io/crawl/5caa5439-03a4-4c74-9a4c-0597e190dd72/logs?url=https://web-scraping.dev/products"
        }
    }
}

```

 

   

 

 

#####  crawler\_url\_skipped

**When:** URLs are skipped (already visited, filtered, depth limit, etc.)

**Use case:** Monitor filtering effectiveness, track duplicate discovery

**Frequency:** Per batch of skipped URLs

 **Key Fields:** `urls` contains a map of each skipped URL to its skip reason 

 ```
{
    "event": "crawler_url_skipped",
    "payload": {
        "state": {
            "duration": 2,
            "urls_visited": 1,
            "urls_extracted": 22,
            "urls_failed": 0,
            "urls_skipped": 21,
            "urls_to_crawl": 1,
            "api_credit_used": 3,
            "stop_reason": "page_limit",
            "start_time": 1762940028,
            "stop_time": 1762940030
        },
        "action": "skipped",
        "crawler_uuid": "b4867c50-318c-47cd-bfc9-bed67f24771a",
        "project": "default",
        "env": "LIVE",
        "urls": {
            "https://web-scraping.dev/product/2?variant=one": "page_limit",
            "https://web-scraping.dev/product/25": "page_limit",
            "https://web-scraping.dev/product/15": "page_limit",
            "https://web-scraping.dev/product/9": "page_limit",
            "https://web-scraping.dev/product/2?variant=six-pack": "page_limit"
        }
    }
}

```

 

   

 

 

#####  crawler\_url\_discovered

**When:** New URLs are discovered from crawled pages

**Use case:** Track crawl expansion, monitor discovery patterns, sitemap building

**Frequency:** High - Fires for each batch of discovered URLs

 **Key Fields:** `origin` (source URL where links were found), `discovered_urls` (list of new URLs) 

 ```
{
    "event": "crawler_url_discovered",
    "payload": {
        "state": {
            "duration": 3,
            "urls_visited": 0,
            "urls_extracted": 0,
            "urls_failed": 0,
            "urls_skipped": 0,
            "urls_to_crawl": 0,
            "api_credit_used": 1,
            "stop_reason": null,
            "start_time": 1762940138,
            "stop_time": 1762940141
        },
        "action": "url_discovery",
        "crawler_uuid": "92e97a67-a962-4dcd-9b3e-261e4d4cb6f5",
        "project": "default",
        "env": "LIVE",
        "origin": "navigation",
        "discovered_urls": [
            "https://web-scraping.dev/product/5",
            "https://web-scraping.dev/product/1",
            "https://web-scraping.dev/product/3",
            "https://web-scraping.dev/product/4",
            "https://web-scraping.dev/product/2"
        ]
    }
}

```

 

   

 

 

#####  crawler\_finished

**When:** Crawler completes successfully (at least one URL visited)

**Use case:** Trigger post-processing, download results, send completion notifications

**Frequency:** Once per successful crawl

  **Success Indicators:** `state.urls_visited` > 0 confirms at least one URL was crawled. Check `state.stop_reason` to understand why the crawler completed (e.g., `no_more_urls`, `page_limit`). 

 ```
{
    "event": "crawler_finished",
    "payload": {
        "crawler_uuid": "b4867c50-318c-47cd-bfc9-bed67f24771a",
        "project": "default",
        "env": "LIVE",
        "seed_url": "https://web-scraping.dev/products",
        "action": "finished",
        "state": {
            "duration": 6.11,
            "urls_visited": 5,
            "urls_extracted": 49,
            "urls_failed": 0,
            "urls_skipped": 44,
            "urls_to_crawl": 5,
            "api_credit_used": 5,
            "stop_reason": "page_limit",
            "start_time": 1762940028,
            "stop_time": 1762940034.1143808
        },
        "links": {
            "status": "https://api.scrapfly.io/crawl/b4867c50-318c-47cd-bfc9-bed67f24771a/status"
        }
    }
}

```

 

   

 

 

#####  crawler\_stopped

**When:** Crawler stops due to failure (seed URL failed, errors, no URLs visited)

**Use case:** Error alerting, failure logging, retry automation

**Frequency:** Once per failed crawl

  **Failure Reasons:** Check `state.stop_reason` for the exact cause: - `seed_url_failed` - Initial URL couldn't be crawled
- `crawler_error` - Internal crawler error occurred
- `no_api_credit_left` - Account ran out of API credits mid-crawl
- `max_api_credit` - Configured credit limit reached
 
 

 ```
{
    "event": "crawler_stopped",
    "payload": {
        "crawler_uuid": "d1f6f97a-c48d-440f-86ca-b21b254ba12f",
        "project": "default",
        "env": "LIVE",
        "seed_url": "https://web-scraping.dev/products",
        "action": "stopped",
        "state": {
            "duration": 8.53,
            "urls_visited": 0,
            "urls_extracted": 1,
            "urls_failed": 1,
            "urls_skipped": 0,
            "urls_to_crawl": 1,
            "api_credit_used": 0,
            "stop_reason": "seed_url_failed",
            "start_time": 1762951426,
            "stop_time": 1762951434.5287035
        },
        "links": {
            "status": "https://api.scrapfly.home/crawl/d1f6f97a-c48d-440f-86ca-b21b254ba12f/status"
        }
    }
}

```

 

   

 

 

#####  crawler\_cancelled

**When:** User manually cancels the crawl via API or dashboard

**Use case:** Update tracking systems, release resources, log cancellations

**Frequency:** Once per user cancellation

  **Cancellation State:** `state.stop_reason` will be `user_cancelled`. Partial crawl results are available via the status endpoint and can be retrieved normally. 

 ```
{
    "event": "crawler_cancelled",
    "payload": {
        "crawler_uuid": "60cf1121-9de4-43fc-a0c6-7dda1721a65b",
        "project": "default",
        "env": "LIVE",
        "seed_url": "https://web-scraping.dev/products",
        "action": "cancelled",
        "state": {
            "duration": 45,
            "urls_visited": 23,
            "urls_extracted": 87,
            "urls_failed": 2,
            "urls_skipped": 5,
            "urls_to_crawl": 57,
            "api_credit_used": 230,
            "stop_reason": "user_cancelled",
            "start_time": 1762939798,
            "stop_time": 1762939843
        },
        "links": {
            "status": "https://api.scrapfly.io/crawl/60cf1121-9de4-43fc-a0c6-7dda1721a65b/status"
        }
    }
}

```

 

   

 

 

 

## Development

 Useful tools for local webhook development:

-  - Collect and display webhook notifications
-  - Expose your local application through a secured tunnel to the internet
 
## Security

 Webhooks are signed using HMAC (Hash-based Message Authentication Code) with the SHA-256 algorithm to ensure the integrity of the webhook content and verify its authenticity. This mechanism helps prevent tampering and ensures that webhook payloads are from trusted sources.

#### HMAC Overview

 HMAC is a cryptographic technique that combines a secret key with a hash function (in this case, SHA-256) to produce a fixed-size hash value known as the HMAC digest. This digest is unique to both the original message and the secret key, providing a secure way to verify the integrity and authenticity of the message.

#### Signature in HTTP Header

 When Scrapfly sends a webhook notification, it includes an HMAC signature in the `X-Scrapfly-Webhook-Signature` HTTP header. This signature is generated by applying the HMAC-SHA256 algorithm to the entire request body using your webhook's secret key (configured in the webhook settings).

#### Verification Example

 To verify the authenticity of a webhook notification, compute the HMAC-SHA256 signature of the request body using your secret key and compare it with the signature provided in the `X-Scrapfly-Webhook-Signature` header:

 ```
import hmac
import hashlib

# Example secret key (replace with actual secret key from webhook settings)
secret_key = b'my_secret_key'

# Example webhook payload (replace with actual payload)
webhook_payload = b'{"event": "crawler_finished", "crawler_uuid": "..."}'

# Compute HMAC-SHA256 signature
computed_signature = hmac.new(secret_key, webhook_payload, hashlib.sha256).hexdigest()

# Compare computed signature with received signature
received_signature = '...'  # Extracted from X-Scrapfly-Webhook-Signature header
if computed_signature == received_signature:
    print("Signature verification successful. Payload is authentic.")
else:
    print("Signature verification failed. Payload may have been tampered with.")

```

 

   

 

> **Security Best Practices**- Always verify the HMAC signature before processing webhook payloads
> - Keep your webhook secret key confidential and rotate it periodically
> - Use HTTPS endpoints for webhook URLs to encrypt data in transit
> - Implement rate limiting on your webhook endpoint to handle high-frequency events

## Next Steps

- Create your first webhook in the [webhook dashboard](https://scrapfly.home/dashboard/webhook)
- Learn about [crawler configuration options](https://scrapfly.home/docs/crawler-api/getting-started)
- Review [error handling](https://scrapfly.home/docs/crawler-api/errors) for webhook failures

# Crawler API Billing

 The Crawler API billing is simple: **crawler cost = sum of all Web Scraping API calls made during the crawl**.

## How It Works 

  **Each page crawled = 1 Web Scraping API request** The crawler makes individual scraping requests for each page it discovers. Each request is billed exactly the same as if you called the Web Scraping API directly.

 

 **Total crawler cost** = Number of pages crawled × Cost per page

 The cost per page depends on the features you enable in your crawler configuration:

- **ASP (Anti-Scraping Protection):** Enables browser rendering and bypass features
- **Proxy pool:** Datacenter (standard) or residential proxies
- **Proxy country:** Geographic location of the proxy
- **Screenshots:** If screenshots are captured
- **Content extraction:** AI-powered extraction features (see [Extraction Rules](https://scrapfly.home/docs/crawler-api/extraction-rules))
- **Cache usage:** Cached pages cost 0 credits
 
 For detailed pricing rules and cost breakdown, see the [**Web Scraping API Billing documentation**](https://scrapfly.home/docs/scrape-api/billing).

## Cost Examples 

 Here are a few examples showing how crawler costs are calculated. Remember, each page follows the same billing rules as the Web Scraping API.

### Example 1: Basic Crawl (100 pages, no ASP)

 ```
{
  "url": "https://example.com",
  "max_pages": 100,
  "asp": false
}
```

 

   

 

 

 

**Cost:** 100 pages × base cost per page = **see Web Scraping API pricing**

### Example 2: Crawl with ASP (100 pages)

 ```
{
  "url": "https://example.com",
  "max_pages": 100,
  "asp": true
}
```

 

   

 

 

 

**Cost:** 100 pages × (base cost + ASP cost) = **see Web Scraping API pricing**

### Example 3: Crawl with Residential Proxies (100 pages)

 ```
{
  "url": "https://example.com",
  "max_pages": 100,
  "proxy_pool": "public_residential_pool"
}
```

 

   

 

 

 

**Cost:** 100 pages × (base cost + residential proxy cost) = **see Web Scraping API pricing**

  **Calculate Your Costs** For exact pricing per feature, visit the [Web Scraping API Billing page](https://scrapfly.home/docs/scrape-api/billing) or check the [pricing page](https://scrapfly.home/pricing).

 

## Cost Control 

### Set Budget Limits

 Control costs by setting hard limits on your crawl:

- `max_pages` - Limit total pages crawled
- `max_duration` - Limit crawl duration in seconds
- `max_api_credit_cost` - Stop crawl when credit limit is reached
 
 ```
{
  "url": "https://example.com",
  "max_pages": 500,
  "max_duration": 1800,
  "max_api_credit_cost": 3000
}
```

 

   

 

 

 

### Project Budget Limits

 Set crawler-specific budget limits in your [project settings](https://scrapfly.home/docs/project) to prevent unexpected costs:

- Monthly crawler credit limit
- Per-job credit limit
- Automatic alerts when approaching limits
 
## Cost Optimization Tips 

 Since each page is billed like a Web Scraping API call, you can reduce costs by:

### 1. Crawl Only What You Need

- **Use path filtering:** `include_only_paths` and `exclude_paths`
- **Set page limits:** `max_pages` to cap total pages
- **Limit depth:** `max_depth` to focus on nearby pages
- **Set budget limits:** `max_api_credit` to stop when budget is reached
 
### 2. Use Caching

 Enable caching to avoid re-scraping unchanged pages:

 ```
{
  "url": "https://example.com",
  "cache": true,
  "cache_ttl": 86400
}
```

 

   

 

 

 

 Cached pages cost **0 credits** when hit within TTL period.

### 3. Choose the Right Features

- **ASP:** Only enable if the site has anti-bot protection (costs more)
- **Proxy pool:** Use datacenter by default, residential only when needed (costs significantly more)
- **Screenshots:** Only capture if required (adds to cost)
- **Content formats:** Extract only the formats you need
 
 For detailed cost optimization strategies, see: [Web Scraping API Cost Optimization](https://scrapfly.home/docs/scrape-api/billing#optimization)

## Billing Transparency 

 Track your crawler costs in real-time:

### Cost in API Response

The crawl status endpoint includes cost information:

 ```
{
  "uuid": "550e8400-e29b-41d4-a716-446655440000",
  "status": "RUNNING",
  "urls_crawled": 847,
  "total_api_credit_consumed": 5082,
  "average_cost_per_page": 6
}
```

 

   

 

 

 

### Dashboard Analytics

 View detailed cost breakdowns in your [monitoring dashboard](https://scrapfly.home/docs/monitoring):

- Cost per crawl job
- Cost per URL
- Feature usage breakdown
- Daily/monthly cost trends
 
## Billing FAQ 

### Q: Does pausing a crawler stop billing?

 Yes. When you pause a crawler, no new pages are crawled and no new credits are consumed.

### Q: Are duplicate URLs counted?

 No. The crawler automatically deduplicates URLs. Each unique URL is only crawled once per job.

### Q: How are robots.txt requests billed?

 Robots.txt and sitemap.xml requests are **free** and do not consume credits.

### Q: What happens if I exceed my budget limit?

 The crawler automatically stops when `max_api_credit_cost` is reached. You can resume it by increasing the limit.

### Q: Can I get a refund for a failed crawl?

 Failed crawls (system errors) are automatically not billed. For other issues, contact [support](https://scrapfly.home/docs/support).

## Related Documentation 

- [Web Scraping API Billing](https://scrapfly.home/docs/scrape-api/billing)
- [Account Billing & Subscriptions](https://scrapfly.home/docs/billing)
- [Project Budget Management](https://scrapfly.home/docs/project)
- [Pricing Plans](https://scrapfly.home/pricing)

# Crawler API Errors

 The Crawler API returns standard HTTP status codes and detailed error information to help you troubleshoot issues. This page lists error codes specific to crawler operations and inherited errors from the Web Scraping API.

  **Note:** Crawler API also inherits all error codes from the [Web Scraping API](https://scrapfly.home/docs/scrape-api/errors) since each crawled page is treated as a scrape request. 

## Crawler-Specific Errors 

 The Crawler API has specific error codes that are unique to crawler operations:

####  ERR::CRAWLER::ALREADY\_SCHEDULED [  ](https://scrapfly.home/docs/crawler-api/error/ERR::CRAWLER::ALREADY_SCHEDULED) 

The given crawler uuid is already scheduled

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Crawler Documentation](https://scrapfly.io/docs/crawler-api/getting-started)
    - [Crawler Troubleshooting](https://scrapfly.io/docs/crawler-api/troubleshoot)
    - [Related Error Doc](https://scrapfly.io/docs/crawler-api/error/ERR::CRAWLER::ALREADY_SCHEDULED)
 
 

 

 

 

####  ERR::CRAWLER::CONFIG\_ERROR [  ](https://scrapfly.home/docs/crawler-api/error/ERR::CRAWLER::CONFIG_ERROR) 

Crawler configuration error

 

- **Retryable:** No
- **HTTP status code:** `400`
- **Documentation:**
    - [Crawler Documentation](https://scrapfly.io/docs/crawler-api/getting-started)
    - [Related Error Doc](https://scrapfly.io/docs/crawler-api/error/ERR::CRAWLER::CONFIG_ERROR)
 
 

 

 

 

## Intelligent Error Handling 

 The Crawler automatically monitors and responds to errors during execution, protecting your crawl budget and preventing wasted API credits. Different error types trigger different automated responses.

  **Automatic Protection:** The Crawler intelligently stops, throttles, or monitors based on error patterns. You don't need to manually handle most error scenarios - the system protects you automatically. 

### Fatal Errors - Immediate Stop 

 These errors immediately stop the crawler to prevent unnecessary API credit consumption. When encountered, the crawler terminates gracefully and returns results for URLs already crawled.

  **Immediate Termination:** Fatal errors stop the crawler instantly. Review and resolve these issues before restarting. 

**Fatal error codes:**

- [ `ERR::SCRAPE::PROJECT_QUOTA_LIMIT_REACHED` ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::PROJECT_QUOTA_LIMIT_REACHED) - Your project has reached its API credit limit
- [ `ERR::SCRAPE::QUOTA_LIMIT_REACHED` ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::QUOTA_LIMIT_REACHED) - Your account has reached its API credit limit
- [ `ERR::THROTTLE::MAX_API_CREDIT_BUDGET_EXCEEDED` ](https://scrapfly.home/docs/scrape-api/error/ERR::THROTTLE::MAX_API_CREDIT_BUDGET_EXCEEDED) - Monthly budget exceeded
- [ `ERR::ACCOUNT::PAYMENT_REQUIRED` ](https://scrapfly.home/docs/scrape-api/error/ERR::ACCOUNT::PAYMENT_REQUIRED) - Payment required to continue service
- [ `ERR::ACCOUNT::SUSPENDED` ](https://scrapfly.home/docs/scrape-api/error/ERR::ACCOUNT::SUSPENDED) - Account suspended
 
**What happens when a fatal error occurs:**

1. Crawler stops immediately (no new URLs are crawled)
2. URLs already crawled are saved with their results
3. Crawler status transitions to `completed` or `failed`
4. Error details are included in the crawler response
 
### Throttle Errors - Automatic Pause 

 These errors trigger an automatic 5-second pause before the crawler continues. This prevents overwhelming your account limits or proxy resources while allowing the crawl to complete successfully.

  **Automatic Recovery:** The crawler pauses for 5 seconds when throttle errors occur, then resumes automatically. This is normal behavior and helps your crawl complete successfully. 

**Throttle error codes:**

- [ `ERR::THROTTLE::MAX_REQUEST_RATE_EXCEEDED` ](https://scrapfly.home/docs/scrape-api/error/ERR::THROTTLE::MAX_REQUEST_RATE_EXCEEDED) - Request rate limit exceeded
- [ `ERR::THROTTLE::MAX_CONCURRENT_REQUEST_EXCEEDED` ](https://scrapfly.home/docs/scrape-api/error/ERR::THROTTLE::MAX_CONCURRENT_REQUEST_EXCEEDED) - Concurrent request limit exceeded
- [ `ERR::PROXY::RESOURCES_SATURATION` ](https://scrapfly.home/docs/scrape-api/error/ERR::PROXY::RESOURCES_SATURATION) - Proxy pool temporarily saturated
- [ `ERR::SESSION::CONCURRENT_ACCESS` ](https://scrapfly.home/docs/scrape-api/error/ERR::SESSION::CONCURRENT_ACCESS) - Session concurrency limit reached
 
**What happens during throttling:**

1. Crawler pauses for 5 seconds
2. Failed URL is added back to the queue for retry
3. Crawler continues with next URLs after pause
4. Process repeats if throttle error occurs again
 
 ```
{
  "status": "running",
  "urls_crawled": 47,
  "urls_pending": 153,
  "recent_event": "Throttle pause: MAX_REQUEST_RATE_EXCEEDED - resuming in 5s"
}
```

 

   

 

 

 

### High Failure Rate Protection 

 For certain error types (anti-scraping protection and internal errors), the crawler monitors the failure rate and automatically stops if it becomes too high. This prevents wasting credits on a crawl that's unlikely to succeed.

  **Smart Monitoring:** The crawler tracks failure rates for ASP and internal errors. If 70% or more of the last 10 scrapes fail, the crawler stops automatically to protect your credits. 

**Monitored error codes:**

- [ `ERR::ASP::SHIELD_ERROR` ](https://scrapfly.home/docs/scrape-api/error/ERR::ASP::SHIELD_ERROR) - Anti-scraping protection error
- [ `ERR::ASP::SHIELD_PROTECTION_FAILED` ](https://scrapfly.home/docs/scrape-api/error/ERR::ASP::SHIELD_PROTECTION_FAILED) - Failed to bypass anti-scraping protection
- [ `ERR::API::INTERNAL_ERROR` ](https://scrapfly.home/docs/scrape-api/error/ERR::API::INTERNAL_ERROR) - Internal API error
 
**Failure rate threshold:**

- **Monitoring window:** Last 10 scrape requests
- **Threshold:** 70% failure rate (7 or more failures out of 10)
- **Action:** Crawler stops immediately to prevent credit waste
- **Reason:** Indicates systematic issue (website blocking, ASP changes, API issues)
 
 ```
{
  "status": "failed",
  "urls_crawled": 15,
  "urls_failed": 12,
  "error": {
    "code": "ERR::CRAWLER::HIGH_FAILURE_RATE",
    "message": "Crawler stopped: High failure rate detected (8/10 requests failed)",
    "details": {
      "failure_rate": 0.80,
      "threshold": 0.70,
      "recent_errors": ["ERR::ASP::SHIELD_ERROR", "ERR::ASP::SHIELD_PROTECTION_FAILED"]
    }
  }
}
```

 

   

 

 

 

**How to handle high failure rate stops:**

1. **Review error logs:** Check which specific errors are occurring most frequently
2. **ASP errors:** The target site may have updated their protection - contact support for assistance
3. **Adjust configuration:** Try different `asp` settings, proxy pools, or rendering options
4. **Wait and retry:** Some sites have temporary blocks that clear after a period
5. **Contact support:** If issues persist, our team can help analyze and resolve ASP challenges
 
### Error Statistics & Monitoring 

 When a crawler completes (successfully or due to errors), comprehensive error statistics are logged and available for analysis. This helps you understand what went wrong and how to improve future crawls.

**Statistics tracked:**

- Total errors encountered
- Breakdown by error code (e.g., 3x `ERR::THROTTLE::MAX_REQUEST_RATE_EXCEEDED`)
- Fatal errors that stopped the crawler
- Throttle events and pause counts
- High failure rate trigger details
 
 ```
{
  "crawler_id": "abc123...",
  "status": "completed",
  "urls_crawled": 847,
  "urls_failed": 23,
  "error_summary": {
    "total_errors": 23,
    "by_code": {
      "ERR::THROTTLE::MAX_REQUEST_RATE_EXCEEDED": 15,
      "ERR::PROXY::CONNECTION_TIMEOUT": 5,
      "ERR::ASP::SHIELD_ERROR": 3
    },
    "throttle_pauses": 15,
    "fatal_stops": 0,
    "high_failure_rate_stops": 0
  }
}
```

 

   

 

 

 

**Accessing error details:**

1. **Crawler summary:** Use `GET /crawl/{uuid}` to view overall error statistics
2. **Failed URLs:** Use `GET /crawl/{uuid}/urls?status=failed` to retrieve specific failed URLs with error codes
3. **Logs:** Check your crawler logs for detailed error tracking information
 
## Inherited Web Scraping API Errors 

 Since the Crawler API makes individual scraping requests for each page crawled, it can return **any error from the Web Scraping API**. Each page crawled follows the same error handling as a single scrape request.

  **Important:** When a page fails to crawl, the error details are stored in the crawl results. You can retrieve failed URLs and their error codes using the `/crawl/{uuid}/urls?status=failed` endpoint. 

**Common inherited errors by category:**

### Scraping Errors

####  ERR::SCRAPE::BAD\_PROTOCOL [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::BAD_PROTOCOL) 

The protocol is not supported only http:// or https:// are supported

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::BAD_PROTOCOL)
 
 

 

 

 

####  ERR::SCRAPE::BAD\_UPSTREAM\_RESPONSE [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::BAD_UPSTREAM_RESPONSE) 

The website you target respond with an unexpected status code (>400)

 

- **Retryable:** No
- **HTTP status code:** `200`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::BAD_UPSTREAM_RESPONSE)
 
 

 

 

 

####  ERR::SCRAPE::CONFIG\_ERROR [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::CONFIG_ERROR) 

Scrape Configuration Error

 

- **Retryable:** No
- **HTTP status code:** `400`
- **Documentation:**
    - [Getting Started](https://scrapfly.io/docs/scrape-api/getting-started)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::CONFIG_ERROR)
 
 

 

 

 

####  ERR::SCRAPE::COST\_BUDGET\_LIMIT [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::COST_BUDGET_LIMIT) 

Cost budget has been reached, you must increase the budget to pass this target

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [Checkout ASP documentation](https://scrapfly.io/docs/scrape-api/anti-scraping-protection)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::COST_BUDGET_LIMIT)
 
 

 

 

 

####  ERR::SCRAPE::COUNTRY\_NOT\_AVAILABLE\_FOR\_TARGET [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::COUNTRY_NOT_AVAILABLE_FOR_TARGET) 

Country not available

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::COUNTRY_NOT_AVAILABLE_FOR_TARGET)
 
 

 

 

 

####  ERR::SCRAPE::DNS\_NAME\_NOT\_RESOLVED [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::DNS_NAME_NOT_RESOLVED) 

The DNS of the targeted website is not resolving or not responding

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::DNS_NAME_NOT_RESOLVED)
 
 

 

 

 

####  ERR::SCRAPE::DOMAIN\_NOT\_ALLOWED [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::DOMAIN_NOT_ALLOWED) 

The Domain targeted is not allowed or restricted

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::DOMAIN_NOT_ALLOWED)
 
 

 

 

 

####  ERR::SCRAPE::DOM\_SELECTOR\_INVALID [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::DOM_SELECTOR_INVALID) 

The DOM Selector is invalid

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Javascript Documentation](https://scrapfly.io/docs/scrape-api/javascript-rendering)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::DOM_SELECTOR_INVALID)
 
 

 

 

 

####  ERR::SCRAPE::DOM\_SELECTOR\_INVISIBLE [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::DOM_SELECTOR_INVISIBLE) 

The requested DOM selected is invisible (Mostly issued when element is targeted for screenshot)

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Javascript Documentation](https://scrapfly.io/docs/scrape-api/javascript-rendering)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::DOM_SELECTOR_INVISIBLE)
 
 

 

 

 

####  ERR::SCRAPE::DOM\_SELECTOR\_NOT\_FOUND [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::DOM_SELECTOR_NOT_FOUND) 

The requested DOM selected was not found in rendered content within 15s

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Javascript Documentation](https://scrapfly.io/docs/scrape-api/javascript-rendering)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::DOM_SELECTOR_NOT_FOUND)
 
 

 

 

 

####  ERR::SCRAPE::DRIVER\_CRASHED [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::DRIVER_CRASHED) 

Driver used to perform the scrape can crash for many reason

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::DRIVER_CRASHED)
 
 

 

 

 

####  ERR::SCRAPE::DRIVER\_INSUFFICIENT\_RESOURCES [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::DRIVER_INSUFFICIENT_RESOURCES) 

Driver do not have enough resource to render the page correctly

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::DRIVEDRIVER_INSUFFICIENT_RESOURCES)
 
 

 

 

 

####  ERR::SCRAPE::DRIVER\_TIMEOUT [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::DRIVER_TIMEOUT) 

Driver timeout - No response received

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::DRIVER_TIMEOUT)
 
 

 

 

 

####  ERR::SCRAPE::FORMAT\_CONVERSION\_ERROR [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::FORMAT_CONVERSION_ERROR) 

Response format conversion failed, unsupported input content type

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [API Format Parameter](https://scrapfly.io/docs/scrape-api/getting-started#api_param_format)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::FORMAT_CONVERSION_ERROR)
 
 

 

 

 

####  ERR::SCRAPE::JAVASCRIPT\_EXECUTION [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::JAVASCRIPT_EXECUTION) 

The javascript to execute goes wrong, please read the associated message to figure out the problem

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Checkout Javascript Rendering Documentation](https://scrapfly.io/docs/scrape-api/javascript-rendering)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::JAVASCRIPT_EXECUTION)
 
 

 

 

 

####  ERR::SCRAPE::NETWORK\_ERROR [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::NETWORK_ERROR) 

Network error happened between Scrapfly server and remote server

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::NETWORK_ERROR)
 
 

 

 

 

####  ERR::SCRAPE::NETWORK\_SERVER\_DISCONNECTED [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::NETWORK_SERVER_DISCONNECTED) 

Server of upstream website closed unexpectedly the connection

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::NETWORK_SERVER_DISCONNECTED)
 
 

 

 

 

####  ERR::SCRAPE::NO\_BROWSER\_AVAILABLE [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::NO_BROWSER_AVAILABLE) 

No browser available in the pool

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::NO_BROWSER_AVAILABLE)
 
 

 

 

 

####  ERR::SCRAPE::OPERATION\_TIMEOUT [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::OPERATION_TIMEOUT) 

This is a generic error for when timeout occur. It happened when internal operation took too much time

 

- **Retryable:** Yes
- **HTTP status code:** `504`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::OPERATION_TIMEOUT)
    - [Timeout Documentation](https://scrapfly.io/docs/scrape-api/understand-timeout)
 
 

 

 

 

####  ERR::SCRAPE::PLATFORM\_NOT\_AVAILABLE\_FOR\_TARGET [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::PLATFORM_NOT_AVAILABLE_FOR_TARGET) 

Platform not available

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::PLATFORM_NOT_AVAILABLE_FOR_TARGET)
 
 

 

 

 

####  ERR::SCRAPE::PROJECT\_QUOTA\_LIMIT\_REACHED [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::PROJECT_QUOTA_LIMIT_REACHED) 

The limit set to the current project has been reached

 

- **Retryable:** Yes
- **HTTP status code:** `429`
- **Documentation:**
    - [Project Documentation](https://scrapfly.io/docs/project)
    - [Quota Pricing](https://scrapfly.io/pricing)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::PROJECT_QUOTA_LIMIT_REACHED)
 
 

 

 

 

####  ERR::SCRAPE::QUOTA\_LIMIT\_REACHED [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::QUOTA_LIMIT_REACHED) 

You reach your scrape quota plan for the month. You can upgrade your plan if you want increase the quota

 

- **Retryable:** No
- **HTTP status code:** `429`
- **Documentation:**
    - [Project Quota And Usage](https://scrapfly.io/docs/project)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::QUOTA_LIMIT_REACHED)
    - [Upgrade you subscription](https://scrapfly.io/docs/billing#change_plan)
 
 

 

 

 

####  ERR::SCRAPE::SCENARIO\_DEADLINE\_OVERFLOW [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::SCENARIO_DEADLINE_OVERFLOW) 

Submitted scenario would require more than 30s to complete

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Javascript Scenario Documentation](https://scrapfly.io/docs/scrape-api/javascript-scenario)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::SCENARIO_DEADLINE_OVERFLOW)
    - [Timeout Documentation](https://scrapfly.io/docs/scrape-api/understand-timeout)
 
 

 

 

 

####  ERR::SCRAPE::SCENARIO\_EXECUTION [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::SCENARIO_EXECUTION) 

Javascript Scenario Failed

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::SCENARIO_EXECUTION)
 
 

 

 

 

####  ERR::SCRAPE::SCENARIO\_TIMEOUT [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::SCENARIO_TIMEOUT) 

Javascript Scenario Timeout

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [Javascript Scenario Documentation](https://scrapfly.io/docs/scrape-api/javascript-scenario)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::SCENARIO_EXECUTION)
    - [Timeout Documentation](https://scrapfly.io/docs/scrape-api/understand-timeout)
 
 

 

 

 

####  ERR::SCRAPE::SSL\_ERROR [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::SSL_ERROR) 

Upstream website have SSL error

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::SSL_ERROR)
 
 

 

 

 

####  ERR::SCRAPE::TOO\_MANY\_CONCURRENT\_REQUEST [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::TOO_MANY_CONCURRENT_REQUEST) 

You reach concurrent limit of scrape request of your current plan or project if you set a concurrent limit at project level

 

- **Retryable:** Yes
- **HTTP status code:** `429`
- **Documentation:**
    - [Quota Pricing](https://scrapfly.io/pricing)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::TOO_MANY_CONCURRENT_REQUEST)
 
 

 

 

 

####  ERR::SCRAPE::UNABLE\_TO\_TAKE\_SCREENSHOT [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::UNABLE_TO_TAKE_SCREENSHOT) 

Unable to take screenshot

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::UNABLE_TO_TAKE_SCREENSHOT)
 
 

 

 

 

####  ERR::SCRAPE::UPSTREAM\_TIMEOUT [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::UPSTREAM_TIMEOUT) 

The website you target made too much time to response

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::UPSTREAM_TIMEOUT)
 
 

 

 

 

####  ERR::SCRAPE::UPSTREAM\_WEBSITE\_ERROR [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SCRAPE::UPSTREAM_WEBSITE_ERROR) 

The website you tried to scrape have configuration or malformed response

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SCRAPE::UPSTREAM_WEBSITE_ERROR)
 
 

 

 

 

### Proxy Errors

####  ERR::PROXY::POOL\_NOT\_AVAILABLE\_FOR\_TARGET [  ](https://scrapfly.home/docs/scrape-api/error/ERR::PROXY::POOL_NOT_AVAILABLE_FOR_TARGET) 

The desired proxy pool is not available for the given domain - mostly well known protected domain which require at least residential networks

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [API Usage](https://scrapfly.io/docs/scrape-api/getting-started#api_param_proxy_pool)
    - [Proxy Documentation](https://scrapfly.io/docs/scrape-api/proxy)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::PROXY::POOL_NOT_AVAILABLE_FOR_TARGET)
 
 

 

 

 

####  ERR::PROXY::POOL\_NOT\_FOUND [  ](https://scrapfly.home/docs/scrape-api/error/ERR::PROXY::POOL_NOT_FOUND) 

Provided Proxy Pool Name do not exists

 

- **Retryable:** No
- **HTTP status code:** `400`
- **Documentation:**
    - [API Usage](https://scrapfly.io/docs/scrape-api/getting-started#api_param_proxy_pool)
    - [Proxy Documentation](https://scrapfly.io/docs/scrape-api/proxy)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::PROXY::POOL_NOT_FOUND)
 
 

 

 

 

####  ERR::PROXY::POOL\_UNAVAILABLE\_COUNTRY [  ](https://scrapfly.home/docs/scrape-api/error/ERR::PROXY::POOL_UNAVAILABLE_COUNTRY) 

Country not available for given proxy pool

 

- **Retryable:** No
- **HTTP status code:** `400`
- **Documentation:**
    - [API Usage](https://scrapfly.io/docs/scrape-api/getting-started#api_param_proxy_pool)
    - [Proxy Documentation](https://scrapfly.io/docs/scrape-api/proxy)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::PROXY::POOL_UNAVAILABLE_COUNTRY)
 
 

 

 

 

####  ERR::PROXY::RESOURCES\_SATURATION [  ](https://scrapfly.home/docs/scrape-api/error/ERR::PROXY::RESOURCES_SATURATION) 

Proxy are saturated for the desired country, you can try on other countries. They will come back as soon as possible

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::PROXY::RESOURCES_SATURATION)
 
 

 

 

 

####  ERR::PROXY::TIMEOUT [  ](https://scrapfly.home/docs/scrape-api/error/ERR::PROXY::TIMEOUT) 

Proxy connection or website was too slow and timeout

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::PROXY::TIMEOUT)
    - [Timeout Documentation](https://scrapfly.io/docs/scrape-api/understand-timeout)
 
 

 

 

 

####  ERR::PROXY::UNAVAILABLE [  ](https://scrapfly.home/docs/scrape-api/error/ERR::PROXY::UNAVAILABLE) 

Proxy is unavailable - The domain (mainly gov website) is restricted, You are using session feature and the proxy is unreachable at the moment

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [API Usage](https://scrapfly.io/docs/scrape-api/getting-started#api_param_proxy_pool)
    - [Proxy Documentation](https://scrapfly.io/docs/scrape-api/proxy)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::PROXY::UNAVAILABLE)
 
 

 

 

 

### Throttle Errors

####  ERR::THROTTLE::MAX\_API\_CREDIT\_BUDGET\_EXCEEDED [  ](https://scrapfly.home/docs/scrape-api/error/ERR::THROTTLE::MAX_API_CREDIT_BUDGET_EXCEEDED) 

Your scrape request has been throttled. API Credit Budget reached. If it's not expected, please check your throttle configuration for the given project and env.

 

- **Retryable:** Yes
- **HTTP status code:** `429`
- **Documentation:**
    - [API Documentation](https://scrapfly.io/docs/scrape-api/getting-started#api_param_cost_budget)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::THROTTLE::MAX_API_CREDIT_BUDGET_EXCEEDED)
 
 

 

 

 

####  ERR::THROTTLE::MAX\_CONCURRENT\_REQUEST\_EXCEEDED [  ](https://scrapfly.home/docs/scrape-api/error/ERR::THROTTLE::MAX_CONCURRENT_REQUEST_EXCEEDED) 

Your scrape request has been throttled. Too many concurrent access to the upstream. If it's not expected, please check your throttle configuration for the given project and env.

 

- **Retryable:** Yes
- **HTTP status code:** `429`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::THROTTLE::MAX_CONCURRENT_REQUEST_EXCEEDED)
    - [Throttler Documentation](https://scrapfly.io/docs/throttling)
 
 

 

 

 

####  ERR::THROTTLE::MAX\_REQUEST\_RATE\_EXCEEDED [  ](https://scrapfly.home/docs/scrape-api/error/ERR::THROTTLE::MAX_REQUEST_RATE_EXCEEDED) 

Your scrape request as been throttle. Too much request during the 1m window. If it's not expected, please check your throttle configuration for the given project and env

 

- **Retryable:** Yes
- **HTTP status code:** `429`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::THROTTLE::MAX_REQUEST_RATE_EXCEEDED)
    - [Throttler Documentation](https://scrapfly.io/docs/throttling)
 
 

 

 

 

### Anti Scraping Protection (ASP) Errors

####  ERR::ASP::CAPTCHA\_ERROR [  ](https://scrapfly.home/docs/scrape-api/error/ERR::ASP::CAPTCHA_ERROR) 

Something wrong happened with the captcha. We will figure out to fix the problem as soon as possible

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::ASP::CAPTCHA_ERROR)
 
 

 

 

 

####  ERR::ASP::CAPTCHA\_TIMEOUT [  ](https://scrapfly.home/docs/scrape-api/error/ERR::ASP::CAPTCHA_TIMEOUT) 

The budgeted time to solve the captcha is reached

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::ASP::CAPTCHA_TIMEOUT)
 
 

 

 

 

####  ERR::ASP::SHIELD\_ERROR [  ](https://scrapfly.home/docs/scrape-api/error/ERR::ASP::SHIELD_ERROR) 

The ASP encounter an unexpected problem. We will fix it as soon as possible. Our team has been alerted

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Checkout ASP documentation](https://scrapfly.io/docs/scrape-api/anti-scraping-protection#maximize_success_rate)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::ASP::SHIELD_ERROR)
 
 

 

 

 

####  ERR::ASP::SHIELD\_EXPIRED [  ](https://scrapfly.home/docs/scrape-api/error/ERR::ASP::SHIELD_EXPIRED) 

The ASP shield previously set is expired, you must retry.

 

- **Retryable:** Yes
- **HTTP status code:** `422`
 
 

 

 

 

####  ERR::ASP::SHIELD\_NOT\_ELIGIBLE [  ](https://scrapfly.home/docs/scrape-api/error/ERR::ASP::SHIELD_NOT_ELIGIBLE) 

The feature requested is not eligible while using the ASP for the given protection/target

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::ASP::SHIELD_NOT_ELIGIBLE)
 
 

 

 

 

####  ERR::ASP::SHIELD\_PROTECTION\_FAILED [  ](https://scrapfly.home/docs/scrape-api/error/ERR::ASP::SHIELD_PROTECTION_FAILED) 

The ASP shield failed to solve the challenge against the anti scrapping protection

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [Checkout ASP documentation](https://scrapfly.io/docs/scrape-api/anti-scraping-protection#maximize_success_rate)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::ASP::SHIELD_PROTECTION_FAILED)
 
 

 

 

 

####  ERR::ASP::TIMEOUT [  ](https://scrapfly.home/docs/scrape-api/error/ERR::ASP::TIMEOUT) 

The ASP made too much time to solve or respond

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [Checkout ASP documentation](https://scrapfly.io/docs/scrape-api/anti-scraping-protection)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::ASP::TIMEOUT)
 
 

 

 

 

####  ERR::ASP::UNABLE\_TO\_SOLVE\_CAPTCHA [  ](https://scrapfly.home/docs/scrape-api/error/ERR::ASP::UNABLE_TO_SOLVE_CAPTCHA) 

Despite our effort, we were unable to solve the captcha. It can happened sporadically, please retry

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::ASP::UNABLE_TO_SOLVE_CAPTCHA)
 
 

 

 

 

####  ERR::ASP::UPSTREAM\_UNEXPECTED\_RESPONSE [  ](https://scrapfly.home/docs/scrape-api/error/ERR::ASP::UPSTREAM_UNEXPECTED_RESPONSE) 

The response given by the upstream after challenge resolution is not expected. Our team has been alerted

 

- **Retryable:** No
- **HTTP status code:** `422`
- **Documentation:**
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::ASP::UPSTREAM_UNEXPECTED_RESPONSE)
 
 

 

 

 

### Webhook Errors

####  ERR::WEBHOOK::DISABLED [  ](https://scrapfly.home/docs/scrape-api/error/ERR::WEBHOOK::DISABLED) 

Given webhook is disabled, please check out your webhook configuration for the current project / env

 

- **Retryable:** No
- **HTTP status code:** `400`
- **Documentation:**
    - [Checkout Webhook Documentation](https://scrapfly.io/docs/scrape-api/webhook)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::WEBHOOK::DISABLED)
 
 

 

 

 

####  ERR::WEBHOOK::ENDPOINT\_UNREACHABLE [  ](https://scrapfly.home/docs/scrape-api/error/ERR::WEBHOOK::ENDPOINT_UNREACHABLE) 

We were not able to contact your endpoint

 

- **Retryable:** Yes
- **HTTP status code:** `422`
- **Documentation:**
    - [Checkout Webhook Documentation](https://scrapfly.io/docs/scrape-api/webhook)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::WEBHOOK::ENDPOINT_UNREACHABLE)
 
 

 

 

 

####  ERR::WEBHOOK::QUEUE\_FULL [  ](https://scrapfly.home/docs/scrape-api/error/ERR::WEBHOOK::QUEUE_FULL) 

You reach the maximum concurrency limit

 

- **Retryable:** Yes
- **HTTP status code:** `429`
- **Documentation:**
    - [Checkout Webhook Documentation](https://scrapfly.io/docs/scrape-api/webhook)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::WEBHOOK::MAX_CONCURRENCY_REACHED)
 
 

 

 

 

####  ERR::WEBHOOK::MAX\_RETRY [  ](https://scrapfly.home/docs/scrape-api/error/ERR::WEBHOOK::MAX_RETRY) 

Maximum retry exceeded on your webhook

 

- **Retryable:** No
- **HTTP status code:** `429`
- **Documentation:**
    - [Checkout Webhook Documentation](https://scrapfly.io/docs/scrape-api/webhook)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::WEBHOOK::MAX_RETRY)
 
 

 

 

 

####  ERR::WEBHOOK::NOT\_FOUND [  ](https://scrapfly.home/docs/scrape-api/error/ERR::WEBHOOK::NOT_FOUND) 

Unable to find the given webhook for the current project / env

 

- **Retryable:** No
- **HTTP status code:** `400`
- **Documentation:**
    - [Checkout Webhook Documentation](https://scrapfly.io/docs/scrape-api/webhook)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::WEBHOOK::NOT_FOUND)
 
 

 

 

 

####  ERR::WEBHOOK::QUEUE\_FULL [  ](https://scrapfly.home/docs/scrape-api/error/ERR::WEBHOOK::QUEUE_FULL) 

You reach the limit of scheduled webhook - You must wait pending webhook are processed

 

- **Retryable:** Yes
- **HTTP status code:** `429`
- **Documentation:**
    - [Checkout Webhook Documentation](https://scrapfly.io/docs/scrape-api/webhook)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::WEBHOOK::QUEUE_FULL)
 
 

 

 

 

### Session Errors

####  ERR::SESSION::CONCURRENT\_ACCESS [  ](https://scrapfly.home/docs/scrape-api/error/ERR::SESSION::CONCURRENT_ACCESS) 

Concurrent access to the session has been tried. If your spider run on distributed architecture, the same session name is currently used by another scrape

 

- **Retryable:** Yes
- **HTTP status code:** `429`
- **Documentation:**
    - [Checkout Session Documentation](https://scrapfly.io/docs/scrape-api/session)
    - [Related Error Doc](https://scrapfly.io/docs/scrape-api/error/ERR::SESSION::CONCURRENT_ACCESS)
 
 

 

 

 

 For complete details on each inherited error, see the [Web Scraping API Error Reference](https://scrapfly.home/docs/scrape-api/errors).

## HTTP Status Codes 

 | Status Code | Description |
|---|---|
| `200 OK` | Request successful |
| `201 Created` | Crawler job created successfully |
| `400 Bad Request` | Invalid parameters or configuration |
| `401 Unauthorized` | Invalid or missing API key |
| `403 Forbidden` | API key doesn't have permission for this operation |
| `404 Not Found` | Crawler job UUID not found |
| `422 Request Failed` | Request was valid but execution failed |
| `429 Too Many Requests` | Rate limit or concurrency limit exceeded |
| `500 Server Error` | Internal server error |
| `504 Timeout` | Request timed out |

## Error Response Format 

All error responses include detailed information in a consistent format:

 ```
{
  "error": {
    "code": "CRAWLER_TIMEOUT",
    "message": "Crawler exceeded maximum duration of 3600 seconds",
    "retryable": false,
    "details": {
      "max_duration": 3600,
      "elapsed_duration": 3615,
      "urls_crawled": 847
    }
  }
}
```

 

   

 

 

 

**Error response headers:**

- `X-Scrapfly-Error-Code` - Machine-readable error code
- `X-Scrapfly-Error-Message` - Human-readable error description
- `X-Scrapfly-Error-Retryable` - Whether the operation can be retried
 
## Related Documentation 

- [Web Scraping API Errors (Complete List)](https://scrapfly.home/docs/scrape-api/errors)
- [Crawler API Getting Started](https://scrapfly.home/docs/crawler-api/getting-started)
- [Contact Support](https://scrapfly.home/docs/support)

# Crawler API Troubleshooting

 This guide covers common issues when using the Crawler API and how to resolve them. For API errors and error codes, see the [Errors page](https://scrapfly.home/docs/crawler-api/errors).

  **Pro Tip:** Always check the [monitoring dashboard](https://scrapfly.home/docs/monitoring) to inspect crawler status, failed URLs, and detailed error information. 

## Crawler Not Discovering URLs 

 If your crawler isn't discovering the URLs you expect, this is usually a path filtering issue. Here's how to diagnose and fix it:

### Check Path Filters

The most common cause is overly restrictive `include_only_paths` or `exclude_paths` filters.

##### Debugging Steps:

1. **Test without filters first** - Run a small crawl (e.g., `max_pages=10`) without any path filters to verify URL discovery works
2. **Add filters incrementally** - Start with broad patterns and gradually make them more specific
3. **Check pattern syntax** - Ensure patterns use correct wildcards: 
    - `*` matches any characters within a path segment
    - `**` matches across multiple path segments
    - Example: `/products/**` matches all product pages
4. **Review crawled URLs** - Use `/crawl/{uuid}/urls` endpoint to see which URLs were discovered
 
 

 

### Enable Sitemaps

 If your target website has a sitemap, enable `use_sitemaps=true` for better URL discovery. Sitemaps provide a comprehensive list of URLs that might not be linked from the homepage.

### Verify Starting URL

 Ensure your starting URL is accessible and contains the links you expect. Test it manually in a browser to verify.

## Crawler Not Following External Links 

 If you expect the crawler to follow links to external domains but it's not happening, here's what to check:

##### Common Issues:

1. **Missing `follow_external_links=true`** - By default, the crawler stays within the starting domain. You must explicitly enable external link following.
2. **Too restrictive `allowed_external_domains`** - If you specify this parameter, ONLY domains matching the patterns will be followed. Check your fnmatch patterns (e.g., `*.example.com`).
3. **External pages not being re-crawled** - This is expected behavior! External pages are scraped (content extracted, credits consumed), but their links are NOT followed. The crawler only goes "one hop" into external domains.
 
 

 

### Understanding External Link Behavior

  **Important: External Domain Crawling** When `follow_external_links=true`:

- **With no `allowed_external_domains`:** ANY external domain is followed (except social media)
- **With `allowed_external_domains`:** Only matching domains are followed (supports fnmatch patterns)
 
 **Key limitation:** External pages ARE scraped but their outbound links are NOT followed. 
 *Example:* Crawling `example.com` → finds link to `wikipedia.org/page1` → scrapes wikipedia.org/page1 → does NOT follow links from wikipedia.org/page1

 

## High Failure Rate 

 If many pages are failing to crawl, check the error codes to identify the root cause:

 ```
# Get all failed URLs with error details
curl https://api.scrapfly.home/crawl/{uuid}/urls?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&status=failed
```

 

   

 

 

 

### Common Causes and Solutions

 | Error Pattern | Solution |
|---|---|
| [`ERR::ASP::SHIELD_PROTECTION_FAILED`](https://scrapfly.home/docs/crawler-api/error/ERR::ASP::SHIELD_PROTECTION_FAILED) | Enable `asp=true` to bypass anti-bot protection  This activates Anti-Scraping Protection |
| [`ERR::THROTTLE::MAX_CONCURRENT_REQUEST_EXCEEDED`](https://scrapfly.home/docs/crawler-api/error/ERR::THROTTLE::MAX_CONCURRENT_REQUEST_EXCEEDED) | Reduce `max_concurrency` to avoid overwhelming the target server  Try starting with max\_concurrency=2 or 3 |
| [`ERR::SCRAPE::UPSTREAM_TIMEOUT`](https://scrapfly.home/docs/crawler-api/error/ERR::SCRAPE::UPSTREAM_TIMEOUT) | Increase `timeout` parameter or reduce `rendering_wait`  Default timeout is 30 seconds, increase if needed |
| [`ERR::SCRAPE::BAD_UPSTREAM_RESPONSE`](https://scrapfly.home/docs/crawler-api/error/ERR::SCRAPE::BAD_UPSTREAM_RESPONSE) | Verify the target domain is accessible and DNS is working correctly  Check if the website is online |

 For complete error definitions and solutions, see the [Crawler API Errors page](https://scrapfly.home/docs/crawler-api/errors).

## Crawler Taking Too Long 

 Crawler performance depends on several factors. Here's how to optimize speed:

### Increase Concurrency

 The `max_concurrency` parameter controls how many pages are crawled simultaneously. Higher values = faster crawls, but stay within your account limits.

 **Recommended values:**- Small sites (< 100 pages): `max_concurrency=5`
- Medium sites (100-1000 pages): `max_concurrency=10`
- Large sites (1000+ pages): `max_concurrency=20+` (if account allows)
 
 

 

### Optimize Feature Usage

 | Feature | Performance Impact | When to Disable |
|---|---|---|
| `asp` | **5× slower** | Disable if the site doesn't have anti-bot protection |
| `rendering_wait` | Adds delay per page | Reduce or remove if pages load quickly |
| `proxy_pool=public_residential_pool` | Slower than datacenter | Use datacenter proxies when residential IPs aren't required |

### Set Time Limits

 Use `max_duration` to prevent indefinite crawls. The crawler will stop gracefully when this limit is reached:

 ```
{
  "url": "https://example.com",
  "max_duration": 3600,
  "max_pages": 1000
}
```

 

   

 

 

 

This crawler will stop after 1 hour or 1000 pages, whichever comes first

## Budget Control Issues 

 Controlling costs is critical when crawling large websites. Use these strategies to stay within budget:

### Set Credit Limits

 Use `max_api_credit` to automatically stop crawling when your budget is reached:

 ```
{
  "url": "https://example.com",
  "max_api_credit": 1000,
  "max_pages": 10000
}
```

 

   

 

 

 

This crawler will stop after spending 1000 credits or 10000 pages, whichever comes first

### Monitor Costs in Real-Time

 Check the crawler status endpoint to see current credit usage:

 ```
curl https://api.scrapfly.home/crawl/{uuid}/status?key=scp-live-d8ac176c2f9d48b993b58675bdf71615
```

 

   

 

 

 

 The response includes `api_credit_used` showing total credits consumed so far.

### Reduce Per-Page Costs

- **Disable ASP** if not needed - saves significant credits per page
- **Use datacenter proxies** instead of residential when possible
- **Enable caching** for re-crawls to avoid re-scraping unchanged pages
- **Use stricter path filtering** to crawl only necessary pages
- **Choose efficient formats** - markdown and text are cheaper than full HTML
 
 For detailed pricing information, see [Crawler API Billing](https://scrapfly.home/docs/crawler-api/billing).

## Debugging Tips 

### Check Crawler Status

 The status endpoint provides real-time information about your crawler:

 ```
curl https://api.scrapfly.home/crawl/{uuid}/status?key=scp-live-d8ac176c2f9d48b993b58675bdf71615
```

 

   

 

 

 

**Key fields to monitor:**

- `status` - RUNNING, COMPLETED, FAILED, CANCELLED
- `urls_discovered` - Total URLs found by the crawler
- `urls_crawled` - Total URLs successfully crawled
- `urls_failed` - Total URLs that failed to crawl
- `api_credit_used` - Credits consumed so far
 
### Inspect Failed URLs

 Get detailed error information for failed pages:

 ```
curl https://api.scrapfly.home/crawl/{uuid}/urls?key=scp-live-d8ac176c2f9d48b993b58675bdf71615&status=failed
```

 

   

 

 

 

### Test with Small Crawls First

 Before running a large crawl, test with `max_pages=10` to:

- Verify path filters are working correctly
- Check that target pages are accessible
- Confirm content extraction is working
- Estimate costs for the full crawl
 
## Getting Help 

 If you're still experiencing issues after trying these solutions:

- Check the [monitoring dashboard](https://scrapfly.home/docs/monitoring) for detailed logs
- Review the [error codes reference](https://scrapfly.home/docs/crawler-api/errors) for specific errors
- Contact [support](https://scrapfly.home/docs/support) with your crawler UUID for personalized assistance
 
## Related Documentation 

- [Crawler API Getting Started](https://scrapfly.home/docs/crawler-api/getting-started)
- [Crawler API Errors](https://scrapfly.home/docs/crawler-api/errors)
- [Crawler API Billing](https://scrapfly.home/docs/crawler-api/billing)
- [Monitoring Dashboard](https://scrapfly.home/docs/monitoring)

