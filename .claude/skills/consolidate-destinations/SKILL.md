---
name: consolidate-destinations
description: Identify and merge duplicate destination entries to prevent redundant options
disable-model-invocation: true
---

# Consolidate Duplicate Destinations

## Objective
Identify and merge destination entries that represent the same trip, preventing users from seeing redundant options.

## When to Run
- After batch discovery (`/batch-discover`) adds new destinations
- During periodic quality checks on the data set

## Step 1: Identify Duplicates

Two destinations are duplicates when **any** of these apply:

| Rule | Example |
|------|---------|
| **Landmark inside a city** — the attraction is located within the city and every visitor to one visits the other | Angkor Wat is inside Siem Reap |
| **Subset itinerary** — one entry's recommended trip is entirely contained within the other's | Petra (4 days) is a stop on the Jordan (8 days) itinerary |
| **Same region, overlapping attractions** — entries share >70% of their key attractions and the same best months | Cusco & Machu Picchu (MP is always accessed from Cusco) |
| **City inside a broader region trip** — one entry is a specific city that the broader entry already covers as a major stop | Queenstown is a hub within a South Island road trip |

### NOT duplicates (keep separate)
- Different cities in the same country with distinct character (e.g., Marrakech vs Fez, Hanoi vs Ha Long Bay)
- City + surrounding countryside when they target different traveller types (e.g., Edinburgh vs Scottish Highlands)
- Adjacent regions in different countries (e.g., Torres del Paine vs Patagonia Argentina)
- Same country entries with different coordinates >200 km apart and <30% attraction overlap

## Step 2: Decide Which Entry to Keep

Always keep the **broader** entry (more recommended days, wider geographic scope). The narrower entry gets merged in and deleted.

## Step 3: Merge Rules

For each field, follow these rules:

| Field | Rule |
|-------|------|
| `name` / `display_name` | Update to mention both if the sub-destination is famous (e.g., "Cusco & Machu Picchu, Peru") |
| `latitude` / `longitude` | Keep the broader entry's coordinates |
| `seasonal_note` | Combine both notes if they add distinct info |
| `recommended_days` | Keep the larger value |
| `best_months` | Union of both lists |
| `rough_cost` | Widen the range (lower floor, higher ceiling) |
| `cost_breakdown` | Take the higher value per category |
| `attractions_summary` | Concatenate both SOURCE blocks |
| `reference_links` | Merge lists, deduplicate by URL, cap at ~8-10 links |
| `interest_categories` / `tags` | Union of both |
| `interest_scores` | Take the max score per category |
| `child_friendly` / `elderly_friendly` | Keep the more restrictive value (No > Qualified > Yes) |
| All other fields | Keep from the broader entry |

## Step 4: Delete the Redundant File

Remove the narrower entry's JSON file from `data/destinations/`.

## Step 5: Verify

- Confirm total destination count decreased by the expected number
- Spot-check the merged file for valid JSON
- Load the app and confirm the merged destination renders correctly

## Consolidation Log

| Date | Kept | Removed | Reason |
|------|------|---------|--------|
| 2026-02-26 | siem-reap-cambodia-summer | angkor-wat-cambodia-summer | Angkor Wat is a temple complex inside Siem Reap |
| 2026-02-26 | jordan-summer | petra-jordan-summer | Petra is a stop on the broader Jordan itinerary |
| 2026-02-26 | cusco-peru-summer | machu-picchu-peru-summer | Machu Picchu is accessed from Cusco; same trip |
| 2026-02-26 | new-zealand-south-island | queenstown-new-zealand | Queenstown is a hub within the South Island road trip |
| 2026-02-26 | dubrovnik-to-split-coast-croatia-summer | dubrovnik-croatia-summer | Dubrovnik is the starting point of the Dalmatian coast trip |
