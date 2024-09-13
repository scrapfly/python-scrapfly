# Scrapfly SDK

## Installation

`pip install scrapfly-sdk`

You can also install extra dependencies

* `pip install "scrapfly-sdk[seepdup]"` for performance improvement
* `pip install "scrapfly-sdk[concurrency]"` for concurrency out of the box (asyncio / thread)
* `pip install "scrapfly-sdk[scrapy]"` for scrapy integration
* `pip install "scrapfly-sdk[all]"` Everything!

For use of built-in HTML parser (via `ScrapeApiResponse.selector` property) additional requirement of either [parsel](https://pypi.org/project/parsel/) or [scrapy](https://pypi.org/project/Scrapy/) is required.

For reference of usage or examples, please checkout the folder `/examples` in this repository.

This SDK cover the following Scrapfly API endpoints:

* [Web Scraping API](https://scrapfly.io/docs/onboarding#web-scraping-api)
* [Extraction API](https://scrapfly.io/docs/onboarding#extraction-api)
* [Screenshot API](https://scrapfly.io/docs/onboarding#screenshot-api)

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
    "asp": True,  # Bypass scraping blocking and antibot solutions, like Cloudflare
    "render_js": True,  # Enable JavaScript rendering with a cloud headless browser
    "proxy_pool": "public_residential_pool",  # Select a proxy pool (datacenter or residnetial)
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
    "asp": True,  # Bypass scraping blocking and antibot solutions, like Cloudflare
    "render_js": True,  # Enable JavaScript rendering with a cloud headless browser
    "proxy_pool": "public_residential_pool",  # Select a proxy pool (datacenter or residnetial)
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
    async for result in scrapfly.concurrent_scrape(concurrency=10, scrape_configs=[ScrapConfig(...), ...]):
        print(result)
```

brotli args is deprecated and will be removed in the next minor. There is not benefit in most of case
versus gzip regarding and size and use more CPU.

### What's new

### 0.8.x

* Better error log
* Async/Improvement for concurrent scrape with asyncio
* Scrapy media pipeline are now supported out of the box



