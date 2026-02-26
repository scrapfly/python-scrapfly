# LLM.txt Generator with Scrapfly Crawler API

> **Generate LLM-optimized documentation files automatically by crawling any website**

This demo shows you how to use Scrapfly's Crawler API to automatically convert website documentation into the **llms.txt format** - a markdown-based standard designed to help Large Language Models (LLMs) better understand and answer questions about your content.

## 📚 What is llms.txt?

**llms.txt** is a markdown file format specifically designed for providing website content to AI language models like ChatGPT, Claude, and others. It was created to give LLMs structured, clean access to documentation and content.

### Why llms.txt?

- ✅ **LLM-optimized**: Structured format that LLMs can easily parse and understand
- ✅ **Markdown-based**: Clean, readable format without HTML clutter
- ✅ **Standardized**: Following the specification at [llmstxt.org](https://llmstxt.org)
- ✅ **Comprehensive**: Can include full documentation in a single file

### Learn More

- 📖 **Official Specification**: https://llmstxt.org
- 🔧 **llms-txt/llms.txt** on GitHub: https://github.com/llms-txt/llms.txt
- 📝 **Examples**: See real-world llms.txt files from major projects

## 🚀 Quick Start

### Prerequisites

Before you begin, make sure you have:

1. **Python 3.7+** installed
2. **Scrapfly API key** - Get one free at [scrapfly.io/dashboard](https://scrapfly.io/dashboard)
3. **Scrapfly Python SDK** installed:

```bash
pip install scrapfly-sdk
```

### Installation

1. **Clone this repository** or download the example files:

```bash
git clone https://github.com/scrapfly/python-scrapfly.git
cd python-scrapfly/examples/demos/llm-txt-generator
```

2. **Set your API key** as an environment variable:

```bash
export SCRAPFLY_API_KEY='your-api-key-here'
```

> 💡 **Tip**: On Windows, use `set` instead of `export`

### Running the Demo

Simply run the script:

```bash
python generate_llm_txt.py
```

This will:
1. Crawl the Scrapfly documentation at https://scrapfly.io/docs
2. Extract markdown content from all pages
3. Generate a `scrapfly_docs_llms-full.txt` file

**Expected output:**

```
======================================================================
LLM.txt Generator - Scrapfly Crawler API Demo
======================================================================

🔧 Initializing Scrapfly client...

📋 Crawler Configuration:
  • Target URL: https://scrapfly.io/docs
  • Path filter: /docs/*
  • Page limit: 50
  • Max depth: 5
  • Using sitemaps: Yes
  • Respecting robots.txt: Yes

🚀 Starting crawler...

📊 Crawling in progress...
[Progress updates...]

✅ Crawl completed!
  Pages crawled: 50
  Pages failed: 0
  Total discovered: 893

💾 Successfully saved to: scrapfly_docs_llms-full.txt
  File size: 330.4 KB
  Pages included: 50
  Total content: 340,315 characters

======================================================================
✅ LLM.txt generation complete!
======================================================================
```

## 📖 How It Works

### Step 1: Configure the Crawler

The crawler is configured to:
- Start at a specific URL (e.g., `https://scrapfly.io/docs`)
- Restrict crawling to certain paths (e.g., `/docs/*` only)
- Respect robots.txt and use sitemaps
- Extract markdown content from each page

```python
crawler_config = CrawlerConfig(
    url="https://scrapfly.io/docs",
    include_only_paths=["/docs/*"],  # Only crawl /docs pages
    page_limit=50,                    # Limit for demo
    max_depth=5,                      # How deep to crawl
    use_sitemaps=True,                # Use sitemap.xml
    respect_robots_txt=True,          # Follow robots.txt
    content_formats=['markdown'],     # Extract as markdown
)
```

### Step 2: Start the Crawl

The crawler runs asynchronously on Scrapfly's infrastructure:

```python
crawl = Crawl(client, crawler_config).crawl()
crawl.wait(poll_interval=5, verbose=True)  # Wait for completion
```

### Step 3: Retrieve Content Efficiently

Instead of making separate API calls for each page, we use the **batch content API** which retrieves up to 100 URLs per request:

```python
# Get URLs from WARC artifact
warc_artifact = crawl.warc()
urls = [record.url for record in warc_artifact.iter_responses()]

# Fetch content in batches of 100
all_contents = {}
for i in range(0, len(urls), 100):
    batch = urls[i:i + 100]
    contents = crawl.read_batch(batch, formats=['markdown'])
    all_contents.update(contents)
```

**Why batch retrieval?**
- ⚡ **Much faster**: 1 API call for 100 URLs vs 100 separate calls
- 💰 **More efficient**: Reduced API overhead
- 🎯 **Optimized**: Multipart/related response format

### Step 4: Build the llms.txt File

The file follows the [llmstxt.org specification](https://llmstxt.org):

```python
# Required: H1 heading with project name
llm_lines.append("# Scrapfly Documentation")
llm_lines.append("")

# Optional: Blockquote summary
llm_lines.append("> Comprehensive guides and API references...")
llm_lines.append("")

# Optional: About section
llm_lines.append("## About")
llm_lines.append("This document contains...")

# Main content: All pages
llm_lines.append("## Content")
for url, content in all_contents.items():
    llm_lines.append(f"### {url}")
    llm_lines.append(content['markdown'])
```

## 🎯 Use Cases

### 1. Documentation Sites

Convert your entire documentation into an LLM-friendly format:

```python
generate_llm_txt(
    base_url="https://docs.yourproject.com",
    site_name="YourProject Documentation",
    description="Complete API and usage documentation",
    path_filter="/docs/*",
)
```

### 2. Blog Content

Create an LLM-optimized archive of your blog:

```python
generate_llm_txt(
    base_url="https://yourblog.com/posts",
    site_name="YourBlog Articles",
    description="Collection of technical blog posts and tutorials",
    path_filter="/posts/*",
    page_limit=100,
)
```

### 3. Knowledge Bases

Archive support articles or knowledge base content:

```python
generate_llm_txt(
    base_url="https://support.yourcompany.com",
    site_name="Support Knowledge Base",
    description="Help articles and troubleshooting guides",
    path_filter="/kb/*",
)
```

## 🔧 Customization

### Adjusting Crawl Parameters

**Crawl more/fewer pages:**

```python
page_limit=100,  # Crawl up to 100 pages (None = unlimited)
```

**Change crawl depth:**

```python
max_depth=3,  # Stay within 3 clicks of the starting URL
```

**Include external links:**

```python
follow_external_links=True,  # Follow links to other domains
```

**Exclude certain paths:**

```python
exclude_paths=['/api/*', '/admin/*'],  # Don't crawl these
```

### Custom Output Format

Modify the `generate_llm_txt()` function to customize:

- **File structure**: Add more sections, change headings
- **Content filtering**: Skip certain pages or content
- **Metadata**: Add timestamps, versions, etc.

Example - add a table of contents:

```python
# Add after About section
llm_lines.append("## Table of Contents")
llm_lines.append("")
for url in all_contents.keys():
    title = extract_title(url)  # Your custom function
    llm_lines.append(f"- [{title}]({url})")
llm_lines.append("")
```

## 📊 Understanding the Output

The generated `llms-full.txt` file follows this structure:

```markdown
# Project Name

> Short description of the content

## About

Context and information about this document

## Content

---

### https://example.com/page1

[Markdown content of page 1]

---

### https://example.com/page2

[Markdown content of page 2]

---

## Metadata

- Total pages: 50
- Source: https://example.com
- Format: llms.txt (https://llmstxt.org)
```

### Using with LLMs

Once generated, you can use the file with:

**ChatGPT:**
1. Upload the file to ChatGPT
2. Ask questions like: "Based on this documentation, how do I...?"

**Claude:**
1. Paste the content or upload the file
2. Query: "Using this documentation, explain..."

**API-based:**
```python
# Use as context in API calls
with open('llms-full.txt') as f:
    context = f.read()

response = openai.ChatCompletion.create(
    messages=[
        {"role": "system", "content": f"Documentation:\n{context}"},
        {"role": "user", "content": "How do I configure the API?"}
    ]
)
```

## 🏗️ Technical Details

### Scrapfly Crawler API Features Used

1. **Path Filtering**: `include_only_paths` restricts crawling to specific URL patterns
2. **Sitemap Integration**: `use_sitemaps=True` discovers pages from sitemap.xml
3. **Robots.txt Compliance**: `respect_robots_txt=True` follows site crawling guidelines
4. **Markdown Extraction**: `content_formats=['markdown']` extracts clean markdown
5. **Batch Content API**: `read_batch()` retrieves multiple URLs efficiently

### WARC Artifact

The crawler stores results in **WARC format** (Web ARChive):
- Industry-standard format for web crawling
- Contains all HTTP responses and metadata
- Automatically compressed (gzip)

```python
# Access WARC artifact
warc = crawl.warc()

# Iterate through responses
for record in warc.iter_responses():
    print(f"{record.url}: {record.status_code}")
```

### Batch Contents API

Efficient content retrieval via multipart/related responses:

```python
# Single API call for up to 100 URLs
contents = crawl.read_batch(
    urls=['https://example.com/page1', ...],
    formats=['markdown']  # Can also request 'html', 'text'
)

# Returns: {'https://example.com/page1': {'markdown': '...'}, ...}
```

## 🛟 Troubleshooting

### "SCRAPFLY_API_KEY environment variable not set"

**Solution**: Set your API key before running:

```bash
export SCRAPFLY_API_KEY='scp-live-xxxxxxxx'
```

### "No content retrieved"

**Possible causes:**
- Page limit too low (increase `page_limit`)
- Path filter too restrictive (check `include_only_paths`)
- Site blocks crawlers (try adding `asp=True` for anti-bot bypass)

**Solution**: Adjust crawler config:

```python
CrawlerConfig(
    page_limit=None,  # Remove limit
    include_only_paths=None,  # Crawl everything
)
```

### "Crawl takes too long"

**Solution**: Reduce scope:

```python
page_limit=20,  # Fewer pages
max_depth=2,    # Shallower crawl
```

### File too large for LLM context

**Solution**: Split into multiple files or reduce content:

```python
# Option 1: Lower page limit
page_limit=30,

# Option 2: Generate separate files per section
# (Modify script to create multiple smaller files)
```

## 📚 Additional Resources

### llms.txt Ecosystem

- **Specification**: https://llmstxt.org
- **GitHub Repository**: https://github.com/llms-txt/llms.txt
- **llms-txt/llms_txt2ctx**: CLI tool for parsing llms.txt files
- **Examples**: See llms.txt files from Next.js, Supabase, and other projects

### Scrapfly Resources

- **Documentation**: https://scrapfly.io/docs
- **API Reference**: https://scrapfly.io/docs/crawler-api
- **Python SDK**: https://github.com/scrapfly/python-scrapfly
- **Dashboard**: https://scrapfly.io/dashboard (monitor crawls, view usage)
- **Support**: support@scrapfly.io

### Related Examples

- **Crawler Webhook Demo**: Real-time notifications when crawls complete
- **WARC Parser Example**: Advanced WARC file processing
- **Content Extraction**: Using extraction rules with crawler

## 💡 Tips & Best Practices

### 1. Start Small

Test with a small `page_limit` first:

```python
page_limit=10,  # Test with 10 pages
```

Once confirmed working, increase or remove the limit.

### 2. Use Path Filters

Restrict crawling to relevant content:

```python
include_only_paths=['/docs/*', '/guides/*'],
```

This saves API credits and reduces irrelevant content.

### 3. Monitor Your Crawls

Check the dashboard at https://scrapfly.io/dashboard to:
- Monitor crawl progress in real-time
- View discovered vs crawled URLs
- Check for errors
- Review API credit usage

### 4. Respect Rate Limits

For large sites, be mindful of:
- API rate limits (check your plan)
- Site server load
- Crawl politeness (delay between requests)

### 5. Update Regularly

Re-run the generator periodically to keep your llms.txt file updated:

```bash
# Weekly cron job example
0 0 * * 0 cd /path/to/script && python generate_llm_txt.py
```

## 🤝 Contributing

Found a bug or want to improve this example? Contributions welcome!

1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## 📄 License

This example is part of the Scrapfly Python SDK and follows the same license.

---

**Need Help?**

- 📧 Email: support@scrapfly.io
- 📖 Docs: https://scrapfly.io/docs
- 🐛 Issues: https://github.com/scrapfly/python-scrapfly/issues
