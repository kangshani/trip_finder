#!/usr/bin/env python3
"""
Generate seed destination data by searching the web and scraping travel sources.

This script orchestrates the full pipeline:
1. Search Brave for destination lists across interest categories
2. Deduplicate and build a master destination list
3. For each destination, search for details and reference links
4. Scrape Wikivoyage for structured travel info
5. Build structured JSON records and save to data/destinations/

Usage:
    python tools/generate_seed_data.py
    python tools/generate_seed_data.py --limit 10          # Generate only 10 for testing
    python tools/generate_seed_data.py --skip-search       # Skip search, use existing queue
"""

import argparse
import json
import os
import re
import sys
import time
import hashlib
from pathlib import Path

# Add project root and lib to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent  # scripts/ -> batch-discover/ -> skills/ -> .claude/ -> project root
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "lib"))

from search_destinations import search_and_save, search_brave, extract_results
from scrape_single_site import scrape_and_save, fetch_page, extract_text
from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

# Directories
DATA_DIR = PROJECT_ROOT / "data" / "destinations"
TMP_DIR = PROJECT_ROOT / ".tmp"
QUEUE_FILE = TMP_DIR / "destination_queue.json"
PROGRESS_FILE = TMP_DIR / "batch_progress.json"
CONFIG_FILE = PROJECT_ROOT / "config" / "user_preferences.json"

# Rate limiting
SEARCH_DELAY = 1.5  # seconds between Brave API calls


def load_config() -> dict:
    with open(CONFIG_FILE) as f:
        return json.load(f)


