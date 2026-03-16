---
name: refresh-destination
description: Update an existing destination record with fresh web data
argument-hint: <destination-slug>
disable-model-invocation: true
---

# Refresh Destination

## Objective
Update an existing destination record with fresh data from the web. Use when data may be outdated (costs changed, new attractions, etc.).

## Inputs
- `$0` — the slug of the existing destination (e.g., "kyoto-japan" or "yellowstone-summer")

## Steps

### 1. Load existing record
Read `data/destinations/$0.json` to get current data.

### 2. Re-scrape sources
Invoke `/scrape-website` against the original reference links.

Also search for any new sources:
```bash
python lib/search_destinations.py --query "<display_name> travel guide 2025" --max-results 5
```

### 3. Re-analyze
Read the scraped text and merge new data with the existing record:
- The `--existing` flag tells the analysis to merge new data with existing, preserving any manual edits
- Fields that changed are logged to `.tmp/refresh_log/<slug>.diff.json`

### 4. Review changes
Print a diff summary of what changed. If cost changed by >30% or safety rating changed, flag for manual review.

### 5. Re-generate visualizations
If the record was updated, invoke `/generate-visualizations`.

## Output
- Updated `data/destinations/<slug>.json`
- Diff log in `.tmp/refresh_log/<slug>.diff.json`

## Edge Cases
- **Destination no longer exists** (e.g., closed attraction): Add a `status: "needs_review"` flag but don't delete.
- **Conflicting data across sources**: Prefer official tourism sites > Wikivoyage > blogs.
