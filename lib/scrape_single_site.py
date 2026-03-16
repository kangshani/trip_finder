#!/usr/bin/env python3
"""
Scrape a single website URL and extract clean text content.

Usage:
    python tools/scrape_single_site.py --url "https://en.wikivoyage.org/wiki/Kyoto" --output .tmp/scraped/kyoto/
"""

import argparse
import hashlib
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup


USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

MAX_CONTENT_LENGTH = 50_000  # chars


def fetch_page(url: str, timeout: int = 15) -> str:
    """Fetch a URL and return raw HTML."""
    headers = {"User-Agent": USER_AGENT}
    response = requests.get(url, headers=headers, timeout=timeout)
    response.raise_for_status()
    response.encoding = response.apparent_encoding or "utf-8"
    return response.text


def extract_text(html: str, url: str = "") -> str:
    """Extract clean text from HTML, preserving section headers."""
    soup = BeautifulSoup(html, "lxml")

    # Try to find main content area FIRST
    candidates = soup.find_all(class_="mw-parser-output")
    candidates += soup.find_all("main")
    candidates += soup.find_all("article")
    candidates += soup.find_all(id=re.compile(r"(content|main|article)", re.IGNORECASE))
    candidates += soup.find_all(class_=re.compile(r"(content|main|article)", re.IGNORECASE))
    
    if candidates:
        # Pick the largest text container
        main = max(candidates, key=lambda c: len(c.get_text()))
    else:
        main = soup.find("body") or soup

    # Remove unwanted elements inside main
    for tag in main.find_all(["script", "style", "nav", "footer", "header",
                              "aside", "iframe", "noscript", "form"]):
        tag.decompose()

    # Remove common ad/navigation classes inside main (safely)
    for element in main.find_all(class_=re.compile(
        r"(sidebar|menu|nav|footer|header|ad|banner|cookie|popup|modal)",
        re.IGNORECASE
    )):
        if getattr(element, "attrs", None) is None:
            continue
        if element.name not in ["body", "html", "main", "article"]:
            try:
                if element.get("data-main") or "mw-parser-output" in element.get("class", []):
                    continue
            except AttributeError:
                pass
            element.decompose()

    # Extract text with headers preserved
    lines = []
    for element in main.find_all(["h1", "h2", "h3", "h4", "p", "li"]):
        if element.name in ("h1", "h2", "h3", "h4"):
            text = element.get_text(strip=True)
            if text:
                prefix = "#" * int(element.name[1])
                lines.append(f"\n{prefix} {text}\n")
        elif element.name == "p":
            text = element.get_text(strip=True)
            if text and len(text) > 20:  # Skip very short paragraphs (likely UI elements)
                lines.append(text)
        elif element.name == "li":
            text = element.get_text(strip=True)
            if text and len(text) > 10:
                lines.append(f"- {text}")

    content = "\n".join(lines)

    # Truncate if too long
    if len(content) > MAX_CONTENT_LENGTH:
        content = content[:MAX_CONTENT_LENGTH] + "\n\n[TRUNCATED]"

    return content


def scrape_and_save(url: str, output_dir: str) -> str:
    """Scrape a URL and save clean text to output directory."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Generate filename from URL
    parsed = urlparse(url)
    domain = parsed.hostname.replace(".", "_")
    url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
    filename = f"{domain}_{url_hash}.txt"
    filepath = output_path / filename

    print(f"Scraping: {url}")

    try:
        html = fetch_page(url)
    except requests.exceptions.HTTPError as e:
        if e.response.status_code in (403, 429):
            print(f"  BLOCKED ({e.response.status_code}): {url}", file=sys.stderr)
            return ""
        raise
    except requests.exceptions.Timeout:
        print(f"  TIMEOUT: {url}", file=sys.stderr)
        return ""
    except requests.exceptions.RequestException as e:
        print(f"  ERROR: {e}", file=sys.stderr)
        return ""

    content = extract_text(html, url)

    # Validate content
    if len(content.strip()) < 100:
        print(f"  WARNING: Extracted content too short ({len(content)} chars), possibly blocked")
        return ""

    # Check for block indicators
    block_indicators = ["access denied", "403 forbidden", "captcha", "please verify"]
    if any(indicator in content.lower()[:500] for indicator in block_indicators):
        print(f"  WARNING: Content appears to be a block page")
        return ""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"SOURCE: {url}\n")
        f.write(f"DOMAIN: {parsed.hostname}\n")
        f.write("---\n\n")
        f.write(content)

    print(f"  Saved {len(content)} chars to {filepath}")
    return str(filepath)


def main():
    parser = argparse.ArgumentParser(description="Scrape a website and extract clean text")
    parser.add_argument("--url", "-u", required=True, help="URL to scrape")
    parser.add_argument("--output", "-o", default=".tmp/scraped/", help="Output directory")
    args = parser.parse_args()

    result = scrape_and_save(args.url, args.output)
    if result:
        print(f"\nSuccess: {result}")
    else:
        print("\nFailed to scrape content", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
