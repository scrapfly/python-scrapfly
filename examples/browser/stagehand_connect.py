"""
Stagehand Cloud Browser Connection

Stagehand is a JavaScript/TypeScript-only library (@browserbase/stagehand)
and cannot be used directly from Python.

You can generate the CDP WebSocket URL from Python and use it in your
JavaScript Stagehand code:

    from scrapfly import ScrapflyClient, BrowserConfig

    scrapfly = ScrapflyClient(key='__API_KEY__')
    cdp_url = scrapfly.cloud_browser(BrowserConfig(proxy_pool='datacenter'))
    print(f"Use this CDP URL in your Stagehand JS code: {cdp_url}")

JavaScript Stagehand example:

    import { Stagehand } from "@browserbase/stagehand";

    const stagehand = new Stagehand({
        env: "BROWSERBASE",
        browserbaseConnectURL: "wss://browser.scrapfly.io?api_key=YOUR_KEY&proxy_pool=datacenter",
    });

    await stagehand.init();
    await stagehand.page.goto("https://web-scraping.dev");
    await stagehand.act("click on the products link");

    const products = await stagehand.extract({
        instruction: "extract all product names and prices",
        schema: { products: [{ name: "string", price: "string" }] }
    });

    console.log("Products:", products);
    await stagehand.close();

For full documentation, see:
https://scrapfly.io/docs/cloud-browser-api/stagehand
"""

from scrapfly import ScrapflyClient, BrowserConfig

scrapfly = ScrapflyClient(key='__API_KEY__')
cdp_url = scrapfly.cloud_browser(BrowserConfig(proxy_pool='datacenter', os='linux'))
print(f"Use this CDP URL in your Stagehand JS code:\n{cdp_url}")
