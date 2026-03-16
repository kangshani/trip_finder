---
name: plan-trip
description: Create a high-level travel plan with highlights, neighborhoods, practical tips, and current pricing for any destination worldwide
argument-hint: <destination>
disable-model-invocation: true
allowed-tools: Read, Grep, Bash, WebSearch, WebFetch, Glob
---

# Plan Trip

## Objective
Create a high-level, actionable travel plan for any destination worldwide through an iterative, conversational process. The plan covers highlights, must-see attractions, best neighborhoods, practical logistics, and current pricing — NOT a rigid day-by-day itinerary.

## Inputs
- `$0` — destination name (e.g. "Tokyo", "Patagonia", "Lisbon, Portugal")
- Remaining details gathered interactively from the user (see Turn 1)

## Turn 1: Gather Preferences

Read `config/user_preferences.json` to populate sensible defaults, then present them to the user for confirmation or adjustment.

Information to gather:
1. **Dates or duration** — "When are you going, or how many days?" (default: user_preferences.trip_length_days)
2. **Budget level** — budget / comfort / luxury (default: user_preferences.travel_style)
3. **Interests and priorities** — what matters most? (default: user_preferences.interests_ranked, top 3-4)
4. **Group composition** — solo, couple, family, friends? (default: user_preferences.group_size)
5. **Constraints** — mobility limitations, dietary needs, visa concerns? (default: none)
6. **Home airport** — for flight search context (default: user_preferences.home_airport)

Present these as a concise checklist with defaults pre-filled. Example:

> I'll plan your trip to **$0**! Let me confirm a few details — adjust any or say "looks good":
>
> - Duration: **7-14 days**
> - Budget: **comfort**
> - Top interests: **wildlife, natural beauty, historical sites, food**
> - Group: **1-2 travelers**
> - Constraints: **none**
> - Flying from: **SFO**

**Wait for the user's response before proceeding.**

## Turn 2: Overview & Highlights

### 2a. Check existing data
Search `data/destinations/` for a matching destination JSON file:
```bash
ls data/destinations/ | grep -i "<slug-pattern>"
```
If found, read it for supplementary context (cost breakdown, attractions, seasonal notes, interest categories).

### 2b. Research overview and highlights
Run targeted web searches:
```bash
python lib/search_destinations.py --query "$0 travel guide highlights" --max-results 8
python lib/search_destinations.py --query "$0 must see attractions top things to do" --max-results 5
python lib/search_destinations.py --query "$0 weather <travel_month> what to expect" --max-results 3
```

Also use the WebSearch tool for quick supplementary lookups (visa requirements, currency, safety).

Scrape the top 2-3 most promising URLs:
```bash
python lib/scrape_single_site.py --url "<url>" --output ".tmp/scraped/plan-<slug>/"
```

### 2c. Present to user
Show:
- **At a Glance** summary table (visa, currency, timezone, weather, safety)
- **Why \<Destination\>** — a 2-3 sentence pitch tailored to their stated interests
- **Top Highlights** organized by theme (cultural, nature, food, etc.) — each with a brief description and practical note

**Ask the user**: "Does this look right? Anything to add, remove, or focus on?"

**Wait for the user's response before proceeding.**

## Turn 3: Neighborhoods & Logistics

### 3a. Gather hotel preferences

Read `config/user_preferences.json` for saved hotel preferences. If `hotel_preferences` exists, present as defaults:
- Min rating: Google 4.3+ (relax to 4.0 if all 4.3+ are above budget)
- Min reviews: 500+
- Nightly budget: €100-200 (adjust for destination cost of living)
- Required: hotel type, free cancellation, walkable location, 24h front desk, private bathroom

Ask the user to confirm or adjust these for this specific trip.

### 3b. Research neighborhoods and logistics
```bash
python lib/search_destinations.py --query "$0 best neighborhoods where to stay" --max-results 5
python lib/search_destinations.py --query "flights from <home_airport> to $0 <travel_month>" --max-results 5
python lib/search_destinations.py --query "$0 getting around public transport" --max-results 3
```

Scrape 1-2 top results for neighborhood details.