def slugify(name: str) -> str:
    """Convert destination name to a filesystem-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s]+', '-', slug)
    slug = re.sub(r'-+', '-', slug)
    return slug.strip('-')


def generate_search_queries(config: dict) -> list[str]:
    """Generate search queries based on user interests and target months."""
    queries = []
    interests = config.get("interests_ranked", [])
    
    # Interest-based queries focused on summer
    interest_phrases = {
        "wildlife": ["best wildlife safari destinations summer", 
                     "best places to see animals in the wild june july august",
                     "wildlife viewing destinations summer vacation"],
        "natural_beauty": ["most beautiful natural destinations to visit in summer",
                          "stunning nature travel destinations june july august",
                          "best national parks to visit summer"],
        "historical_sites": ["best historical sites to visit summer vacation",
                            "ancient ruins worth visiting june july august",
                            "historical travel destinations summer"],
        "food": ["best food travel destinations summer",
                "culinary travel destinations june july august",
                "best cities for food lovers summer trip"],
        "museum": ["best museum destinations worth traveling to summer",
                   "cities with best museums summer vacation"],
        "culture": ["best cultural immersion destinations summer",
                   "unique cultural experiences travel june july august"],
        "cities": ["best cities to visit in summer 1-2 weeks",
                  "top city destinations june july august vacation"],
    }
    
    for interest in interests:
        if interest in interest_phrases:
            queries.extend(interest_phrases[interest])
    
    # Regional queries for summer
    regions = [
        "Southeast Asia", "East Asia", "Europe", "Northern Europe", "Southern Europe",
        "Central America", "South America", "East Africa", "Southern Africa",
        "Oceania", "Caribbean", "Pacific Islands", "Central Asia",
        "Mediterranean", "Scandinavia", "Balkans"
    ]
    for region in regions:
        queries.append(f"best places to visit in {region} june july august")
    
    # General discovery
    queries.extend([
        "best summer vacation destinations 2025 for couples",
        "top 50 travel destinations summer",
        "best 2 week trip destinations summer",
        "underrated travel destinations summer 2025",
        "bucket list destinations best in summer",
        "best adventure travel destinations june july august",
        "top island destinations summer vacation",
        "best mountain destinations summer hiking",
        "best coastal destinations summer trip",
    ])
    
    return queries


def extract_destination_names(search_results: list[dict]) -> list[str]:
    """Extract destination names from search result snippets and titles."""
    # Common destination patterns in search results
    destinations = set()
    
    # We'll collect the raw text from all results
    all_text = ""
    for result in search_results:
        all_text += f" {result.get('title', '')} {result.get('description', '')}"
    
    return all_text  # Return raw text for the LLM to parse later


def search_for_destination_details(dest_name: str) -> dict:
    """Search for details about a specific destination."""
    queries = [
        f"{dest_name} travel guide things to do",
        f"{dest_name} trip cost budget how much",
        f"{dest_name} youtube travel video",
    ]
    
    all_results = []
    for query in queries:
        try:
            raw = search_brave(query, count=5)
            results = extract_results(raw)
            all_results.extend(results)
            time.sleep(SEARCH_DELAY)
        except Exception as e:
            print(f"  Search error for '{query}': {e}", file=sys.stderr)
    
    return all_results


def find_wikivoyage_url(dest_name: str) -> str:
    """Try to find a Wikivoyage page for the destination."""
    # Clean the name for Wikivoyage URL format
    clean_name = dest_name.split(",")[0].strip()  # "Kyoto, Japan" -> "Kyoto"
    clean_name = clean_name.replace(" ", "_")
    url = f"https://en.wikivoyage.org/wiki/{clean_name}"
    
    try:
        import requests as req
        resp = req.head(url, allow_redirects=True, timeout=5, 
                       headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code == 200:
            return resp.url  # Follow redirects
    except:
        pass
    
    return ""


def extract_reference_links(search_results: list[dict], dest_name: str) -> list[dict]:
    """Extract the best reference links from search results."""
    links = []
    seen_domains = set()
    
    for result in search_results:
        url = result.get("url", "")
        title = result.get("title", "")
        domain = result.get("source", "")
        
        if domain in seen_domains:
            continue
        
        # Categorize
        link_type = "article"
        if "youtube.com" in url or "youtu.be" in url:
            link_type = "video"
        elif "vimeo.com" in url:
            link_type = "video"
        
        # Skip low-quality sources
        skip_domains = ["pinterest", "tripadvisor.com/ShowForum", "reddit.com"]
        if any(skip in url for skip in skip_domains):
            continue
        
        links.append({
            "title": title,
            "url": url,
            "type": link_type,
        })
        seen_domains.add(domain)
        
        if len(links) >= 5:
            break
    
    return links


def parse_wikivoyage_data(text: str, dest_name: str) -> dict:
    """Extract structured data from Wikivoyage scraped text."""
    data = {}
    
    # Try to extract sections
    sections = {}
    current_section = "intro"
    current_content = []
    
    for line in text.split("\n"):
        if line.startswith("# ") or line.startswith("## "):
            if current_content:
                sections[current_section] = "\n".join(current_content)
            current_section = line.strip("# ").strip().lower()
            current_content = []
        else:
            current_content.append(line)
    if current_content:
        sections[current_section] = "\n".join(current_content)
    
    # Build attractions summary from available sections
    summary_parts = []
    
    intro = sections.get("intro", "")
    if intro:
        # Take first 2-3 sentences
        sentences = re.split(r'(?<=[.!?])\s+', intro.strip())
        summary_parts.append(" ".join(sentences[:3]))
    
    # Look for "see" or "do" sections for attractions
    for key in ["see", "do", "understand", "eat", "drink"]:
        if key in sections:
            content = sections[key].strip()
            if content and len(content) > 50:
                summary_parts.append(f"\n**{key.title()}**: {content[:300]}")
    
    data["wiki_summary"] = "\n\n".join(summary_parts)[:1500]
    data["sections_found"] = list(sections.keys())
    
    return data


# ─── Master destination list (curated + discovered) ───────────────────────────
# This provides the canonical list of 100 summer destinations.
# The search pipeline enriches each with real data and links.

SUMMER_DESTINATIONS = [
    # Wildlife & Safari
    {"name": "Serengeti, Tanzania", "country": "Tanzania", "region": "East Africa", "lat": -2.33, "lng": 34.83, "season": "summer", "interests": ["wildlife", "natural_beauty"]},
    {"name": "Masai Mara, Kenya", "country": "Kenya", "region": "East Africa", "lat": -1.50, "lng": 35.15, "season": "summer", "interests": ["wildlife", "natural_beauty"]},
    {"name": "Kruger National Park, South Africa", "country": "South Africa", "region": "Southern Africa", "lat": -23.99, "lng": 31.55, "season": "year-round", "interests": ["wildlife", "natural_beauty"]},
    {"name": "Galapagos Islands, Ecuador", "country": "Ecuador", "region": "South America", "lat": -0.95, "lng": -90.97, "season": "summer", "interests": ["wildlife", "natural_beauty"]},
    {"name": "Yellowstone", "country": "United States", "region": "North America", "lat": 44.43, "lng": -110.59, "season": "summer", "interests": ["wildlife", "natural_beauty"]},
    {"name": "Borneo, Malaysia", "country": "Malaysia", "region": "Southeast Asia", "lat": 1.55, "lng": 110.35, "season": "summer", "interests": ["wildlife", "natural_beauty"]},
    {"name": "Costa Rica", "country": "Costa Rica", "region": "Central America", "lat": 10.0, "lng": -84.0, "season": "summer", "interests": ["wildlife", "natural_beauty"]},
    {"name": "Svalbard, Norway", "country": "Norway", "region": "Northern Europe", "lat": 78.22, "lng": 15.64, "season": "summer", "interests": ["wildlife", "natural_beauty"]},
    {"name": "Pantanal, Brazil", "country": "Brazil", "region": "South America", "lat": -17.85, "lng": -57.41, "season": "summer", "interests": ["wildlife", "natural_beauty"]},
    {"name": "Alaska", "country": "United States", "region": "North America", "lat": 63.35, "lng": -152.0, "season": "summer", "interests": ["wildlife", "natural_beauty"]},
    
    # Natural Beauty
    {"name": "Iceland", "country": "Iceland", "region": "Northern Europe", "lat": 64.96, "lng": -19.02, "season": "summer", "interests": ["natural_beauty", "wildlife"]},
    {"name": "Banff, Canada", "country": "Canada", "region": "North America", "lat": 51.18, "lng": -115.57, "season": "summer", "interests": ["natural_beauty"]},
    {"name": "Patagonia, Argentina", "country": "Argentina", "region": "South America", "lat": -50.34, "lng": -72.26, "season": "year-round", "interests": ["natural_beauty"]},
    {"name": "Norwegian Fjords", "country": "Norway", "region": "Northern Europe", "lat": 61.50, "lng": 6.80, "season": "summer", "interests": ["natural_beauty"]},
    {"name": "Swiss Alps", "country": "Switzerland", "region": "Western Europe", "lat": 46.57, "lng": 7.98, "season": "summer", "interests": ["natural_beauty"]},
    {"name": "Dolomites, Italy", "country": "Italy", "region": "Southern Europe", "lat": 46.41, "lng": 11.84, "season": "summer", "interests": ["natural_beauty"]},
    {"name": "Plitvice Lakes, Croatia", "country": "Croatia", "region": "Southern Europe", "lat": 44.88, "lng": 15.62, "season": "summer", "interests": ["natural_beauty"]},
    {"name": "Zhangjiajie, China", "country": "China", "region": "East Asia", "lat": 29.33, "lng": 110.43, "season": "summer", "interests": ["natural_beauty"]},
    {"name": "Faroe Islands", "country": "Denmark", "region": "Northern Europe", "lat": 62.01, "lng": -6.77, "season": "summer", "interests": ["natural_beauty", "wildlife"]},
    {"name": "Azores, Portugal", "country": "Portugal", "region": "Southern Europe", "lat": 37.74, "lng": -25.68, "season": "summer", "interests": ["natural_beauty", "wildlife"]},
    {"name": "New Zealand South Island", "country": "New Zealand", "region": "Oceania", "lat": -44.00, "lng": 170.48, "season": "year-round", "interests": ["natural_beauty"]},
    {"name": "Grand Canyon", "country": "United States", "region": "North America", "lat": 36.11, "lng": -112.11, "season": "summer", "interests": ["natural_beauty"]},
    {"name": "Ha Long Bay, Vietnam", "country": "Vietnam", "region": "Southeast Asia", "lat": 20.91, "lng": 107.18, "season": "summer", "interests": ["natural_beauty"]},
    {"name": "Lofoten Islands, Norway", "country": "Norway", "region": "Northern Europe", "lat": 68.24, "lng": 14.57, "season": "summer", "interests": ["natural_beauty"]},
    
    # Historical Sites
    {"name": "Rome, Italy", "country": "Italy", "region": "Southern Europe", "lat": 41.90, "lng": 12.50, "season": "summer", "interests": ["historical_sites", "food", "culture"]},
    {"name": "Athens, Greece", "country": "Greece", "region": "Southern Europe", "lat": 37.98, "lng": 23.73, "season": "summer", "interests": ["historical_sites", "culture", "food"]},
    {"name": "Machu Picchu, Peru", "country": "Peru", "region": "South America", "lat": -13.16, "lng": -72.55, "season": "summer", "interests": ["historical_sites", "natural_beauty"]},
    {"name": "Angkor Wat, Cambodia", "country": "Cambodia", "region": "Southeast Asia", "lat": 13.41, "lng": 103.87, "season": "summer", "interests": ["historical_sites", "culture"]},
    {"name": "Petra, Jordan", "country": "Jordan", "region": "Middle East", "lat": 30.33, "lng": 35.44, "season": "summer", "interests": ["historical_sites"]},
    {"name": "Istanbul, Turkey", "country": "Turkey", "region": "Middle East", "lat": 41.01, "lng": 28.98, "season": "summer", "interests": ["historical_sites", "food", "culture"]},
    {"name": "Kyoto, Japan", "country": "Japan", "region": "East Asia", "lat": 35.01, "lng": 135.77, "season": "summer", "interests": ["historical_sites", "culture", "food"]},
    {"name": "Cairo & Luxor, Egypt", "country": "Egypt", "region": "North Africa", "lat": 30.04, "lng": 31.24, "season": "year-round", "interests": ["historical_sites", "culture"]},
    {"name": "Dubrovnik, Croatia", "country": "Croatia", "region": "Southern Europe", "lat": 42.65, "lng": 18.09, "season": "summer", "interests": ["historical_sites", "natural_beauty"]},
    {"name": "Edinburgh, Scotland", "country": "United Kingdom", "region": "Northern Europe", "lat": 55.95, "lng": -3.19, "season": "summer", "interests": ["historical_sites", "culture"]},
    {"name": "Cusco, Peru", "country": "Peru", "region": "South America", "lat": -13.53, "lng": -71.97, "season": "summer", "interests": ["historical_sites", "culture"]},
    {"name": "Jerusalem, Israel", "country": "Israel", "region": "Middle East", "lat": 31.77, "lng": 35.23, "season": "summer", "interests": ["historical_sites", "culture"]},
    
    # Food Destinations
    {"name": "Tokyo, Japan", "country": "Japan", "region": "East Asia", "lat": 35.68, "lng": 139.69, "season": "summer", "interests": ["food", "culture", "cities"]},
    {"name": "Bangkok, Thailand", "country": "Thailand", "region": "Southeast Asia", "lat": 13.76, "lng": 100.50, "season": "summer", "interests": ["food", "culture", "cities"]},
    {"name": "Barcelona, Spain", "country": "Spain", "region": "Southern Europe", "lat": 41.39, "lng": 2.17, "season": "summer", "interests": ["food", "culture", "cities"]},
    {"name": "Mexico City, Mexico", "country": "Mexico", "region": "North America", "lat": 19.43, "lng": -99.13, "season": "summer", "interests": ["food", "culture", "cities"]},
    {"name": "Bologna, Italy", "country": "Italy", "region": "Southern Europe", "lat": 44.49, "lng": 11.34, "season": "summer", "interests": ["food", "historical_sites"]},
    {"name": "Lima, Peru", "country": "Peru", "region": "South America", "lat": -12.05, "lng": -77.04, "season": "year-round", "interests": ["food", "culture"]},
    {"name": "San Sebastian, Spain", "country": "Spain", "region": "Southern Europe", "lat": 43.32, "lng": -1.98, "season": "summer", "interests": ["food", "natural_beauty"]},
    {"name": "Oaxaca, Mexico", "country": "Mexico", "region": "North America", "lat": 17.07, "lng": -96.73, "season": "summer", "interests": ["food", "culture"]},
    {"name": "Hanoi, Vietnam", "country": "Vietnam", "region": "Southeast Asia", "lat": 21.03, "lng": 105.85, "season": "summer", "interests": ["food", "culture"]},
    {"name": "Lisbon, Portugal", "country": "Portugal", "region": "Southern Europe", "lat": 38.72, "lng": -9.14, "season": "summer", "interests": ["food", "culture", "cities"]},
    {"name": "Seoul, South Korea", "country": "South Korea", "region": "East Asia", "lat": 37.57, "lng": 126.98, "season": "summer", "interests": ["food", "culture", "cities"]},
    
    # Museums
    {"name": "Paris, France", "country": "France", "region": "Western Europe", "lat": 48.86, "lng": 2.35, "season": "summer", "interests": ["museum", "food", "culture", "cities"]},
    {"name": "London, England", "country": "United Kingdom", "region": "Western Europe", "lat": 51.51, "lng": -0.13, "season": "summer", "interests": ["museum", "culture", "historical_sites", "cities"]},
    {"name": "Amsterdam, Netherlands", "country": "Netherlands", "region": "Western Europe", "lat": 52.37, "lng": 4.90, "season": "summer", "interests": ["museum", "culture", "cities"]},
    {"name": "Florence, Italy", "country": "Italy", "region": "Southern Europe", "lat": 43.77, "lng": 11.25, "season": "summer", "interests": ["museum", "historical_sites", "food"]},
    {"name": "Berlin, Germany", "country": "Germany", "region": "Western Europe", "lat": 52.52, "lng": 13.41, "season": "summer", "interests": ["museum", "culture", "historical_sites", "cities"]},
    {"name": "Vienna, Austria", "country": "Austria", "region": "Western Europe", "lat": 48.21, "lng": 16.37, "season": "summer", "interests": ["museum", "culture", "historical_sites"]},
    {"name": "St. Petersburg, Russia", "country": "Russia", "region": "Eastern Europe", "lat": 59.93, "lng": 30.32, "season": "summer", "interests": ["museum", "historical_sites", "culture"]},
    {"name": "Madrid, Spain", "country": "Spain", "region": "Southern Europe", "lat": 40.42, "lng": -3.70, "season": "summer", "interests": ["museum", "food", "culture", "cities"]},
    {"name": "Washington D.C.", "country": "United States", "region": "North America", "lat": 38.91, "lng": -77.04, "season": "summer", "interests": ["museum", "historical_sites"]},
    
    # Culture
    {"name": "Marrakech, Morocco", "country": "Morocco", "region": "North Africa", "lat": 31.63, "lng": -8.00, "season": "summer", "interests": ["culture", "food", "historical_sites"]},
    {"name": "Bali, Indonesia", "country": "Indonesia", "region": "Southeast Asia", "lat": -8.34, "lng": 115.09, "season": "summer", "interests": ["culture", "natural_beauty"]},
    {"name": "Havana, Cuba", "country": "Cuba", "region": "Caribbean", "lat": 23.11, "lng": -82.37, "season": "summer", "interests": ["culture", "historical_sites"]},
    {"name": "Fez, Morocco", "country": "Morocco", "region": "North Africa", "lat": 34.03, "lng": -5.00, "season": "summer", "interests": ["culture", "historical_sites", "food"]},
    {"name": "Luang Prabang, Laos", "country": "Laos", "region": "Southeast Asia", "lat": 19.89, "lng": 102.13, "season": "summer", "interests": ["culture", "natural_beauty"]},
    {"name": "Varanasi, India", "country": "India", "region": "South Asia", "lat": 25.32, "lng": 83.01, "season": "summer", "interests": ["culture", "historical_sites"]},
    {"name": "Tbilisi, Georgia", "country": "Georgia", "region": "Central Asia", "lat": 41.72, "lng": 44.79, "season": "summer", "interests": ["culture", "food", "historical_sites"]},
    {"name": "Bhutan", "country": "Bhutan", "region": "South Asia", "lat": 27.47, "lng": 89.64, "season": "summer", "interests": ["culture", "natural_beauty"]},
    {"name": "Zanzibar, Tanzania", "country": "Tanzania", "region": "East Africa", "lat": -6.17, "lng": 39.19, "season": "summer", "interests": ["culture", "natural_beauty"]},
    
    # Cities
    {"name": "New York City", "country": "United States", "region": "North America", "lat": 40.71, "lng": -74.01, "season": "summer", "interests": ["cities", "museum", "food", "culture"]},
    {"name": "Singapore", "country": "Singapore", "region": "Southeast Asia", "lat": 1.35, "lng": 103.82, "season": "year-round", "interests": ["cities", "food", "culture"]},
    {"name": "Copenhagen, Denmark", "country": "Denmark", "region": "Northern Europe", "lat": 55.68, "lng": 12.57, "season": "summer", "interests": ["cities", "food", "culture"]},
    {"name": "Buenos Aires, Argentina", "country": "Argentina", "region": "South America", "lat": -34.60, "lng": -58.38, "season": "year-round", "interests": ["cities", "food", "culture"]},
    {"name": "Prague, Czech Republic", "country": "Czech Republic", "region": "Eastern Europe", "lat": 50.08, "lng": 14.44, "season": "summer", "interests": ["cities", "historical_sites", "culture"]},
    {"name": "Budapest, Hungary", "country": "Hungary", "region": "Eastern Europe", "lat": 47.50, "lng": 19.04, "season": "summer", "interests": ["cities", "historical_sites", "culture", "food"]},
    {"name": "Cape Town, South Africa", "country": "South Africa", "region": "Southern Africa", "lat": -33.93, "lng": 18.42, "season": "year-round", "interests": ["cities", "natural_beauty", "wildlife"]},
    {"name": "Montreal, Canada", "country": "Canada", "region": "North America", "lat": 45.50, "lng": -73.57, "season": "summer", "interests": ["cities", "food", "culture"]},
    {"name": "Melbourne, Australia", "country": "Australia", "region": "Oceania", "lat": -37.81, "lng": 144.96, "season": "year-round", "interests": ["cities", "food", "culture"]},
    {"name": "Taipei, Taiwan", "country": "Taiwan", "region": "East Asia", "lat": 25.03, "lng": 121.57, "season": "summer", "interests": ["cities", "food", "culture"]},
    
    # Beach / Island (good for summer)
    {"name": "Santorini, Greece", "country": "Greece", "region": "Southern Europe", "lat": 36.39, "lng": 25.46, "season": "summer", "interests": ["natural_beauty", "culture"]},
    {"name": "Amalfi Coast, Italy", "country": "Italy", "region": "Southern Europe", "lat": 40.63, "lng": 14.60, "season": "summer", "interests": ["natural_beauty", "food"]},
    {"name": "Maldives", "country": "Maldives", "region": "South Asia", "lat": 3.20, "lng": 73.22, "season": "summer", "interests": ["natural_beauty", "wildlife"]},
    {"name": "Raja Ampat, Indonesia", "country": "Indonesia", "region": "Southeast Asia", "lat": -0.23, "lng": 130.52, "season": "summer", "interests": ["natural_beauty", "wildlife"]},
    {"name": "Palawan, Philippines", "country": "Philippines", "region": "Southeast Asia", "lat": 10.17, "lng": 119.05, "season": "summer", "interests": ["natural_beauty", "wildlife"]},
    {"name": "Hawaii", "country": "United States", "region": "North America", "lat": 19.90, "lng": -155.58, "season": "year-round", "interests": ["natural_beauty", "wildlife", "culture"]},
    {"name": "Corsica, France", "country": "France", "region": "Southern Europe", "lat": 42.04, "lng": 9.01, "season": "summer", "interests": ["natural_beauty", "food"]},
    {"name": "Sardinia, Italy", "country": "Italy", "region": "Southern Europe", "lat": 40.12, "lng": 9.01, "season": "summer", "interests": ["natural_beauty", "food"]},
    
    # Adventure / Mixed
    {"name": "Queenstown, New Zealand", "country": "New Zealand", "region": "Oceania", "lat": -45.03, "lng": 168.66, "season": "year-round", "interests": ["natural_beauty"]},
    {"name": "Torres del Paine, Chile", "country": "Chile", "region": "South America", "lat": -51.00, "lng": -73.00, "season": "year-round", "interests": ["natural_beauty"]},
    {"name": "Namibia", "country": "Namibia", "region": "Southern Africa", "lat": -22.56, "lng": 17.08, "season": "summer", "interests": ["wildlife", "natural_beauty"]},
    {"name": "Sri Lanka", "country": "Sri Lanka", "region": "South Asia", "lat": 7.87, "lng": 80.77, "season": "summer", "interests": ["wildlife", "natural_beauty", "culture", "historical_sites"]},
    {"name": "Madagascar", "country": "Madagascar", "region": "East Africa", "lat": -18.77, "lng": 46.87, "season": "summer", "interests": ["wildlife", "natural_beauty"]},
    {"name": "Colombia", "country": "Colombia", "region": "South America", "lat": 4.71, "lng": -74.07, "season": "summer", "interests": ["natural_beauty", "culture", "food"]},
    {"name": "Montenegro", "country": "Montenegro", "region": "Southern Europe", "lat": 42.44, "lng": 19.26, "season": "summer", "interests": ["natural_beauty", "historical_sites"]},
    {"name": "Slovenia", "country": "Slovenia", "region": "Southern Europe", "lat": 46.15, "lng": 14.99, "season": "summer", "interests": ["natural_beauty"]},
    {"name": "Scottish Highlands", "country": "United Kingdom", "region": "Northern Europe", "lat": 57.12, "lng": -4.71, "season": "summer", "interests": ["natural_beauty", "culture", "wildlife"]},
    {"name": "Provence, France", "country": "France", "region": "Southern Europe", "lat": 43.95, "lng": 5.45, "season": "summer", "interests": ["natural_beauty", "food", "culture"]},
    {"name": "Uganda", "country": "Uganda", "region": "East Africa", "lat": 1.37, "lng": 32.29, "season": "summer", "interests": ["wildlife", "natural_beauty"]},
    {"name": "Jordan", "country": "Jordan", "region": "Middle East", "lat": 30.59, "lng": 36.24, "season": "summer", "interests": ["historical_sites", "natural_beauty"]},
    {"name": "Oman", "country": "Oman", "region": "Middle East", "lat": 23.59, "lng": 58.55, "season": "year-round", "interests": ["natural_beauty", "culture", "historical_sites"]},
    {"name": "Siem Reap, Cambodia", "country": "Cambodia", "region": "Southeast Asia", "lat": 13.36, "lng": 103.86, "season": "summer", "interests": ["historical_sites", "culture", "food"]},
    {"name": "Dubrovnik to Split Coast, Croatia", "country": "Croatia", "region": "Southern Europe", "lat": 43.51, "lng": 16.44, "season": "summer", "interests": ["natural_beauty", "historical_sites"]},
    {"name": "Kyrgyzstan", "country": "Kyrgyzstan", "region": "Central Asia", "lat": 41.20, "lng": 74.77, "season": "summer", "interests": ["natural_beauty", "culture"]},
    {"name": "Tasmania, Australia", "country": "Australia", "region": "Oceania", "lat": -42.88, "lng": 147.33, "season": "year-round", "interests": ["natural_beauty", "wildlife", "food"]},
]


def compute_interest_scores(interests_list: list[str], config: dict) -> dict:
    """Compute interest strength scores based on user preferences."""
    ranked = config.get("interests_ranked", [])
    scores = {}
    for interest in ranked:
        if interest in interests_list:
            # Higher rank = higher score. Rank 1 (index 0) = 1.0, last = ~0.3
            rank_idx = ranked.index(interest)
            scores[interest] = round(1.0 - (rank_idx * 0.1), 2)
        else:
            scores[interest] = 0.0
    return scores


def build_destination_record(dest: dict, search_results: list, wiki_data: dict, config: dict) -> dict:
    """Build a complete destination JSON record."""
    name = dest["name"]
    season = dest.get("season", "year-round")
    display_name = f"{name} (Summer)" if season == "summer" else name
    
    # Extract reference links from search results
    ref_links = extract_reference_links(search_results, name)
    
    # Compute interest scores
    interest_scores = compute_interest_scores(dest.get("interests", []), config)
    
    # Build attractions summary from wiki data or placeholder
    attractions = wiki_data.get("wiki_summary", "")
    if not attractions or len(attractions) < 100:
        attractions = f"A destination known for: {', '.join(dest.get('interests', []))}."
    
    record = {
        "name": name,
        "display_name": display_name,
        "country": dest["country"],
        "region": dest["region"],
        "latitude": dest["lat"],
        "longitude": dest["lng"],
        "season": season,
        "seasonal_note": "",
        "recommended_days": 0,  # Will be enriched
        "best_months": [],  # Will be enriched
        "child_friendly": "Unknown",
        "elderly_friendly": "Unknown",
        "flight_duration_from_sfo": "",
        "rough_cost": "",
        "cost_breakdown": {},
        "attractions_summary": attractions,
        "reference_links": ref_links,
        "interest_categories": dest.get("interests", []),
        "interest_scores": interest_scores,
        "tags": dest.get("interests", []),
        "safety_rating": "Unknown",
        "visa_required": "Unknown",
    }
    
    return record


def load_progress() -> dict:
    """Load batch progress to allow resuming."""
    if PROGRESS_FILE.exists():
        with open(PROGRESS_FILE) as f:
            return json.load(f)
    return {"completed": [], "failed": []}


def save_progress(progress: dict):
    """Save batch progress."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    with open(PROGRESS_FILE, "w") as f:
        json.dump(progress, f, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Generate seed destination data")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of destinations (0 = all)")
    parser.add_argument("--skip-search", action="store_true", help="Skip web search, use cached data only")
    parser.add_argument("--resume", action="store_true", help="Resume from last progress checkpoint")
    args = parser.parse_args()
    
    # Setup
    config = load_config()
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    
    destinations = SUMMER_DESTINATIONS
    if args.limit:
        destinations = destinations[:args.limit]
    
    progress = load_progress() if args.resume else {"completed": [], "failed": []}
    
    total = len(destinations)
    print(f"\n{'='*60}")
    print(f"  Trip Finder — Generating {total} Destinations")
    print(f"{'='*60}\n")
    
    for i, dest in enumerate(destinations):
        slug = slugify(dest["name"])
        if dest.get("season") and dest["season"] != "year-round":
            slug = f"{slug}-{dest['season']}"
        
        # Skip if already completed
        if slug in progress["completed"]:
            print(f"[{i+1}/{total}] SKIP (already done): {dest['name']}")
            continue
        
        # Skip if file already exists
        output_file = DATA_DIR / f"{slug}.json"
        if output_file.exists() and not args.resume:
            print(f"[{i+1}/{total}] SKIP (file exists): {dest['name']}")
            progress["completed"].append(slug)
            continue
        
        print(f"\n[{i+1}/{total}] Processing: {dest['name']}")
        
        search_results = []
        wiki_data = {}
        
        if not args.skip_search:
            # Search for details
            try:
                print(f"  Searching for details...")
                search_results = search_for_destination_details(dest["name"])
                print(f"  Found {len(search_results)} search results")
            except Exception as e:
                print(f"  Search error: {e}", file=sys.stderr)
            
            # Try Wikivoyage
            try:
                wiki_url = find_wikivoyage_url(dest["name"])
                if wiki_url:
                    print(f"  Scraping Wikivoyage: {wiki_url}")
                    scraped_dir = TMP_DIR / "scraped" / slug
                    filepath = scrape_and_save(wiki_url, str(scraped_dir))
                    if filepath:
                        with open(filepath) as f:
                            wiki_text = f.read()
                        wiki_data = parse_wikivoyage_data(wiki_text, dest["name"])
                        print(f"  Wikivoyage sections: {wiki_data.get('sections_found', [])}")
                else:
                    print(f"  No Wikivoyage page found")
            except Exception as e:
                print(f"  Wikivoyage error: {e}", file=sys.stderr)
        
        # Build record
        record = build_destination_record(dest, search_results, wiki_data, config)
        
        # Save
        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2, ensure_ascii=False)
        
        print(f"  Saved: {output_file}")
        progress["completed"].append(slug)
        save_progress(progress)
        
        # Rate limit between destinations
        if not args.skip_search and i < total - 1:
            time.sleep(1)
    
    # Summary
    print(f"\n{'='*60}")
    print(f"  DONE: {len(progress['completed'])}/{total} destinations generated")
    print(f"  Failed: {len(progress.get('failed', []))}")
    print(f"  Output: {DATA_DIR}/")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
