---
name: enrich-attractions
description: Add key attractions with Wikimedia Commons images to destination JSON files
argument-hint: [--single slug] [--dry-run] [--skip-images] [--force]
disable-model-invocation: true
---

# Enrich Destinations with Key Attractions

## Objective
Add a structured `key_attractions` array to each destination JSON file, containing 5-10 named attractions with Wikimedia Commons images.

## Inputs
- Destination JSON files in `data/destinations/`
- Brave Search API key in `.env` (for fallback searches)

## Scripts Used
- `scripts/enrich_attractions.py` — main orchestrator
- `scripts/fetch_attraction_images.py` — Wikimedia Commons image lookup
- `lib/search_destinations.py` — Brave Search (used as fallback)

## How It Works

### Step 1: Extract attraction names from Wikivoyage
The script scrapes the destination's Wikivoyage page and extracts attraction names from `<h3>` / `<h4>` headings within the "See" and "Do" sections.

**Quality filter:** If the extracted headings look like thematic categories (e.g., "Temples", "Beaches") rather than specific named places, the results are discarded and the tool falls through to Brave search.

### Step 2: Brave Search fallback
If Wikivoyage yields fewer than 5 specific attractions, the script searches Brave for `"top 10 things to see in [destination] attractions"`, then scrapes the top travel blog result to extract attraction names from headings.

**Filtering applied:**
- Blog meta-headings stripped ("Travel Tips", "FAQ", etc.)
- Time durations removed from names (": 30 minutes")
- Extraction stops at post-article markers ("Leave a comment", "Related Posts")
- TripAdvisor skipped (messy HTML)

### Step 3: Fetch images from Wikimedia Commons
For each attraction, the script queries the Wikimedia Commons API for 1 thumbnail image (800px width). No API key needed. All images are CC-licensed.

### Step 4: Update destination JSON
The script writes a `key_attractions` array into each file:

```json
"key_attractions": [
  {
    "name": "Colosseum",
    "images": [
      {
        "url": "https://upload.wikimedia.org/wikipedia/commons/thumb/.../800px-Colosseum.jpg",
        "attribution": "Photographer Name",
        "license": "CC BY-SA 4.0"
      }
    ]
  }
]
```

## Usage

```bash
# Process all destinations
python .claude/skills/enrich-attractions/scripts/enrich_attractions.py

# Process a single destination (for testing)
python .claude/skills/enrich-attractions/scripts/enrich_attractions.py --single rome-italy-summer

# Preview without writing (dry run)
python .claude/skills/enrich-attractions/scripts/enrich_attractions.py --dry-run

# Names only, skip image fetching
python .claude/skills/enrich-attractions/scripts/enrich_attractions.py --skip-images

# Overwrite existing attractions data
python .claude/skills/enrich-attractions/scripts/enrich_attractions.py --force
```

## API Budget
- **Wikivoyage scraping:** Free, no key needed
- **Wikimedia Commons:** Free, no key needed
- **Brave Search:** 1 call per destination that fails Wikivoyage (typically ~60-70% of destinations). Budget ~70 calls per full run.

## Edge Cases
- **Wikivoyage 404:** Falls through to Brave (common for region-level entries like "Jordan")
- **Brave returns no usable results:** Destination gets 0 attractions; logged as WARNING
- **Wikimedia Commons returns no images:** Attraction entry saved with empty `images` array
- **Rate limiting:** 1s delay between HTTP requests; 0.5s between Commons API calls
- **Already enriched:** Skipped unless `--force` is used

## When to Run
- After adding new destinations via `/batch-discover` or `/research-destination`
- After consolidating duplicates via `/consolidate-destinations`
- When refreshing image URLs (Wikimedia Commons URLs are stable but occasionally change)
