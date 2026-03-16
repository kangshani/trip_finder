---
name: generate-visualizations
description: Create interactive charts and map data from the destination database for the web UI
disable-model-invocation: true
---

# Generate Visualizations

## Objective
Create interactive charts and map data from the destination database for display in the web UI.

## Inputs
- All destination records from `data/destinations/*.json`
- User preferences from `config/user_preferences.json`

## Steps

### 1. Load all destination data
Read every JSON file in `data/destinations/` into memory.

### 2. Generate charts

Charts to generate:

#### a. Cost Comparison (bar chart)
- X-axis: destination display names
- Y-axis: rough cost per person
- Color: by region
- Sorted by cost ascending
- Output: `data/charts/cost_comparison.json`

#### b. Flight Time Distribution (histogram)
- Bins: 0-4h, 4-8h, 8-12h, 12-16h, 16-20h, 20h+
- Each bar shows count of destinations in that range
- Output: `data/charts/flight_time_distribution.json`

#### c. Best Months Heatmap (calendar grid)
- Rows: destinations
- Columns: Jan-Dec
- Color intensity: how good each month is for visiting
- Output: `data/charts/best_months_heatmap.json`

#### d. Interest Match Radar (per destination)
- Axes: each interest category
- Values: how well the destination matches each interest
- Overlay user's ranked interests for context
- Output: `data/charts/radar/<slug>.json`

#### e. Budget Breakdown (per destination, donut)
- Slices: flights, hotels, food, activities
- Output: `data/charts/budget/<slug>.json`

### 3. Prepare map data
- Extract lat/lng, display_name, rough_cost, flight_duration, recommended_days, top interest tags, best_months for each destination
- Compute marker color based on preference score
- Output: `data/charts/map_markers.json`

## Output
- `data/charts/*.json` — Plotly chart configs (loaded by frontend)
- `data/charts/map_markers.json` — marker data for Leaflet map

## When to Re-run
- After adding/updating destinations
- After changing user preferences (re-scores interest matches, re-colors markers)
