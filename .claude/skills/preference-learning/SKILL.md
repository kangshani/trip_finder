---
name: preference-learning
description: Learn user destination preferences through pairwise A/B comparisons and provide scoring and similarity
disable-model-invocation: true
---

# Preference Learning

## Objective
Learn user destination preferences through pairwise A/B comparisons and provide preference-based scoring and similarity recommendations.

## How It Works

### Algorithm
The system uses a **Bradley-Terry model** with learned feature weights. Each destination is encoded as a 35-dimensional feature vector (interest scores, cost, location, region, season, accessibility, safety). A weight vector `w` is learned such that `score(dest) = w . features(dest)`. Pairwise comparisons update `w` via SGD on the log-likelihood.

### Pair Selection
Three phases ensure efficient learning:
1. **Exploration** (first 10): maximally different pairs to learn gross preferences
2. **Uncertainty reduction** (11-30): pairs the model is most unsure about
3. **Refinement** (30+): close pairs among top-ranked destinations

### Similarity
Cosine similarity on raw feature vectors finds destinations with similar characteristics.

## Inputs
- Destination JSON files in `data/destinations/`
- User preferences from `config/user_preferences.json` (for initial weights)

## Scripts
- `lib/preference_engine.py` — feature vectors, learning, scoring, similarity
- `lib/preference_io.py` — state persistence

## API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/api/preference/init` | Build feature vectors, set initial weights |
| GET | `/api/preference/next-pair` | Get next comparison pair |
| POST | `/api/preference/compare` | Submit A/B choice |
| GET | `/api/preference/scores` | Get all preference scores |
| GET | `/api/preference/similar?slug=X&n=10` | Find similar destinations |
| GET | `/api/preference/status` | Learning progress |
| POST | `/api/preference/reset` | Clear learned preferences |

## State File
`data/preference_state.json` stores weights, comparison history, feature vectors, and cached scores. Persists across server restarts.

## When to Re-initialize
- After adding new destinations via `/batch-discover` or `/research-destination`
- After significant destination data changes (re-enrichment)
- Re-init preserves comparison history and adapts weights to the new feature space

## Edge Cases
- **No comparisons yet**: Uses initial weights from `interests_ranked` — system is useful immediately
- **Missing cost_breakdown**: Imputed with dataset median during feature construction
- **All pairs exhausted**: 99 destinations -> 4,851 possible pairs; practically inexhaustible
- **Contradictory choices**: SGD naturally handles noise; weights converge on average preference
