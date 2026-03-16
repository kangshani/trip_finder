#!/usr/bin/env python3
"""
Fetch images from Wikimedia Commons for a given attraction/landmark.

Uses the Wikimedia Commons API (free, no key needed) to find relevant photos
and return thumbnail URLs with attribution.

Usage:
    python tools/fetch_attraction_images.py --query "Angkor Wat Cambodia" --count 2
    python tools/fetch_attraction_images.py --query "Colosseum Rome" --count 1
"""

import argparse
import json
import re
import sys
import time

import requests

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
USER_AGENT = "TripFinder/1.0 (travel research tool; polite bot)"


def search_commons_images(query: str, count: int = 2) -> list[dict]:
    """Search Wikimedia Commons for images matching a query.

    Returns a list of dicts with: thumb_url, full_url, attribution, license.
    """
    params = {
        "action": "query",
        "generator": "search",
        "gsrsearch": f"{query}",
        "gsrlimit": count * 3,  # fetch extra to filter out non-photos
        "gsrnamespace": 6,  # File namespace
        "prop": "imageinfo",
        "iiprop": "url|extmetadata|mime",
        "iiurlwidth": 800,
        "format": "json",
    }
    headers = {"User-Agent": USER_AGENT}

    try:
        resp = requests.get(COMMONS_API, params=params, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"  Commons API error for '{query}': {e}", file=sys.stderr)
        return []

    pages = data.get("query", {}).get("pages", {})
    results = []

    for page_id, page in sorted(pages.items(), key=lambda x: x[1].get("index", 999)):
        imageinfo = page.get("imageinfo", [{}])[0]
        mime = imageinfo.get("mime", "")

        # Only keep JPEG/PNG photos (skip SVG, audio, PDF, etc.)
        if mime not in ("image/jpeg", "image/png", "image/webp"):
            continue

        thumb_url = imageinfo.get("thumburl", "")
        full_url = imageinfo.get("url", "")

        if not thumb_url:
            continue

        # Get attribution info
        extmeta = imageinfo.get("extmetadata", {})
        artist_html = extmeta.get("Artist", {}).get("value", "Unknown")
        # Strip HTML tags from artist field
        artist = re.sub(r"<[^>]+>", "", artist_html).strip()
        license_name = extmeta.get("LicenseShortName", {}).get("value", "Unknown")

        results.append({
            "thumb_url": thumb_url,
            "full_url": full_url,
            "attribution": artist,
            "license": license_name,
        })

        if len(results) >= count:
            break

    return results


def main():
    parser = argparse.ArgumentParser(description="Fetch images from Wikimedia Commons")
    parser.add_argument("--query", "-q", required=True, help="Search query (e.g., 'Angkor Wat Cambodia')")
    parser.add_argument("--count", "-n", type=int, default=2, help="Number of images to return (default: 2)")
    args = parser.parse_args()

    results = search_commons_images(args.query, args.count)
    print(json.dumps(results, indent=2))
    print(f"\nFound {len(results)} images", file=sys.stderr)


if __name__ == "__main__":
    main()
