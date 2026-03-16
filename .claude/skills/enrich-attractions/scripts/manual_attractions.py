#!/usr/bin/env python3
"""
Manually set key_attractions for destinations where automated scraping failed.
Fetches Wikimedia Commons images for each attraction.

Usage:
    python tools/manual_attractions.py
    python tools/manual_attractions.py --skip-images
"""

import argparse
import json
import sys
import time
from pathlib import Path

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent.parent.parent.parent  # scripts/ -> enrich-attractions/ -> skills/ -> .claude/ -> project root
DATA_DIR = PROJECT_ROOT / "data" / "destinations"
sys.path.insert(0, str(SCRIPT_DIR))
from fetch_attraction_images import search_commons_images

# ── Manual attraction lists for problematic destinations ─────────────────────

MANUAL_ATTRACTIONS = {
    # 7 destinations that returned NO attractions
    "banff-canada-summer": [
        "Lake Louise", "Moraine Lake", "Johnston Canyon", "Peyto Lake",
        "Icefields Parkway", "Banff Gondola & Sulphur Mountain",
        "Bow Falls", "Lake Minnewanka",
    ],
    "cusco-peru-summer": [
        "Machu Picchu", "Sacsayhuamán", "Sacred Valley of the Incas",
        "Rainbow Mountain (Vinicunca)", "Plaza de Armas Cusco",
        "Qorikancha (Temple of the Sun)", "Ollantaytambo", "Moray Terraces",
    ],
    "galapagos-islands-ecuador-summer": [
        "Charles Darwin Research Station", "Tortuga Bay",
        "Kicker Rock (León Dormido)", "Isabela Island",
        "Los Túneles", "Pinnacle Rock (Bartolomé Island)",
        "North Seymour Island", "Sierra Negra Volcano",
    ],
    "havana-cuba-summer": [
        "Old Havana (Habana Vieja)", "El Malecón", "El Capitolio",
        "Plaza de la Catedral", "Fusterlandia", "Museo de la Revolución",
        "Tropicana Cabaret", "Fábrica de Arte Cubano",
    ],
    "london-england-summer": [
        "Tower of London", "British Museum", "Buckingham Palace",
        "Westminster Abbey", "Tower Bridge", "Hyde Park",
        "Borough Market", "Tate Modern", "Camden Market",
    ],
    "seoul-south-korea-summer": [
        "Gyeongbokgung Palace", "Bukchon Hanok Village", "N Seoul Tower",
        "Changdeokgung Palace", "Myeongdong", "Hongdae",
        "Gwangjang Market", "Lotte World Tower",
    ],
    "zanzibar-tanzania-summer": [
        "Stone Town", "Nungwi Beach", "Prison Island",
        "Jozani Chwaka Bay National Park", "Spice Farms",
        "The Rock Restaurant", "Mnemba Atoll", "Forodhani Gardens Night Market",
    ],
    # 6 destinations with bad scraping artifacts (excluding colombia which was fine)
    "fez-morocco-summer": [
        "Fez el Bali (Old Medina)", "Bou Inania Madrasa",
        "Chouara Tannery", "Al-Attarine Madrasa", "Dar Batha Museum",
        "Merenid Tombs", "Bab Bou Jeloud (Blue Gate)", "Mellah (Jewish Quarter)",
    ],
    "slovenia-summer": [
        "Lake Bled", "Ljubljana Old Town", "Postojna Cave",
        "Predjama Castle", "Triglav National Park", "Lake Bohinj",
        "Škocjan Caves", "Piran",
    ],
    "svalbard-norway-summer": [
        "Longyearbyen", "Magdalenefjorden", "Nordenskiöld Glacier",
        "Ny-Ålesund", "Pyramiden (Ghost Town)", "Arctic Cathedral",
        "Svalbard Global Seed Vault (exterior)", "Polar Bear Safari",
    ],
    "swiss-alps-summer": [
        "Jungfraujoch (Top of Europe)", "Matterhorn", "Lake Oeschinen",
        "Aletsch Glacier", "Lauterbrunnen Valley", "Grindelwald First",
        "Glacier Express Route", "Trümmelbach Falls",
    ],
    "tasmania-australia": [
        "Cradle Mountain", "Wineglass Bay", "Port Arthur Historic Site",
        "MONA (Museum of Old and New Art)", "Bay of Fires",
        "Gordon River Cruise", "Mount Wellington (kunanyi)",
        "Salamanca Market",
    ],
    "varanasi-india-summer": [
        "Dashashwamedh Ghat (Ganga Aarti)", "Kashi Vishwanath Temple",
        "Assi Ghat", "Manikarnika Ghat", "Sarnath",
        "Ramnagar Fort", "Boat Ride on the Ganges", "Banaras Hindu University",
    ],
}


def process_destination(slug: str, attractions: list[str], skip_images: bool = False):
    """Write manual attractions to a destination file."""
    filepath = DATA_DIR / f"{slug}.json"
    if not filepath.exists():
        print(f"  ERROR: {filepath} not found")
        return

    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    print(f"\nProcessing: {data.get('name', slug)}")
    key_attractions = []

    for name in attractions:
        entry = {"name": name, "images": []}

        if not skip_images:
            city = data.get("name", slug).split(",")[0].strip()
            query = f"{name} {city}"
            images = search_commons_images(query, count=1)
            if images:
                entry["images"] = [
                    {"url": img["thumb_url"], "attribution": img["attribution"], "license": img["license"]}
                    for img in images
                ]
                print(f"  {name}: 1 image")
            else:
                print(f"  {name}: no image found")
            time.sleep(0.5)
        else:
            print(f"  {name}")

        key_attractions.append(entry)

    data["key_attractions"] = key_attractions

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"  Saved {len(key_attractions)} attractions to {slug}.json")


def main():
    parser = argparse.ArgumentParser(description="Manually set attractions for problematic destinations")
    parser.add_argument("--skip-images", action="store_true", help="Skip image fetching")
    parser.add_argument("--single", "-s", help="Process a single slug")
    args = parser.parse_args()

    targets = {args.single: MANUAL_ATTRACTIONS[args.single]} if args.single else MANUAL_ATTRACTIONS

    for slug, attractions in targets.items():
        process_destination(slug, attractions, skip_images=args.skip_images)

    print(f"\nDone: {len(targets)} destinations fixed")


if __name__ == "__main__":
    main()
