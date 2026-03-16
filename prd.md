# Trip Finder — Product Requirements Document

## Vision

A personal tool that builds and maintains a curated database of **100+ trip destinations** suitable for 1–2 week vacations for 1–2 people. The system uses **web search and scraping** to gather data, then presents it in a clean, searchable, filterable interface with data visualizations.

**User**: Solo traveler or couple, based in San Francisco (SFO).

---

## User Preference Config

Stored in `config/user_preferences.json`. Drives destination scoring and sort order.

```json
{
  "home_airport": "SFO",
  "interests_ranked": [
    "wildlife",
    "natural_beauty",
    "historical_sites",
    "food",
    "museum",
    "culture",
    "cities"
  ],
  "group_size": "1-2",
  "trip_length_days": { "min": 7, "max": 14 },
  "child_friendly_required": false,
  "elderly_friendly_required": false
}
```

- **`interests_ranked`** — ordered from most to least important. Each destination is tagged with relevant interest categories. The scoring algorithm weights matches by rank position (rank 1 = highest weight).
- Changing preferences re-ranks all destinations without re-fetching data.
- Future: multiple user profiles.

---

## Seasonal Destination Model

Some destinations offer **fundamentally different experiences** depending on the season. These are treated as **separate destination entries**.

**Rule**: If a destination's core activities, attractions, or character change significantly by season, it gets multiple entries. If the experience is roughly the same year-round, it's a single entry.

| Destination | Seasonal? | Entries |
|---|---|---|
| Yellowstone | Yes | "Yellowstone (Summer)" — hiking, geysers, wildlife. "Yellowstone (Winter)" — snowshoeing, frozen landscapes, wolf tracking. |
| Hawaii | No | Single entry — beach, snorkeling, hiking year-round |
| Iceland | Yes | "Iceland (Summer)" — midnight sun, puffins, highlands. "Iceland (Winter)" — northern lights, ice caves, hot springs. |
| Tokyo | Partially | "Tokyo (Spring)" — cherry blossoms. "Tokyo (General)" — year-round attractions. |

**Data model addition**: each destination record includes a `season` field:

```json
{
  "name": "Yellowstone",
  "season": "summer",
  "display_name": "Yellowstone (Summer)",
  "best_months": ["Jun", "Jul", "Aug", "Sep"],
  "seasonal_note": "Most roads and facilities open. Peak wildlife viewing.",
  ...
}
```

- `season`: `"year-round"` | `"spring"` | `"summer"` | `"fall"` | `"winter"`
- When `season` is `"year-round"`, it counts as 1 destination
- When multiple seasons exist, each is an independent entry with its own attractions, costs, and best months

---

## Core Feature: Destination Database

### Data Model

Each destination record contains:

| Field | Description | Example |
|---|---|---|
| **Name** | Destination name | "Kyoto, Japan" |
| **Country** | Country | "Japan" |
| **Region** | Geographic region | "East Asia" |
| **Latitude** | GPS latitude | 35.0116 |
| **Longitude** | GPS longitude | 135.7681 |
| **Recommended Days** | Ideal trip length (days) | 10–14 |
| **Best Months** | Months with best weather / experience | ["Mar", "Apr", "Oct", "Nov"] |
| **Child-Friendly** | Suitable for children (Yes / Qualified / No) | "Qualified" |
| **Elderly-Friendly** | Suitable for elderly travelers (Yes / Qualified / No) | "Yes" |
| **Flight Duration from SFO** | Approximate flight time (hours, including layovers) | "12h direct, ~15h with layover" |
| **Rough Cost** | Estimated total trip cost per person (flights + accommodation + food + activities) | "$3,000–$4,500" |
| **Cost Breakdown** | Rough split: flights, hotels, food, activities | { flights: 1200, hotels: 1000, food: 500, activities: 300 } |
| **Major Attractions** | 1-page summary of top things to see/do | Markdown text (see below) |
| **Reference Links** | 3–5 curated video/article introductions | [{ title, url, type: "video" \| "article" }] |
| **Season** | Season variant or year-round | "summer" |
| **Display Name** | Name with season if applicable | "Yellowstone (Summer)" |
| **Seasonal Note** | What makes this season special | "Peak wildlife viewing, all roads open" |
| **Interest Categories** | Matched to user preferences | ["wildlife", "natural_beauty"] |
| **Tags** | Searchable tags | ["culture", "temples", "food", "nature"] |
| **Safety Rating** | General safety for tourists | "High" |
| **Visa Required** | Visa requirement for US passport holders | "No (90-day waiver)" |

