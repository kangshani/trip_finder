#!/usr/bin/env python3
"""
Enrich destination JSON files with structured key_attractions data.

For each destination:
  1. Scrape Wikivoyage "See" / "Do" sections for attraction names
  2. Fall back to Brave Search if Wikivoyage yields < 5 attractions
  3. Fetch 1-2 images per attraction from Wikimedia Commons
  4. Write the key_attractions array into the destination JSON

Usage:
    python tools/enrich_attractions.py                          # All destinations
    python tools/enrich_attractions.py --single bali-indonesia-summer
    python tools/enrich_attractions.py --dry-run                # Preview without writing
    python tools/enrich_attractions.py --skip-images            # Names only, no images
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests
from bs4 import BeautifulSoup

# ── Project paths ────────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent  # scripts/ -> enrich-attractions/ -> skills/ -> .claude/ -> project root
DATA_DIR = PROJECT_ROOT / "data" / "destinations"

# ── Import sibling scripts and shared lib ────────────────────────────────────
sys.path.insert(0, str(SCRIPT_DIR))
sys.path.insert(0, str(PROJECT_ROOT / "lib"))
from fetch_attraction_images import search_commons_images
from search_destinations import search_brave, extract_results

# ── Constants ────────────────────────────────────────────────────────────────
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

WIKIVOYAGE_BASE = "https://en.wikivoyage.org/wiki/"
MIN_ATTRACTIONS = 5
MAX_ATTRACTIONS = 10
IMAGES_PER_ATTRACTION = 1
REQUEST_DELAY = 1.0  # seconds between HTTP requests (be polite)


# ── Wikivoyage Scraping ─────────────────────────────────────────────────────

def wikivoyage_url(destination_name: str) -> str:
    """Convert a destination name to a Wikivoyage URL."""
    # Strip country suffix like "Siem Reap, Cambodia" -> "Siem Reap"
    # But keep compound names like "New Zealand South Island"
    name = destination_name.split(",")[0].strip()
    # Handle special cases for country-level entries
    name = name.replace(" ", "_")
    return WIKIVOYAGE_BASE + quote(name, safe="_()/'")


def scrape_wikivoyage_attractions(destination_name: str) -> list[str]:
    """Scrape Wikivoyage for attraction names from See/Do sections.

    Returns a list of attraction name strings.
    """
    url = wikivoyage_url(destination_name)
    print(f"  Trying Wikivoyage: {url}")

    try:
        resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
        if resp.status_code == 404:
            print(f"  Wikivoyage page not found for '{destination_name}'")
            return []
        resp.raise_for_status()
    except requests.RequestException as e:
        print(f"  Wikivoyage fetch error: {e}")
        return []

    soup = BeautifulSoup(resp.text, "lxml")
    attractions = []

    # Find "See" and "Do" section headings (h2 with mw-headline spans)
    target_sections = {"see", "do"}
    skip_sections = {"get around", "get in", "buy", "eat", "drink", "sleep",
                     "cope", "go next", "respect", "stay safe", "connect",
                     "understand", "talk"}
    in_target = False

    # Generic words that indicate a category, not a specific attraction
    generic_words = {
        "temples", "beaches", "museums", "parks", "markets", "churches",
        "mosques", "monuments", "landscape", "art", "music", "nightlife",
        "shopping", "nature", "wildlife", "festivals", "architecture",
        "gardens", "lakes", "rivers", "mountains", "islands", "villages",
        "palaces", "castles", "ruins", "galleries", "squares", "bridges",
        "water activities", "other sports, adventure and family activities",
        "sports", "activities", "tours", "day trips", "excursions",
        "outdoor activities", "adventure", "cultural activities",
    }

    for element in soup.find_all(["h2", "h3", "h4"]):
        # Check if this is a section heading
        headline = element.find(class_="mw-headline")
        if not headline:
            headline = element

        heading_text = headline.get_text(strip=True).lower()

        if element.name == "h2":
            if heading_text in target_sections:
                in_target = True
            elif heading_text in skip_sections or heading_text not in target_sections:
                in_target = False
            continue

        if in_target and element.name in ("h3", "h4"):
            name = headline.get_text(strip=True)
            # Filter out generic headings, navigation, and transport
            if (
                name
                and len(name) > 2
                and len(name) < 80
                and name.lower() not in ("edit", "see also", "other")
                and name.lower().strip() not in generic_words
                and not name.startswith("[")
                and not name.lower().startswith("by ")
            ):
                attractions.append(name)

    # Deduplicate while preserving order
    seen = set()
    unique = []
    for a in attractions:
        if a.lower() not in seen:
            seen.add(a.lower())
            unique.append(a)

    # Quality filter: specific attractions typically include a proper noun
    # (e.g., "Colosseum", "Fushimi Inari Shrine"), while thematic categories
    # are generic English phrases (e.g., "Just walking around", "Public baths").
    # Heuristic: a "specific" name has at least one capitalized word beyond the
    # first word, or contains a place-word (Temple, Palace, Museum, etc.).
    place_words = {"temple", "shrine", "palace", "castle", "museum", "cathedral",
                   "basilica", "mosque", "fort", "fortress", "tower", "bridge",
                   "plaza", "square", "park", "garden", "market", "bay", "falls",
                   "waterfall", "beach", "hill", "mountain", "lake", "river",
                   "gorge", "canyon", "cave", "reef", "tomb", "wall", "gate",
                   "monastery", "abbey", "chapel", "theater", "theatre", "stadium",
                   "observatory", "aquarium", "zoo", "district", "quarter"}

    # Words from the destination name itself shouldn't count as "specific"
    dest_words = {w.lower() for w in destination_name.replace(",", "").split()}

    def looks_specific(name: str) -> bool:
        words = name.split()
        # Has a capitalized word after the first that isn't the destination name
        has_proper = any(
            w[0].isupper() and w.lower() not in dest_words
            for w in words[1:] if w[0].isalpha()
        )
        # Contains a place-type word
        has_place_word = any(w.lower() in place_words for w in words)
        return has_proper or has_place_word

    specific_count = sum(1 for a in unique if looks_specific(a))
    if unique and specific_count / len(unique) < 0.5:
        print(f"  Wikivoyage results look thematic ({specific_count}/{len(unique)} specific), will try Brave")
        return []

    return unique[:MAX_ATTRACTIONS]


# ── Brave Search Fallback ────────────────────────────────────────────────────

def brave_search_attractions(destination_name: str) -> list[str]:
    """Use Brave Search to find top attractions, then scrape the best result."""
    query = f"top 10 things to see in {destination_name} attractions"
    print(f"  Brave search: '{query}'")

    try:
        raw = search_brave(query, count=5)
        results = extract_results(raw)
    except Exception as e:
        print(f"  Brave search error: {e}", file=sys.stderr)
        return []

    time.sleep(REQUEST_DELAY)

    # Try to scrape the top non-ad results for numbered/bulleted attraction lists
    for result in results[:3]:
        url = result["url"]
        # Skip video/social/hard-to-parse sites
        if any(domain in url for domain in ["youtube.com", "tiktok.com", "instagram.com",
                                             "pinterest.com", "tripadvisor.com", "tripadvisor.co"]):
            continue

        print(f"  Scraping: {url}")
        try:
            resp = requests.get(url, headers={"User-Agent": USER_AGENT}, timeout=15)
            resp.raise_for_status()
        except requests.RequestException:
            continue

        attractions = extract_attractions_from_html(resp.text, destination_name)
        if len(attractions) >= MIN_ATTRACTIONS:
            return attractions[:MAX_ATTRACTIONS]

        time.sleep(REQUEST_DELAY)

    return []


def extract_attractions_from_html(html: str, destination_name: str) -> list[str]:
    """Extract attraction names from a travel blog/article HTML page.

    Looks for numbered headings like "1. Colosseum" or "The Colosseum" in h2/h3 tags.
    """
    soup = BeautifulSoup(html, "lxml")

    # Remove nav, footer, sidebar, ads
    for tag in soup.find_all(["nav", "footer", "aside", "header", "script", "style"]):
        tag.decompose()

    attractions = []
    country = destination_name.split(",")[-1].strip() if "," in destination_name else ""

    # Patterns that indicate we've left the main article content
    stop_patterns = re.compile(
        r"(leave a (comment|reply)|related posts?|you (may|might) also|"
        r"more from|recent posts?|popular posts?|comments?$|"
        r"about the author|sign up|subscribe|newsletter)",
        re.IGNORECASE
    )

    for heading in soup.find_all(["h2", "h3"]):
        text = heading.get_text(strip=True)

        # Stop if we've hit post-article content
        if stop_patterns.search(text):
            break

        # Strip leading numbers like "1. ", "1) ", "#1 "
        cleaned = re.sub(r"^[\d#]+[\.\)\-–—:\s]+", "", text).strip()
        # Strip trailing UI artifacts like "Arrow" from TripAdvisor
        cleaned = re.sub(r"Arrow$", "", cleaned).strip()
        # Strip trailing time durations like ": 30 minutes", ": 1-1.5 hours"
        cleaned = re.sub(r":?\s*\d[\d\-–.]*\s*(minutes?|hours?|mins?|hrs?|days?).*$",
                         "", cleaned, flags=re.IGNORECASE).strip()
        # Strip trailing parenthetical content that's just logistics
        cleaned = re.sub(r"\s*\([\d\-–,.\s]*(minutes?|hours?|USD|EUR|\$|free).*\)$",
                         "", cleaned, flags=re.IGNORECASE).strip()

        # Skip generic headings
        skip_words = {
            "table of contents", "related", "conclusion", "summary", "faq",
            "getting there", "where to stay", "where to eat", "how to get",
            "tips", "budget", "map", "overview", "introduction", "about",
            "when to visit", "best time", "travel tips", "practical info",
            "final thoughts", "pin it", "share", "comments", "leave a reply",
        }
        # Skip blog meta-headings and non-attraction entries
        skip_patterns = re.compile(
            r"(^(why|how|when|what|where|is|are|do|does|can|should|top \d+|best \d+|"
            r"\d+ best|\d+ top|\d+ things|travel tips|getting around|"
            r"frequently asked|related posts?|more from|you may also|"
            r"plan your|before you go|know before|prepare for|"
            r"packing|transportation|visiting key|lunch|dinner|breakfast|"
            r"take a )"
            r"|tips$|guide$|itinerary$|essentials$|& more$)",
            re.IGNORECASE
        )
        if (cleaned.lower() in skip_words or len(cleaned) < 3 or len(cleaned) > 100
                or skip_patterns.search(cleaned)):
            continue

        # Skip headings that are just the destination name
        if cleaned.lower() in (destination_name.lower(), country.lower()):
            continue

        attractions.append(cleaned)

    # Deduplicate
    seen = set()
    unique = []
    for a in attractions:
        key = a.lower()
        if key not in seen:
            seen.add(key)
            unique.append(a)

    return unique[:MAX_ATTRACTIONS]


# ── Image Enrichment ─────────────────────────────────────────────────────────

def get_images_for_attraction(attraction_name: str, destination_name: str,
                               count: int = IMAGES_PER_ATTRACTION) -> list[dict]:
    """Fetch Wikimedia Commons images for a specific attraction."""
    # Build a specific search query
    # Strip country from destination for shorter query if attraction already implies location
    city = destination_name.split(",")[0].strip()
    query = f"{attraction_name} {city}"

    images = search_commons_images(query, count=count)
    time.sleep(0.5)  # Be polite to Wikimedia

    return images


# ── Main Processing ──────────────────────────────────────────────────────────

def process_destination(filepath: Path, dry_run: bool = False,
                         skip_images: bool = False, force: bool = False) -> bool:
    """Process a single destination file. Returns True if modified."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    dest_name = data.get("name", filepath.stem)
    print(f"\n{'='*60}")
    print(f"Processing: {dest_name}")

    # Skip if already has attractions (unless --force)
    if "key_attractions" in data and data["key_attractions"] and not force:
        print(f"  Already has {len(data['key_attractions'])} attractions, skipping (use --force to overwrite)")
        return False

    # Step 1: Try Wikivoyage
    attraction_names = scrape_wikivoyage_attractions(dest_name)
    print(f"  Wikivoyage found: {len(attraction_names)} attractions")
    time.sleep(REQUEST_DELAY)

    # Step 2: Fall back to Brave if needed
    if len(attraction_names) < MIN_ATTRACTIONS:
        print(f"  Below minimum ({MIN_ATTRACTIONS}), trying Brave search...")
        brave_names = brave_search_attractions(dest_name)
        print(f"  Brave found: {len(brave_names)} attractions")

        # Merge: keep Wikivoyage results first, then add new ones from Brave
        existing = {a.lower() for a in attraction_names}
        for name in brave_names:
            if name.lower() not in existing:
                attraction_names.append(name)
                existing.add(name.lower())
            if len(attraction_names) >= MAX_ATTRACTIONS:
                break

    attraction_names = attraction_names[:MAX_ATTRACTIONS]

    if not attraction_names:
        print(f"  WARNING: No attractions found for {dest_name}")
        return False

    print(f"  Final attraction list ({len(attraction_names)}):")
    for i, name in enumerate(attraction_names, 1):
        print(f"    {i}. {name}")

    # Step 3: Fetch images
    key_attractions = []
    for name in attraction_names:
        entry = {"name": name, "images": []}

        if not skip_images:
            images = get_images_for_attraction(name, dest_name)
            if images:
                entry["images"] = [
                    {"url": img["thumb_url"], "attribution": img["attribution"], "license": img["license"]}
                    for img in images
                ]
                print(f"    {name}: {len(images)} image(s)")
            else:
                print(f"    {name}: no images found")

        key_attractions.append(entry)

    # Step 4: Write back
    data["key_attractions"] = key_attractions

    if not dry_run:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"  Saved {len(key_attractions)} attractions to {filepath.name}")
    else:
        print(f"  [DRY RUN] Would save {len(key_attractions)} attractions")

    return True


