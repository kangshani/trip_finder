---
name: scrape-website
description: Extract clean text content from a single URL for downstream analysis
argument-hint: <url> [output-dir]
disable-model-invocation: true
---

# Scrape Website

## Objective
Extract useful text content from a single URL and save it as a clean text file for downstream analysis.

## Inputs
- `$0` — the URL to scrape
- `$1` (optional) — output directory (default: `.tmp/scraped/`)

## Steps

### 1. Fetch the page
**Script**: `lib/scrape_single_site.py`
```bash
python lib/scrape_single_site.py --url "$0" --output "$1"
```

The script will:
1. Send a GET request with a browser-like User-Agent header
2. Parse HTML with BeautifulSoup
3. Extract the main content (strip nav, footer, ads, scripts)
4. Convert to clean text with section headers preserved
5. Save to `<output_dir>/<domain>_<hash>.txt`

### 2. Validate output
- File should be >= 100 characters (if less, the scrape likely failed)
- File should not contain "Access Denied", "403", or "captcha" indicators
- If validation fails, retry once with a 10s delay

## Output
- Clean text file in the specified output directory

## Supported Sources
| Source | Notes |
|---|---|
| Wikivoyage | Excellent structure, no blocking |
| Wikipedia | Good for geography, culture context |
| Travel blogs | Varies — some block scrapers |
| News/magazine sites | Often have paywalls — skip if blocked |

## Edge Cases
- **403 / Blocked**: Log the URL and skip. Do not retry more than once.
- **Timeout (>15s)**: Skip and log.
- **Non-HTML content (PDF, image)**: Skip.
- **Encoding issues**: Force UTF-8, replace undecodable characters.
- **Very long pages**: Truncate to first 50,000 characters to avoid memory issues.
