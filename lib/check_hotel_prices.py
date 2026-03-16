#!/usr/bin/env python3
"""
Look up real-time hotel prices using SerpApi Google Hotels API.

Falls back to web search (Brave → DuckDuckGo) when SerpApi quota is
exhausted or the API key is not configured.

Tracks monthly usage in data/api_usage.json (250 free calls/month).

Usage:
    python lib/check_hotel_prices.py --city "Milan" --checkin 2026-08-01 --checkout 2026-08-02
    python lib/check_hotel_prices.py --city "Milan" --hotel "Hotel Manzoni" --checkin 2026-08-01 --checkout 2026-08-02
    python lib/check_hotel_prices.py --usage
"""

import argparse
import json
import os
import sys
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

import requests
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
load_dotenv(PROJECT_ROOT / ".env")

SERPAPI_KEY = os.getenv("SERPAPI_KEY")
SERPAPI_URL = "https://serpapi.com/search.json"
SERPAPI_MONTHLY_LIMIT = 250

USAGE_FILE = PROJECT_ROOT / "data" / "api_usage.json"


# ─── Usage Tracking ─────────────────────────────────────────────────────────

def _load_usage() -> dict:
    if USAGE_FILE.exists():
        with open(USAGE_FILE) as f:
            return json.load(f)
    return {}


def _save_usage(usage: dict):
    USAGE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(USAGE_FILE, "w") as f:
        json.dump(usage, f, indent=2)


def _ensure_serpapi_section(usage: dict) -> dict:
    if "serpapi" not in usage:
        usage["serpapi"] = {
            "month": "",
            "count": 0,
            "monthly_limit": SERPAPI_MONTHLY_LIMIT,
            "history": [],
        }
    return usage


def _increment_serpapi() -> int:
    usage = _load_usage()
    usage = _ensure_serpapi_section(usage)
    current_month = datetime.now().strftime("%Y-%m")
    serpapi = usage["serpapi"]
    if serpapi["month"] != current_month:
        if serpapi["month"]:
            serpapi["history"].append({"month": serpapi["month"], "count": serpapi["count"]})
        serpapi["month"] = current_month
        serpapi["count"] = 0
    serpapi["count"] += 1
    _save_usage(usage)
    return serpapi["count"]


def _serpapi_remaining() -> int:
    usage = _load_usage()
    usage = _ensure_serpapi_section(usage)
    current_month = datetime.now().strftime("%Y-%m")
    serpapi = usage["serpapi"]
    if serpapi["month"] != current_month:
        return SERPAPI_MONTHLY_LIMIT
    return max(0, SERPAPI_MONTHLY_LIMIT - serpapi["count"])


def get_serpapi_usage() -> dict:
    usage = _load_usage()
    usage = _ensure_serpapi_section(usage)
    current_month = datetime.now().strftime("%Y-%m")
    serpapi = usage["serpapi"]
    count = serpapi["count"] if serpapi["month"] == current_month else 0
    return {
        "used": count,
        "limit": SERPAPI_MONTHLY_LIMIT,
        "remaining": SERPAPI_MONTHLY_LIMIT - count,
        "month": current_month,
    }


# ─── SerpApi Google Hotels ──────────────────────────────────────────────────

def search_hotels_serpapi(city: str, checkin: str, checkout: str,
                          adults: int = 2, currency: str = "EUR") -> list[dict]:
    """Query SerpApi Google Hotels and return parsed hotel list."""
    if not SERPAPI_KEY:
        raise ValueError("SERPAPI_KEY not set in .env file")

    remaining = _serpapi_remaining()
    if remaining <= 0:
        raise ValueError(f"SerpApi monthly limit reached ({SERPAPI_MONTHLY_LIMIT}/{SERPAPI_MONTHLY_LIMIT})")

    params = {
        "engine": "google_hotels",
        "q": f"{city} hotels",
        "check_in_date": checkin,
        "check_out_date": checkout,
        "adults": adults,
        "currency": currency,
        "gl": "us",
        "hl": "en",
        "api_key": SERPAPI_KEY,
    }

    response = requests.get(SERPAPI_URL, params=params, timeout=20)
    response.raise_for_status()
    data = response.json()

    count = _increment_serpapi()
    remaining = SERPAPI_MONTHLY_LIMIT - count
    print(f"  [SerpApi usage: {count}/{SERPAPI_MONTHLY_LIMIT}, {remaining} remaining]",
          file=sys.stderr)

    hotels = []
    for prop in data.get("properties", []):
        rate = prop.get("rate_per_night", {})
        total = prop.get("total_rate", {})
        hotels.append({
            "name": prop.get("name", ""),
            "type": prop.get("type", "hotel"),
            "rate_per_night": rate.get("lowest", ""),
            "rate_per_night_value": rate.get("extracted_lowest"),
            "total_rate": total.get("lowest", ""),
            "total_rate_value": total.get("extracted_lowest"),
            "rating": prop.get("overall_rating"),
            "reviews": prop.get("reviews"),
            "hotel_class": prop.get("hotel_class"),
            "check_in_time": prop.get("check_in_time", ""),
            "check_out_time": prop.get("check_out_time", ""),
            "amenities": prop.get("amenities", []),
            "source": "serpapi_google_hotels",
        })

    return hotels