def main():
    parser = argparse.ArgumentParser(description="Enrich destinations with key attractions and images")
    parser.add_argument("--single", "-s", help="Process a single destination by slug (filename without .json)")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing files")
    parser.add_argument("--skip-images", action="store_true", help="Skip image fetching (names only)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing attractions data")
    args = parser.parse_args()

    if not DATA_DIR.exists():
        print(f"Error: {DATA_DIR} not found")
        sys.exit(1)

    if args.single:
        filepath = DATA_DIR / f"{args.single}.json"
        if not filepath.exists():
            print(f"Error: {filepath} not found")
            sys.exit(1)
        process_destination(filepath, dry_run=args.dry_run, skip_images=args.skip_images, force=args.force)
    else:
        files = sorted(DATA_DIR.glob("*.json"))
        print(f"Found {len(files)} destination files")

        enriched = 0
        skipped = 0
        failed = 0

        for filepath in files:
            try:
                if process_destination(filepath, dry_run=args.dry_run,
                                       skip_images=args.skip_images, force=args.force):
                    enriched += 1
                else:
                    skipped += 1
            except Exception as e:
                print(f"  ERROR processing {filepath.name}: {e}", file=sys.stderr)
                failed += 1

        print(f"\n{'='*60}")
        print(f"Done: {enriched} enriched, {skipped} skipped, {failed} failed")
        print(f"Total: {len(files)} destinations")


if __name__ == "__main__":
    main()
