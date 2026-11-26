# Scrapfly SDK

## Installation

`pip install scrapfly-sdk`

You can also install extra dependencies

* `pip install "scrapfly-sdk[speedups]"` for brotli compression and msgpack serialization
* `pip install "scrapfly-sdk[parser]"` for the built-in HTML parser (lxml, beautifulsoup4, extruct)
* `pip install "scrapfly-sdk[scrapy]"` for scrapy integration
* `pip install "scrapfly-sdk[browser]"` for the playwright based cloud browser helpers
* `pip install "scrapfly-sdk[browser-use]"` for browser-use agent integration
* `pip install "scrapfly-sdk[webhook-server]"` for a native webhook server using flask
* `pip install "scrapfly-sdk[concurrency]"` kept for compatibility, concurrency needs no extra dependency
* `pip install "scrapfly-sdk[all]"` Everything!

The `speedups` and `webhook-server` extras install `brotli` (CPython) or `brotlicffi`. Up to 0.12 they installed the
archived `brotlipy`, which pip does not remove on upgrade and which shadows `brotli` under the same import name:
run `pip uninstall brotlipy` before upgrading.

For use of built-in HTML parser (via `ScrapeApiResponse.selector` property) additional requirement of either [parsel](https://pypi.org/project/parsel/) or [scrapy](https://pypi.org/project/Scrapy/) is required.

For reference of usage or examples, please checkout the folder `/examples` in this repository.

This SDK cover the following Scrapfly API endpoints:

* [Web Scraping API](https://scrapfly.io/docs/onboarding#web-scraping-api)
* [Extraction API](https://scrapfly.io/docs/onboarding#extraction-api)
* [Screenshot API](https://scrapfly.io/docs/onboarding#screenshot-api)

## Async client

Added in 1.0.0: `AsyncScrapflyClient` has every method of `ScrapflyClient`, as coroutines, and the streamed ones
(`scrape_batch`, `crawl_prompt`) as async iterators. Open it with `async with` to reuse connections across calls.

```python
import asyncio
from scrapfly import AsyncScrapflyClient, ScrapeConfig

async def main():
    async with AsyncScrapflyClient(key='__API_KEY__') as scrapfly:
        api_response = await scrapfly.scrape(ScrapeConfig(url='https://web-scraping.dev/product/1'))
        print(api_response.content)

        configs = [ScrapeConfig(url=f'https://web-scraping.dev/product/{n}') for n in range(1, 6)]
        async for result in scrapfly.concurrent_scrape(configs, concurrency=5):
            print(result)

asyncio.run(main())
```

Up to 0.12, `ScrapflyClient` runs a call as a coroutine with `async_scrape` (and `async_screenshot`,
`async_extraction`), and `concurrent_scrape` is an async generator of it. This works on 1.0.0 too:

```python
import asyncio
from scrapfly import ScrapflyClient, ScrapeConfig

async def main():
    scrapfly = ScrapflyClient(key='__API_KEY__')
    api_response = await scrapfly.async_scrape(ScrapeConfig(url='https://web-scraping.dev/product/1'))
    print(api_response.content)

    configs = [ScrapeConfig(url=f'https://web-scraping.dev/product/{n}') for n in range(1, 6)]
    async for result in scrapfly.concurrent_scrape(configs, concurrency=5):
        print(result)

asyncio.run(main())
```

## Proxy pools

`proxy_pool` picks the proxy pool of the Web Scraping API and the crawler:

| Constant | Value | What it runs |
|---|---|---|
| `ScrapeConfig.PUBLIC_DATACENTER_POOL` | `'public_datacenter_pool'` | datacenter proxies, the default |
| `ScrapeConfig.PUBLIC_RESIDENTIAL_POOL` | `'public_residential_pool'` | residential proxies |
| `ScrapeConfig.PUBLIC_TOR_POOL` | `'public_tor_pool'` | the Tor network, the only pool that reaches `.onion` sites |

```python
from scrapfly import CrawlerConfig, ScrapeConfig

scrape_config = ScrapeConfig(url='https://web-scraping.dev/product/1', proxy_pool=ScrapeConfig.PUBLIC_RESIDENTIAL_POOL)
crawler_config = CrawlerConfig(url='https://web-scraping.dev/', proxy_pool=ScrapeConfig.PUBLIC_RESIDENTIAL_POOL)
```

Without `proxy_pool` the SDK sends none. `ScrapeConfig.BASIC`, `ScrapeConfig.UNBLOCKER`,
`ScrapeConfig.UNBLOCKER_ULTRA` and `ScrapeConfig.AUTO` (added in 1.0.0) name pools the API does not
accept yet: a request naming one fails with `ERR::PROXY::POOL_NOT_FOUND`. The Screenshot API picks its
pool itself and ignores the `proxy_pool` of `ScreenshotConfig` (added in 1.0.0). The Cloud Browser keeps
its own pools, `datacenter`, `residential`, `tor` and `byop`.

## Unblocker

`unblocker` turns on the anti-bot bypass. It defeats blocking and antibot solutions such as
Cloudflare, DataDome, PerimeterX or Akamai.

```python
from scrapfly import ScrapeConfig, ScrapflyClient

scrapfly = ScrapflyClient(key='__API_KEY__')

api_response = scrapfly.scrape(ScrapeConfig(
    url='https://web-scraping.dev/product/1',
    unblocker=True
))
```

It is available on the crawler too:

```python
from scrapfly import CrawlerConfig

config = CrawlerConfig(url='https://web-scraping.dev/', unblocker=True)
```

### `asp` is the deprecated alias

`unblocker` was previously named `asp`. `asp` keeps working: existing code needs no change.

```python
ScrapeConfig(url='https://web-scraping.dev/product/1', asp=True)  # same setting as unblocker=True
```

When both names are supplied, an explicitly supplied `asp` wins; `unblocker` applies only when
`asp` was not given. `False` on either name turns the feature off. `None` counts as *not*
supplied — the same reading the API takes of a JSON `null` — so forwarding an optional through
(`ScrapeConfig(**{**opts, 'asp': opts.get('asp')})`) cannot silently veto an explicit
`unblocker=True`.

One thing deliberately keeps the old name: the `asp` key of the API request itself. The error
class also keeps it, because the API status it carries is still `ERR::ASP::*` — but
`ScrapflyUnblockerError` is an alias for the same class, so either name works in `except`:

```python
from scrapfly import ScrapflyUnblockerError  # the same class as ScrapflyAspError
```

## Timeouts and retries

A call waits for its answer up to its read timeout. The client sets those of a scrape,
`web_scraping_api_read_timeout` (160 s by default), of a screenshot, `screenshot_api_read_timeout` (130 s), and of an
extraction, `extraction_api_read_timeout` (165 s).

```python
from scrapfly import ScrapflyClient

scrapfly = ScrapflyClient(key='__API_KEY__', web_scraping_api_read_timeout=200)
```

- `scrape()`, `screenshot()`, `extract()`, `start_crawl()` and `crawl_search()` are sent once when their read
  times out, and the timeout is raised at once: `requests.ReadTimeout` from `ScrapflyClient` (a
  `requests.ConnectionError` when the body stopped arriving), `httpx.ReadTimeout` from `AsyncScrapflyClient`.
  `ScrapflyMiddleware` does not retry it either.
- When the connection cannot be made or drops before the answer, they are sent again with an exponential backoff,
  up to 5 times in all.
- The reads of a crawl (`get_crawl_status()`, `get_crawl_urls()`, `get_crawl_contents()`, `get_crawl_artifact()`,
  `crawl_refresh_history()`) are sent again on a read timeout too.

## Integrations  

Scrapfly Python SDKs are integrated with [LlamaIndex](https://www.llamaindex.ai/) and [LangChain](https://www.langchain.com/). Both framework allows training Large Language Models (LLMs) using augmented context.

This augmented context is approached by training LLMs on top of private or domain-specific data for common use cases:
- Question-Answering Chatbots (commonly referred to as RAG systems, which stands for "Retrieval-Augmented Generation")
- Document Understanding and Extraction
- Autonomous Agents that can perform research and take actions
<br>  

In the context of web scraping, web page data can be extracted as Text or Markdown using [Scrapfly's format feature](https://scrapfly.io/docs/scrape-api/specification#api_param_format) to train LLMs with the scraped data.

### LlamaIndex

#### Installation
Install `llama-index`, `llama-index-readers-web`, and `scrapfly-sdk` using pip:
```shell
pip install llama-index llama-index-readers-web scrapfly-sdk
```

#### Usage
Scrapfly is available at LlamaIndex as a [data connector](https://docs.llamaindex.ai/en/stable/module_guides/loading/connector/), known as a `Reader`. This reader is used to gather a web page data into a `Document` representation, which can be used with the LLM directly. Below is an example of building a RAG system using LlamaIndex and scraped data. See the [LlamaIndex use cases](https://docs.llamaindex.ai/en/stable/use_cases/) for more.
```python
import os

from llama_index.readers.web import ScrapflyReader
from llama_index.core import VectorStoreIndex

# Initiate ScrapflyReader with your Scrapfly API key
scrapfly_reader = ScrapflyReader(
    api_key="Your Scrapfly API key",  # Get your API key from https://www.scrapfly.io/
    ignore_scrape_failures=True,  # Ignore unprocessable web pages and log their exceptions
)

# Load documents from URLs as markdown
documents = scrapfly_reader.load_data(
    urls=["https://web-scraping.dev/products"]
)

# After creating the documents, train them with an LLM
# LlamaIndex uses OpenAI default, other options can be found at the examples direcotry: 
# https://docs.llamaindex.ai/en/stable/examples/llm/openai/

# Add your OpenAI key (a paid subscription must exist) from: https://platform.openai.com/api-keys/
os.environ['OPENAI_API_KEY'] = "Your OpenAI Key"
index = VectorStoreIndex.from_documents(documents)
query_engine = index.as_query_engine()

response = query_engine.query("What is the flavor of the dark energy potion?")
print(response)
"The flavor of the dark energy potion is bold cherry cola."
```

The `load_data` function accepts a ScrapeConfig object to use the desired Scrapfly API parameters:
```python
from llama_index.readers.web import ScrapflyReader

# Initiate ScrapflyReader with your ScrapFly API key
scrapfly_reader = ScrapflyReader(
    api_key="Your Scrapfly API key",  # Get your API key from https://www.scrapfly.io/
    ignore_scrape_failures=True,  # Ignore unprocessable web pages and log their exceptions
)

scrapfly_scrape_config = {
    "unblocker": True,  # Bypass scraping blocking and antibot solutions, like Cloudflare (formerly "asp")
    "render_js": True,  # Enable JavaScript rendering with a cloud headless browser
    "proxy_pool": "public_residential_pool",  # Select a proxy pool (datacenter or residential)
    "country": "us",  # Select a proxy location
    "auto_scroll": True,  # Auto scroll the page
    "js": "",  # Execute custom JavaScript code by the headless browser
}

# Load documents from URLs as markdown
documents = scrapfly_reader.load_data(
    urls=["https://web-scraping.dev/products"],
    scrape_config=scrapfly_scrape_config,  # Pass the scrape config
    scrape_format="markdown",  # The scrape result format, either `markdown`(default) or `text`
)
```

### LangChain

#### Installation
Install `langchain`, `langchain-community`, and `scrapfly-sdk` using pip:
```shell
pip install langchain langchain-community scrapfly-sdk
```

#### Usage
Scrapfly is available at LangChain as a [document loader](https://python.langchain.com/v0.2/docs/concepts/#document-loaders), known as a `Loader`. This reader is used to gather a web page data into `Document` representation, which canbe used with the LLM after a few operations. Below is an example of building a RAG system with LangChain using scraped data, see [LangChain tutorials](https://python.langchain.com/v0.2/docs/tutorials/) for further use cases.
```python
import os

from langchain import hub # pip install langchainhub
from langchain_chroma import Chroma # pip install langchain_chroma
from langchain_core.runnables import RunnablePassthrough
from langchain_core.output_parsers import StrOutputParser
from langchain_openai import OpenAIEmbeddings, ChatOpenAI # pip install langchain_openai
from langchain_text_splitters import RecursiveCharacterTextSplitter # pip install langchain_text_splitters
from langchain_community.document_loaders import ScrapflyLoader


scrapfly_loader = ScrapflyLoader(
    ["https://web-scraping.dev/products"],
    api_key="Your Scrapfly API key",  # Get your API key from https://www.scrapfly.io/
    continue_on_failure=True,  # Ignore unprocessable web pages and log their exceptions
)

# Load documents from URLs as markdown
documents = scrapfly_loader.load()

# This example uses OpenAI. For more see: https://python.langchain.com/v0.2/docs/integrations/platforms/
os.environ["OPENAI_API_KEY"] = "Your OpenAI key"

# Create a retriever
text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
splits = text_splitter.split_documents(documents)
vectorstore = Chroma.from_documents(documents=splits, embedding=OpenAIEmbeddings())
retriever = vectorstore.as_retriever()

def format_docs(docs):
    return "\n\n".join(doc.page_content for doc in docs)

model = ChatOpenAI()
prompt = hub.pull("rlm/rag-prompt")

rag_chain = (
    {"context": retriever | format_docs, "question": RunnablePassthrough()}
    | prompt
    | model
    | StrOutputParser()
)

response = rag_chain.invoke("What is the flavor of the dark energy potion?")
print(response)
"The flavor of the Dark Energy Potion is bold cherry cola."
```

To use the full Scrapfly features with LangChain, pass a ScrapeConfig object to the `ScrapflyLoader`:
```python
from langchain_community.document_loaders import ScrapflyLoader

scrapfly_scrape_config = {
    "unblocker": True,  # Bypass scraping blocking and antibot solutions, like Cloudflare (formerly "asp")
    "render_js": True,  # Enable JavaScript rendering with a cloud headless browser
    "proxy_pool": "public_residential_pool",  # Select a proxy pool (datacenter or residential)
    "country": "us",  # Select a proxy location
    "auto_scroll": True,  # Auto scroll the page
    "js": "",  # Execute custom JavaScript code by the headless browser
}

scrapfly_loader = ScrapflyLoader(
    ["https://web-scraping.dev/products"],
    api_key="Your Scrapfly API key",  # Get your API key from https://www.scrapfly.io/
    continue_on_failure=True,  # Ignore unprocessable web pages and log their exceptions
    scrape_config=scrapfly_scrape_config,  # Pass the scrape_config object
    scrape_format="markdown",  # The scrape result format, either `markdown`(default) or `text`
)

# Load documents from URLs as markdown
documents = scrapfly_loader.load()
print(documents)
```
## Get Your API Key

You can create a free account on [Scrapfly](https://scrapfly.io/register) to get your API Key.

* [Usage](https://scrapfly.io/docs/sdk/python)
* [Python API](https://scrapfly.github.io/python-scrapfly/scrapfly)
* [Open API 3 Spec](https://scrapfly.io/docs/openapi#get-/scrape) 
* [Scrapy Integration](https://scrapfly.io/docs/sdk/scrapy)

## Migration

### Migrate from 0.7.x to 0.8

asyncio-pool dependency has been dropped

`scrapfly.concurrent_scrape` is now an async generator. If the concurrency is `None` or not defined, the max concurrency allowed by
your current subscription is used.

```python
    async for result in scrapfly.concurrent_scrape(concurrency=10, scrape_configs=[ScrapeConfig(...), ...]):
        print(result)
```

brotli args is deprecated and will be removed in the next minor. There is not benefit in most of case
versus gzip regarding and size and use more CPU.

### What's new

### 0.8.x

* Better error log
* Async/Improvement for concurrent scrape with asyncio
* Scrapy media pipeline are now supported out of the box