def filter_by_hotel_name(hotels: list[dict], hotel_name: str) -> list[dict]:
    """Return hotels matching the given name, sorted by match quality."""
    scored = []
    name_lower = hotel_name.lower()
    for h in hotels:
        h_name_lower = h["name"].lower()
        # Exact substring match gets highest score
        if name_lower in h_name_lower or h_name_lower in name_lower:
            score = 0.95
        else:
            score = SequenceMatcher(None, name_lower, h_name_lower).ratio()
        if score >= 0.4:
            scored.append((score, h))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [h for _, h in scored]


# ─── Web Search Fallback ────────────────────────────────────────────────────

def search_hotels_websearch(city: str, checkin: str, checkout: str,
                            hotel_name: str = None) -> list[dict]:
    """Fallback: use existing search infrastructure to find hotel prices."""
    from lib.search_destinations import search

    if hotel_name:
        query = f'"{hotel_name}" {city} price per night {checkin[:7].replace("-", " ")}'
    else:
        query = f"{city} hotel prices {checkin[:7].replace('-', ' ')} per night"

    results, provider = search(query, count=10, provider="auto")
    print(f"  [Fallback web search via {provider}: {len(results)} results]",
          file=sys.stderr)

    return [{
        "name": hotel_name or f"{city} hotels (web search)",
        "search_results": results[:5],
        "source": f"web_search_{provider}",
        "note": "Prices are estimates from web search results — verify on booking sites",
    }]


# ─── Main Logic ─────────────────────────────────────────────────────────────

def check_prices(city: str, checkin: str, checkout: str,
                 hotel_name: str = None, adults: int = 2,
                 currency: str = "EUR") -> dict:
    """
    Look up hotel prices. Returns dict with results and metadata.
    Uses SerpApi if available, falls back to web search.
    """
    result = {
        "city": city,
        "check_in": checkin,
        "check_out": checkout,
        "adults": adults,
        "currency": currency,
        "source": None,
        "hotels": [],
    }

    # Try SerpApi first
    try:
        hotels = search_hotels_serpapi(city, checkin, checkout, adults, currency)
        result["source"] = "serpapi_google_hotels"
        if hotel_name:
            matched = filter_by_hotel_name(hotels, hotel_name)
            result["hotels"] = matched[:5] if matched else hotels[:10]
            if not matched:
                result["note"] = f"No close match for '{hotel_name}' — showing top results"
        else:
            result["hotels"] = hotels[:15]
    except (ValueError, requests.RequestException) as e:
        print(f"  [SerpApi unavailable: {e}]", file=sys.stderr)
        # Fallback to web search
        result["source"] = "web_search_fallback"
        result["hotels"] = search_hotels_websearch(city, checkin, checkout, hotel_name)
        result["note"] = "SerpApi unavailable — results are web search estimates"

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Look up real-time hotel prices via SerpApi Google Hotels")
    parser.add_argument("--city", "-c", help="City to search (required unless --usage)")
    parser.add_argument("--checkin", help="Check-in date (YYYY-MM-DD)")
    parser.add_argument("--checkout", help="Check-out date (YYYY-MM-DD)")
    parser.add_argument("--hotel", help="Specific hotel name to look up")
    parser.add_argument("--adults", type=int, default=2, help="Number of adults (default: 2)")
    parser.add_argument("--currency", default="EUR", help="Currency code (default: EUR)")
    parser.add_argument("--usage", action="store_true", help="Show SerpApi usage stats")
    args = parser.parse_args()

    if args.usage:
        info = get_serpapi_usage()
        print("SerpApi Google Hotels Usage:")
        print(f"  Used:      {info['used']}")
        print(f"  Limit:     {info['limit']}/month")
        print(f"  Remaining: {info['remaining']}")
        print(f"  Month:     {info['month']}")
        sys.exit(0)

    if not args.city or not args.checkin or not args.checkout:
        parser.error("--city, --checkin, and --checkout are required")

    result = check_prices(
        city=args.city,
        checkin=args.checkin,
        checkout=args.checkout,
        hotel_name=args.hotel,
        adults=args.adults,
        currency=args.currency,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
