# Trip Finder

Personal tool for browsing 100+ curated travel destinations with filtering, comparison, and data visualizations. Built on the WAT framework (Workflows, Agents, Tools).

## Setup

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Optionally add API keys to `.env` for live data enrichment (SerpAPI, etc.). The app works without them using seed data.

## Run

```bash
python app.py
```

Open `http://localhost:5000`.

## Structure

```
app.py              Flask backend
static/             Frontend (HTML, CSS, JS) — Leaflet.js maps, Plotly.js charts
config/             User preferences (interests, travel style)
data/destinations/  JSON files, one per destination
tools/              Python scripts for search, scraping, enrichment
workflows/          Markdown SOPs for agent orchestration
```

## Features

- Interactive map with clustered markers color-coded by interest match
- Card grid with filters: continent, travel month, match score, interest tags, suitability
- Side-by-side destination comparison
- Charts: region distribution, scores, interest radar, top tags
- Data pipeline to search, scrape, and enrich new destinations
