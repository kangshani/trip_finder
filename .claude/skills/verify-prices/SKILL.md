---
name: verify-prices
description: Look up real-time hotel prices for specific dates using Google Hotels data via SerpApi. Falls back to web search if quota exhausted.
argument-hint: <city>, <checkin> to <checkout> [hotel names...]
disable-model-invocation: true
allowed-tools: Read, Bash, WebSearch, WebFetch, Glob
---

# Verify Hotel Prices

## Objective
Look up real-time hotel prices for specific cities and dates, optionally filtering by hotel name. Compare against prices listed in an existing trip plan if one exists. Uses SerpApi Google Hotels API (250 free calls/month) with automatic fallback to Brave/DuckDuckGo web search.

## Parsing Arguments

Parse `$ARGUMENTS` to extract:
- **City** (required): e.g. "Milan", "Rome", "Florence"
- **Check-in date** (required): YYYY-MM-DD format, or natural language like "Aug 1 2026"
- **Check-out date** (required): YYYY-MM-DD format, or natural language like "Aug 3 2026"
- **Hotel names** (optional): specific hotels to look up

Examples:
- `/verify-prices Milan, 2026-08-01 to 2026-08-02`
- `/verify-prices Rome, Aug 5-8 2026, Hotel Capo d'Africa, Dharma Boutique Hotel`
- `/verify-prices Florence hotels from plans/italy-2026-03-11.html`

If dates are in natural language, convert to YYYY-MM-DD before calling the script.

## Workflow

### Step 1: Check for existing plan context

If the user references a plan file (e.g. `plans/italy-*.html` or `plans/italy-*.md`), read it to extract:
- Listed hotel names and their claimed price ranges
- The cities and dates mentioned

### Step 2: Look up prices

For each city + date range, run:
```bash
python lib/check_hotel_prices.py --city "<city>" --checkin "<YYYY-MM-DD>" --checkout "<YYYY-MM-DD>" --currency EUR
```

To look up a specific hotel:
```bash
python lib/check_hotel_prices.py --city "<city>" --hotel "<hotel name>" --checkin "<YYYY-MM-DD>" --checkout "<YYYY-MM-DD>" --currency EUR
```

To check remaining API quota:
```bash
python lib/check_hotel_prices.py --usage
```

### Step 3: Present results

**If comparing against a plan**, show a comparison table:

| Hotel | City | Listed Price | Actual Price | Difference |
|-------|------|-------------|--------------|------------|
| Hotel Manzoni | Milan | €130-180/night | €420/night | +€240-290 |

Flag any hotel where the actual price differs by more than 30% from the listed estimate.

**If standalone lookup**, show:

| Hotel | Rating | Price/Night | Total | Class |
|-------|--------|-------------|-------|-------|
| Hotel Name | 4.2 | €150 | €450 | 4-star |

### Step 4: Suggest alternatives (if prices are off)

If any listed hotel's actual price is significantly higher than the plan's estimate:
1. Show cheaper alternatives from the same search results that are in the originally estimated price range
2. Note the neighborhood/location of alternatives relative to the original pick

### Step 5: Report API usage

After all lookups, show remaining SerpApi quota:
```bash
python lib/check_hotel_prices.py --usage
```

## Notes
- SerpApi returns prices from Google Hotels, which aggregates Booking.com, Hotels.com, Expedia, etc.
- Prices are real-time and reflect actual availability for the specified dates
- Free tier: 250 searches/month. The script tracks usage automatically.
- If SerpApi quota is exhausted or key is missing, the script falls back to web search (results will be marked as estimates)
- Currency defaults to EUR but can be changed with `--currency USD` etc.
