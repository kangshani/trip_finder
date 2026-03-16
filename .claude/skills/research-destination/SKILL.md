---
name: research-destination
description: Research a travel destination from scratch and produce a structured JSON record
argument-hint: <destination-name> [season]
disable-model-invocation: true
---

# Research Destination

## Objective
Gather comprehensive data about a trip destination and produce a structured JSON record ready for the database.

## Inputs
- `$0` — destination name (e.g. "Kyoto, Japan")
- `$1` (optional) — season: "spring", "summer", "fall", "winter", or omit for year-round
- User preferences from `config/user_preferences.json`

## Steps

### 1. Search for general info
**Script**: `lib/search_destinations.py`
```bash
python lib/search_destinations.py --query "$0 travel guide" --max-results 10
```
- Output: `.tmp/search_results/<slug>.json` with URLs and snippets

### 2. Scrape top sources
**Script**: `lib/scrape_single_site.py`
```bash
python lib/scrape_single_site.py --url "<url>" --output ".tmp/scraped/<slug>/"
```
- Run against the top 3-5 URLs from step 1
- Prioritize: Wikivoyage, Lonely Planet, travel blogs
- Output: raw text files in `.tmp/scraped/<slug>/`

### 3. Extract structured data
Read the scraped text and extract into a destination JSON:
- Recommended trip length, best months, costs, safety, visa
- Child/elderly friendliness
- GPS coordinates (lat/lng)
- Flight duration from SFO (uses home_airport from config)
- Interest category tags (matched to preference categories)
- 1-page attractions summary
- 3-5 reference links (videos + articles)
- Output: `data/destinations/<slug>.json`

### 4. Validate the record
Check that the output JSON has all required fields:
- [ ] name, country, region, latitude, longitude
- [ ] display_name, season, seasonal_note (if seasonal)
- [ ] recommended_days, best_months
- [ ] child_friendly, elderly_friendly
- [ ] flight_duration_from_sfo
- [ ] rough_cost, cost_breakdown
- [ ] attractions_summary (>= 200 words)
- [ ] reference_links (>= 3 links)
- [ ] interest_categories (>= 1 tag)
- [ ] safety_rating, visa_required

If any field is missing, re-run step 3 with additional scraped sources.

## Output
- `data/destinations/<slug>.json` — complete destination record

## Edge Cases
- **No search results**: Try alternate queries (country name, region name). If still nothing, flag for manual curation.
- **Seasonal variant exists**: Check `data/destinations/` for existing entries with same base name. Use consistent naming: `<slug>-summer.json`, `<slug>-winter.json`.
- **Rate limiting on search API**: Back off 30s and retry. Max 3 retries. If persistent, switch to fallback scraping of Wikivoyage directly.
- **Scraping blocked**: Skip that source, try the next URL from search results.
