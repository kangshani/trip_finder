#!/usr/bin/env python3
"""
Search for travel destinations using multiple search providers.

Providers (in auto-fallback order):
  1. Brave Search API — 1000 free calls/month, then $5/1K
  2. DuckDuckGo       — free, unlimited, no API key needed
  3. Serper.dev        — 2500 one-time credits (on-demand only, not in auto chain)

Tracks API usage per provider in data/api_usage.json.

Usage:
    python lib/search_destinations.py --query "best wildlife destinations"
    python lib/search_destinations.py --query "test" --provider duckduckgo
    python lib/search_destinations.py --usage
"""

import argparse
import json
import os
import sys
import time
import hashlib
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

# Load env from project root
PROJECT_ROOT = Path(__file__).parent.parent
load_dotenv(PROJECT_ROOT / ".env")

BRAVE_API_KEY = os.getenv("BRAVE_SEARCH_API_KEY")
BRAVE_SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

SERPER_API_KEY = os.getenv("SERPER_API_KEY")
SERPER_SEARCH_URL = "https://google.serper.dev/search"

DEFAULT_OUTPUT_DIR = ".tmp/search_results"
USAGE_FILE = PROJECT_ROOT / "data" / "api_usage.json"
BRAVE_MONTHLY_LIMIT = 1000
SERPER_INITIAL_CREDITS = 2500
SERPER_EXPIRATION = "2026-09-10"


# ─── API Usage Tracking ──────────────────────────────────────────────────────

def _load_usage() -> dict:
    """Load API usage data from disk. Migrate from old format if needed."""
    if USAGE_FILE.exists():
        with open(USAGE_FILE) as f:
            data = json.load(f)
        # Migrate old single-provider format
        if "brave" not in data:
            data = {
                "brave": {
                    "month": data.get("month", ""),
                    "count": data.get("count", 0),
                    "history": data.get("history", []),
                },
                "duckduckgo": {
                    "total_calls": 0,
                },
                "serper": {
                    "initial_credits": SERPER_INITIAL_CREDITS,
                    "used": 0,
                    "expiration": SERPER_EXPIRATION,
                },
            }
            _save_usage(data)
        return data
    return {
        "brave": {"month": "", "count": 0, "history": []},
        "duckduckgo": {"total_calls": 0},
        "serper": {
            "initial_credits": SERPER_INITIAL_CREDITS,
            "used": 0,
            "expiration": SERPER_EXPIRATION,
        },
    }


def _save_usage(usage: dict):
    """Save API usage data to disk."""
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USAGE_FILE, "w") as f:
        json.dump(usage, f, indent=2)


def _increment_usage(provider: str) -> dict:
    """Increment usage for the given provider. Returns the provider's usage dict."""
    usage = _load_usage()
    current_month = datetime.now().strftime("%Y-%m")

    if provider == "brave":
        brave = usage["brave"]
        if brave["month"] != current_month:
            if brave["month"]:
                brave["history"].append({"month": brave["month"], "count": brave["count"]})
            brave["month"] = current_month
            brave["count"] = 0
        brave["count"] += 1
    elif provider == "duckduckgo":
        usage["duckduckgo"]["total_calls"] += 1
    elif provider == "serper":
        usage["serper"]["used"] += 1

    _save_usage(usage)
    return usage[provider]


def get_usage() -> dict:
    """Return usage info for all providers."""
    usage = _load_usage()
    current_month = datetime.now().strftime("%Y-%m")

    brave = usage["brave"]
    if brave["month"] != current_month:
        brave_count = 0
    else:
        brave_count = brave["count"]

    serper = usage["serper"]
    serper_remaining = max(0, serper["initial_credits"] - serper["used"])
    serper_expired = datetime.now().strftime("%Y-%m-%d") > serper["expiration"]

    return {
        "brave": {
            "used": brave_count,
            "limit": BRAVE_MONTHLY_LIMIT,
            "remaining": BRAVE_MONTHLY_LIMIT - brave_count,
            "month": current_month,
        },
        "duckduckgo": {
            "total_calls": usage["duckduckgo"]["total_calls"],
        },
        "serper": {
            "used": serper["used"],
            "initial_credits": serper["initial_credits"],
            "remaining": serper_remaining if not serper_expired else 0,
            "expiration": serper["expiration"],
            "expired": serper_expired,
        },
    }


def _brave_limit_reached() -> bool:
    """Return True if Brave monthly limit is reached."""
    info = get_usage()
    return info["brave"]["remaining"] <= 0


# ─── Search Providers ─────────────────────────────────────────────────────────

def search_brave(query: str, count: int = 10) -> dict:
    """Execute a Brave Search API query and return raw response."""
    if not BRAVE_API_KEY or BRAVE_API_KEY == "your_key_here":
        raise ValueError("BRAVE_SEARCH_API_KEY not set in .env file")

    if _brave_limit_reached():
        raise ValueError(f"Brave monthly limit reached ({BRAVE_MONTHLY_LIMIT}/{BRAVE_MONTHLY_LIMIT})")

    headers = {
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
        "X-Subscription-Token": BRAVE_API_KEY,
    }
    params = {
        "q": query,
        "count": min(count, 20),
        "search_lang": "en",
        "text_decorations": False,
    }

    response = requests.get(BRAVE_SEARCH_URL, headers=headers, params=params, timeout=15)
    response.raise_for_status()

    provider_usage = _increment_usage("brave")
    used = provider_usage["count"]
    remaining = BRAVE_MONTHLY_LIMIT - used
    print(f"  [Brave API usage: {used}/{BRAVE_MONTHLY_LIMIT}, {remaining} remaining]")

    return response.json()


