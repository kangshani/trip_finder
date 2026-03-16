---
name: batch-discover
description: Discover and populate 100+ destination records across multiple categories, regions, and interest types
argument-hint: [target-count]
disable-model-invocation: true
---

# Batch Discover Destinations

## Objective
Discover and populate 100+ destination records by searching the web for trip recommendations across multiple categories, regions, and interest types.

## Inputs
- User preferences from `config/user_preferences.json` (interests, trip length, group size)
- Target count: `$ARGUMENTS` or default 100

## Strategy

Generate search queries across these dimensions:

### By Interest Category
One query per ranked interest from user preferences:
```
"best wildlife destinations for 1-2 week trip"
"most beautiful natural scenery travel destinations"
"best historical sites to visit 2 week vacation"
"top food travel destinations worth visiting"
"best museums in the world worth traveling for"
"cultural immersion travel destinations"
"best cities to visit for 1-2 weeks"
```

### By Region
Ensure global coverage:
```
"best travel destinations in [region]"
```
Regions: Southeast Asia, East Asia, South Asia, Europe (Western, Eastern, Northern, Southern), Central America, South America, East Africa, Southern Africa, Oceania, Middle East, Caribbean

### By Season
```
"best winter travel destinations from San Francisco"
"best summer travel destinations 2 weeks"
```

### By Traveler Type
```
"best destinations for couples 2 week trip"
"solo travel destinations 1-2 weeks"
```

## Steps

### 1. Generate query list
Build the full list of search queries from the dimensions above. Deduplicate expected overlaps.

### 2. Run searches
**Script**: `lib/search_destinations.py`
```bash
python lib/search_destinations.py --query "<query>" --max-results 10
```
- Run each query
- Collect all unique destination names mentioned across results
- Save master list to `.tmp/discovered_destinations.json`

### 3. Deduplicate
- Merge duplicates (e.g., "Kyoto" and "Kyoto, Japan")
- Identify seasonal variants (check if sources mention distinct seasonal experiences)
- Mark each as year-round or split into seasonal entries
- Output: `.tmp/destination_queue.json`

### 4. Research each destination
For each destination in the queue, invoke the `/research-destination` skill.
- Process in batches of 10 to avoid rate limits
- Wait 5s between batches
- Skip any destination that already exists in `data/destinations/`

### 5. Validate coverage
After all destinations are processed:
- Check total count >= target
- Check region diversity (>= 2 destinations per major region)
- Check interest coverage (>= 10 destinations per interest category)
- List gaps and suggest additional queries if needed

## Output
- `data/destinations/*.json` — all destination records
- `data/discovery_report.json` — summary: total found, by region, by interest, gaps

## Edge Cases
- **Too many results**: Prioritize destinations that match top-ranked interests.
- **Duplicate detection**: Use fuzzy matching on destination name + country to catch variants.
- **API quota exhausted**: Save progress. Record where the batch stopped in `.tmp/batch_progress.json`. Resume from there on next run.
- **Seasonal split ambiguity**: When unsure if a destination needs seasonal split, default to year-round. Add a `needs_seasonal_review: true` flag for manual review later.

## Scripts
- `scripts/generate_seed_data.py` — orchestrates the full batch pipeline
