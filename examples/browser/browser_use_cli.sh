#!/bin/bash
# Browser Use CLI with Scrapfly Cloud Browser
#
# The CLI connects to Cloud Browser via CDP and provides interactive
# browser control from the terminal.
#
# Requires: browser-use CLI installed (pip install browser-use)

API_KEY="YOUR_API_KEY"
BROWSER_WS="wss://browser.scrapfly.io?api_key=${API_KEY}&proxy_pool=datacenter&os=linux"

# Open a page in the cloud browser
browser-use --cdp-url "$BROWSER_WS" open https://web-scraping.dev/products

# Get page state (title, URL, clickable elements)
browser-use state

# Click on a product link (by element index from state output)
browser-use click 5

# Take a screenshot
browser-use screenshot product.png

# Type into a search field
browser-use input 3 "web scraping"

# Press Enter
browser-use keys "Enter"

# Close the session (stops billing)
browser-use close