### 3c. Look up real hotel prices

For each city/base in the itinerary, use `check_hotel_prices.py` to get real-time prices:
```bash
python lib/check_hotel_prices.py --city "<city> <neighborhood>" --checkin <YYYY-MM-DD> --checkout <YYYY-MM-DD> --currency <currency>
```

Filter results by user's hotel preferences:
1. Type = hotel (exclude vacation rentals)
2. Google rating >= min_rating (4.3+, relax to 4.0 if needed)
3. Reviews >= min_reviews (500+)
4. Price within nightly budget range

Pick the top 3 hotels per city that best match all criteria.

### 3d. Present to user
Show:
- **Best Neighborhoods** — character/vibe, what each is best for, where to stay and eat
- **Getting There** — flight options from home airport with estimated prices, airport transfer options
- **Where to Stay** — verified hotel recommendations with real prices, ratings, review counts, and star class (sourced from Google Hotels)
- **Getting Around** — transit options, passes worth buying, walking-friendly areas

**Ask the user**: "Any neighborhoods you already know you want? Budget adjustments? Preferences for hotel style?"

**Wait for the user's response before proceeding.**

## Turn 4: Food, Tips & Events

### 4a. Research
```bash
python lib/search_destinations.py --query "$0 best food restaurants must try dishes" --max-results 5
python lib/search_destinations.py --query "$0 events festivals <travel_month> <travel_year>" --max-results 5
python lib/search_destinations.py --query "$0 travel tips safety scams" --max-results 3
```

For each of the user's top 2-3 interests, run a targeted search:
```bash
python lib/search_destinations.py --query "$0 best <interest>" --max-results 3
```

### 4b. Present to user
Show:
- **Food & Dining** — must-try dishes, recommended restaurants/food areas, dietary accommodation notes
- **Seasonal Events** — festivals, events, or seasonal highlights during their travel window
- **Practical Tips** — money (ATMs, cards, tipping), connectivity, safety, cultural norms, packing essentials
- **Budget Breakdown** — estimated costs table (flights, accommodation, food, activities, transport, misc, total)

**Ask the user**: "Any dietary needs I should account for? Anything else to include or adjust?"

**Wait for the user's response before proceeding.**

## Turn 5: Finalize & Save

1. Compile all reviewed and approved sections into the full plan using the template at `.claude/skills/plan-trip/template.md`
2. Incorporate ALL user feedback from Turns 2-4
3. Add a **Useful Links** section with official tourism site, transit map, visa info, weather reference, and booking resources
4. Create output directory and save:
   ```bash
   mkdir -p plans/
   ```
5. Write the completed plan to `plans/<destination-slug>-<YYYY-MM-DD>.md`
6. Present a brief summary:
   - Confirm file location
   - Highlight 2-3 key takeaways
   - Offer to revise any section further

## Content Principles
- Be **SPECIFIC**: name actual places, actual price ranges, actual neighborhoods
- Be **CURRENT**: use web research data, not just training knowledge
- Be **PRACTICAL**: include tips a traveler can act on immediately
- Be **HONEST**: if information is uncertain, say so; include "verify before booking" notes
- **NO rigid day-by-day schedules**: organize by theme/area, let the traveler mix and match
- Include **source URLs** for key claims (hotel prices, flight estimates, attraction hours)

## Edge Cases
- **Destination not recognized**: If search results return nothing useful, ask the user to clarify (city vs region vs country) or provide an alternative spelling
- **No flights found**: Note that connecting flights may be needed; suggest checking Google Flights directly and provide the link
- **Visa complexity**: If visa requirements are unclear or vary by nationality, flag explicitly and link to the official immigration page
- **Budget mismatch**: If the destination is significantly more expensive than the user's budget level, note transparently and suggest cost-saving strategies
- **Overlapping destinations in database**: If multiple seasonal variants exist (e.g., `tokyo-summer.json`, `tokyo-spring.json`), use the one matching the user's travel dates
- **Rate limiting on search API**: Back off 30s and retry. Max 3 retries. If persistent, fall back to WebSearch tool