def extract_results(raw_response: dict) -> list[dict]:
    """Extract clean search results from Brave API response."""
    results = []
    web_results = raw_response.get("web", {}).get("results", [])

    for item in web_results:
        results.append({
            "title": item.get("title", ""),
            "url": item.get("url", ""),
            "description": item.get("description", ""),
            "source": item.get("meta_url", {}).get("hostname", ""),
        })

    return results


def search_duckduckgo(query: str, count: int = 10) -> list[dict]:
    """Search using DuckDuckGo (free, no API key needed). Returns normalized results."""
    from ddgs import DDGS
    with DDGS() as ddgs:
        raw_results = list(ddgs.text(query, max_results=min(count, 20)))

    _increment_usage("duckduckgo")
    print(f"  [DuckDuckGo: returned {len(raw_results)} results (free)]")

    results = []
    for item in raw_results:
        href = item.get("href", "")
        results.append({
            "title": item.get("title", ""),
            "url": href,
            "description": item.get("body", ""),
            "source": href.split("/")[2] if href and "/" in href else "",
        })
    return results


def search_serper(query: str, count: int = 10) -> list[dict]:
    """Search using Serper.dev API. Returns normalized results."""
    if not SERPER_API_KEY:
        raise ValueError("SERPER_API_KEY not set in .env file")

    info = get_usage()
    if info["serper"]["remaining"] <= 0:
        reason = "expired" if info["serper"]["expired"] else "exhausted"
        raise ValueError(f"Serper.dev credits {reason}")

    headers = {
        "X-API-KEY": SERPER_API_KEY,
        "Content-Type": "application/json",
    }
    payload = {"q": query, "num": min(count, 20)}

    response = requests.post(SERPER_SEARCH_URL, headers=headers, json=payload, timeout=15)
    response.raise_for_status()

    provider_usage = _increment_usage("serper")
    remaining = SERPER_INITIAL_CREDITS - provider_usage["used"]
    print(f"  [Serper.dev: {provider_usage['used']}/{SERPER_INITIAL_CREDITS} used, {remaining} remaining]")

    raw = response.json()
    results = []
    for item in raw.get("organic", []):
        link = item.get("link", "")
        results.append({
            "title": item.get("title", ""),
            "url": link,
            "description": item.get("snippet", ""),
            "source": link.split("/")[2] if link and "/" in link else "",
        })
    return results


# ─── Unified Search Dispatcher ────────────────────────────────────────────────

def search(query: str, count: int = 10, provider: str = "auto") -> tuple:
    """
    Unified search function. Returns (results, provider_used).

    provider="auto": Brave first, fallback to DuckDuckGo if limit reached.
    provider="brave": Brave only (raises if limit reached).
    provider="duckduckgo": DuckDuckGo only.
    provider="serper": Serper.dev only (raises if credits exhausted).
    """
    if provider == "auto":
        if not _brave_limit_reached():
            try:
                raw = search_brave(query, count)
                return extract_results(raw), "brave"
            except Exception as e:
                print(f"  [Brave failed: {e}, falling back to DuckDuckGo]")
        else:
            print(f"  [Brave limit reached, using DuckDuckGo]")
        return search_duckduckgo(query, count), "duckduckgo"
    elif provider == "brave":
        raw = search_brave(query, count)
        return extract_results(raw), "brave"
    elif provider == "duckduckgo":
        return search_duckduckgo(query, count), "duckduckgo"
    elif provider == "serper":
        return search_serper(query, count), "serper"
    else:
        raise ValueError(f"Unknown provider: {provider}")


def search_and_save(query: str, max_results: int = 10, output_path: str = None, provider: str = "auto") -> list[dict]:
    """Search using the specified provider and save results to a JSON file."""
    if not output_path:
        slug = hashlib.md5(query.encode()).hexdigest()[:8]
        output_dir = Path(DEFAULT_OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{slug}.json"

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Searching: '{query}'")
    results, used_provider = search(query, count=max_results, provider=provider)
    print(f"  Found {len(results)} results (via {used_provider})")

    output_data = {
        "query": query,
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "provider": used_provider,
        "result_count": len(results),
        "results": results,
    }

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"  Saved to {output_path}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Search for destinations using multiple search providers")
    parser.add_argument("--query", "-q", help="Search query (required unless --usage is used)")
    parser.add_argument("--max-results", "-n", type=int, default=10, help="Max results (default: 10)")
    parser.add_argument("--output", "-o", help="Output JSON file path")
    parser.add_argument("--provider", "-p", choices=["auto", "brave", "duckduckgo", "serper"],
                        default="auto", help="Search provider (default: auto)")
    parser.add_argument("--usage", action="store_true", help="Show API usage for all providers")
    args = parser.parse_args()

    if args.usage:
        info = get_usage()
        print("Search API Usage:")
        print(f"\n  Brave Search (monthly):")
        print(f"    Used:      {info['brave']['used']}")
        print(f"    Limit:     {info['brave']['limit']}")
        print(f"    Remaining: {info['brave']['remaining']}")
        print(f"    Month:     {info['brave']['month']}")
        print(f"\n  DuckDuckGo (free):")
        print(f"    Total calls: {info['duckduckgo']['total_calls']}")
        print(f"\n  Serper.dev (one-time credits):")
        print(f"    Used:       {info['serper']['used']}")
        print(f"    Remaining:  {info['serper']['remaining']}")
        print(f"    Expires:    {info['serper']['expiration']}")
        print(f"    Expired:    {info['serper']['expired']}")
        sys.exit(0)

    if not args.query:
        parser.error("The --query/-q argument is required unless --usage is used.")

    results = search_and_save(args.query, args.max_results, args.output, args.provider)

    for r in results:
        print(f"  - {r['title']}")
        print(f"    {r['url']}")


if __name__ == "__main__":
    main()