### Attractions Summary (1-pager)

Each destination gets a concise ~300-word summary covering:
- **Why go** — what makes this destination special
- **Top 5 attractions** — must-see places with 1-line descriptions
- **Food highlights** — signature dishes or food experiences
- **Best neighborhoods/areas** — where to stay or explore
- **Pro tip** — one insider recommendation

---

## Data Collection Pipeline

### How destinations are gathered

```
User triggers search
  → tools/search_destinations.py queries web for destinations
  → tools/scrape_single_site.py enriches each destination from travel sites
  → tools/analyze_destination.py structures & validates the data
  → Destination saved to data/destinations/<slug>.json
```

### Sources (in priority order)
1. **SerpAPI / Google Search** — find top travel destinations, blog recommendations
2. **Wikivoyage** — free, structured travel info (attractions, costs, safety)
3. **Travel blogs & guides** — curated video/article links
4. **Fallback** — manual curation when APIs are unavailable

> [!NOTE]
> The system should work without any API keys by falling back to a **seed dataset** of 30–50 popular destinations. API keys enable live enrichment & expansion to 100+.

---

## Web Interface

### Pages / Views

#### 1. Map View (Home)
The **primary interface** — an interactive world map with all destinations pinned.

- **Map**: Full-width Leaflet.js map with markers at each destination's coordinates
- **Markers**: Color-coded by interest match score (green = strong match, yellow = moderate, gray = weak)
- **Hover tooltip**: Shows key info at a glance:
  - Display name (with season if applicable)
  - Rough cost
  - Flight time from SFO
  - Recommended days
  - Top 2 interest tags
  - Best months
- **Click**: Opens the destination detail panel (slide-in or modal)
- **Cluster**: Nearby markers cluster at low zoom levels, expand on zoom
- **Filter integration**: Applying filters from the sidebar hides/shows markers in real time

#### 2. Explore (Main View)
- **Card grid** of all destinations with photo placeholder, name, cost, duration, tags
- **Filter sidebar**:
  - Budget range slider
  - Trip length (days)
  - Best month (dropdown or calendar)
  - Region (multi-select)
  - Child-friendly / Elderly-friendly toggles
  - Flight time max
- **Sort by**: cost, flight time, trip length, name
- **Search bar**: free-text search across names, tags, descriptions

#### 3. Destination Detail
- Full data display with the 1-page attraction summary
- Cost breakdown chart (bar or pie)
- Best months visual (highlighted calendar strip)
- Reference links (embedded video previews + article cards)
- "Add to comparison" button

#### 4. Compare (Side-by-Side)
- Select 2–4 destinations
- Table comparison of all fields
- Overlay charts (cost, flight time, trip length)
- Radar chart comparing scores (cost, accessibility, flight time, activities)

#### 5. Data Management
- Trigger new destination search/scrape
- View pipeline status
- Manually add/edit a destination
- Re-scrape / refresh a destination's data

---

## Visualizations

| Chart | Purpose |
|---|---|
| Cost comparison bar chart | Compare costs across selected destinations |
| Monthly weather/visit calendar | Heatmap showing best months to visit |
| Radar chart | Multi-axis comparison (cost, flight time, activities, accessibility) |
| Flight time distribution | Histogram of flight times from SFO |
| Budget breakdown (per destination) | Pie/donut chart of flights, hotels, food, activities |
| Region map | World map with destination pins |

---

## Technical Stack

| Layer | Technology |
|---|---|
| Backend | Python + Flask |
| Frontend | HTML + Vanilla CSS + JavaScript |
| Map | Leaflet.js (free, open-source, no API key needed) |
| Charts | Plotly.js (interactive, embeddable) |
| Data storage | JSON files in `data/destinations/` |
| Web search | SerpAPI (optional) or curated seed data |
| Web scraping | Requests + BeautifulSoup |
| Config | `.env` for API keys |

---

## Non-Goals (v1)

- No user accounts or authentication
- No flight/hotel booking integration
- No real-time pricing (rough estimates only)
- No mobile app (responsive web is sufficient)
- No day-by-day itinerary builder (future v2 feature)

---

## Success Criteria

1. **100+ destinations** populated with complete data
2. All destinations have structured data, a 1-page summary, and ≥3 reference links
3. Filtering and comparison work smoothly in the UI
4. Charts render interactively
5. Pipeline can add new destinations via a single action
