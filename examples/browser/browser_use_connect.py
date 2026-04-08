"""
Connect Browser Use AI agent to Scrapfly Cloud Browser.

Browser Use uses the CDP protocol to control remote browsers.
Note: The initial connection may trigger a WebSocket reconnection - this is normal
and handled automatically by browser-use's reconnection logic.

Requirements:
  - Python 3.11+
  - pip install browser-use scrapfly-sdk langchain-openai
  - OPENAI_API_KEY environment variable set
"""
import asyncio
from scrapfly import ScrapflyClient, BrowserConfig
from langchain_openai import ChatOpenAI
from browser_use import Agent, Browser, BrowserProfile

scrapfly = ScrapflyClient(
    key='YOUR_API_KEY',
)

# Generate the Cloud Browser CDP endpoint
config = BrowserConfig(
    proxy_pool='datacenter',
    os='linux',
)
cdp_url = scrapfly.cloud_browser(config)


async def run_agent():
    # Connect to Cloud Browser via CDP
    browser = Browser(
        browser_profile=BrowserProfile(
            cdp_url=cdp_url,
        )
    )

    # Create AI agent with natural language task
    agent = Agent(
        task=(
            "Go to https://web-scraping.dev/products and extract all product names and prices. "
            "Return the data as a JSON list."
        ),
        llm=ChatOpenAI(model="gpt-4o"),
        browser=browser,
    )

    result = await agent.run()
    print("Agent result:", result)


asyncio.run(run_agent())
