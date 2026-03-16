#!/usr/bin/env python3
"""
Preference engine for destination similarity and learning.

Builds feature vectors from destination data, learns user preferences
through pairwise comparisons (Bradley-Terry model), and computes
destination similarity via cosine distance.
"""

import json
import math
import random
from pathlib import Path

import numpy as np

# ── Feature Schema ───────────────────────────────────────────────────────────

INTEREST_KEYS = [
    "wildlife", "natural_beauty", "historical_sites",
    "food", "museum", "culture", "cities",
]

COST_KEYS = ["flights", "hotels", "food", "activities"]

REGIONS = [
    "Caribbean", "Central America", "Central Asia", "East Africa",
    "East Asia", "Eastern Europe", "Middle East", "North Africa",
    "North America", "Northern Europe", "Oceania", "South America",
    "South Asia", "Southeast Asia", "Southern Africa",
    "Southern Europe", "Western Europe",
]

# Feature vector layout:
#   [0:7]   interest scores (7)
#   [7:11]  cost breakdown (4)
#   [11:13] lat, lon (2)
#   [13]    recommended_days (1)
#   [14:31] region one-hot (17)
#   [31]    season (1)
#   [32:34] child_friendly, elderly_friendly (2)
#   [34]    safety_rating (1)
# Total: 35 dimensions

FEATURE_DIM = 35

_FRIENDLY_MAP = {"Yes": 1.0, "Qualified": 0.5, "No": 0.0}
_SAFETY_MAP = {"High": 1.0, "Moderate": 0.5, "Low": 0.0}
_SEASON_MAP = {"summer": 1.0, "year-round": 0.5, "winter": 0.0,
               "spring": 0.75, "fall": 0.75}


# ── Feature Vector Construction ──────────────────────────────────────────────

def _compute_norm_stats(destinations: list[dict]) -> dict:
    """Compute min/max for numeric fields that need normalization."""
    stats = {}
    for key in COST_KEYS:
        values = [d.get("cost_breakdown", {}).get(key, 0) for d in destinations]
        values = [v for v in values if v > 0]
        if values:
            stats[f"cost_{key}"] = {"min": min(values), "max": max(values)}
        else:
            stats[f"cost_{key}"] = {"min": 0, "max": 1}

    lats = [d.get("latitude", 0) for d in destinations]
    lons = [d.get("longitude", 0) for d in destinations]
    stats["latitude"] = {"min": min(lats), "max": max(lats)}
    stats["longitude"] = {"min": min(lons), "max": max(lons)}

    days = [d.get("recommended_days", 7) for d in destinations]
    stats["recommended_days"] = {"min": min(days), "max": max(days)}

    # Compute medians for missing-value imputation
    for key in COST_KEYS:
        values = sorted(v for d in destinations
                        for v in [d.get("cost_breakdown", {}).get(key, 0)] if v > 0)
        stats[f"cost_{key}"]["median"] = values[len(values) // 2] if values else 0

    return stats


def _normalize(value: float, stat: dict) -> float:
    """Min-max normalize a value to [0, 1]."""
    range_ = stat["max"] - stat["min"]
    if range_ == 0:
        return 0.5
    return (value - stat["min"]) / range_


def _dest_to_vector(dest: dict, norm_stats: dict) -> np.ndarray:
    """Convert a single destination dict to a feature vector."""
    v = np.zeros(FEATURE_DIM, dtype=np.float64)

    # Interest scores [0:7]
    scores = dest.get("interest_scores", {})
    for i, key in enumerate(INTEREST_KEYS):
        v[i] = scores.get(key, 0.0)

    # Cost breakdown [7:11]
    cost = dest.get("cost_breakdown", {})
    for i, key in enumerate(COST_KEYS):
        raw = cost.get(key, 0)
        stat = norm_stats[f"cost_{key}"]
        if raw <= 0:
            raw = stat.get("median", 0)
        v[7 + i] = _normalize(raw, stat)

    # Geographic [11:13]
    v[11] = _normalize(dest.get("latitude", 0), norm_stats["latitude"])
    v[12] = _normalize(dest.get("longitude", 0), norm_stats["longitude"])

    # Recommended days [13]
    v[13] = _normalize(dest.get("recommended_days", 7), norm_stats["recommended_days"])

    # Region one-hot [14:31]
    region = dest.get("region", "")
    if region in REGIONS:
        v[14 + REGIONS.index(region)] = 1.0

    # Season [31]
    v[31] = _SEASON_MAP.get(dest.get("season", "year-round"), 0.5)

    # Accessibility [32:34]
    v[32] = _FRIENDLY_MAP.get(dest.get("child_friendly", "No"), 0.0)
    v[33] = _FRIENDLY_MAP.get(dest.get("elderly_friendly", "No"), 0.0)

    # Safety [34]
    v[34] = _SAFETY_MAP.get(dest.get("safety_rating", "Moderate"), 0.5)

    return v


def build_feature_vectors(destinations: list[dict]) -> tuple[dict, dict]:
    """Build feature vectors for all destinations.

    Args:
        destinations: list of destination dicts (loaded from JSON files)

    Returns:
        (feature_vectors, norm_stats) where feature_vectors maps
        slug -> list[float] and norm_stats stores normalization params.
    """
    norm_stats = _compute_norm_stats(destinations)
    vectors = {}
    for dest in destinations:
        slug = _dest_slug(dest)
        vectors[slug] = _dest_to_vector(dest, norm_stats).tolist()
    return vectors, norm_stats


def _dest_slug(dest: dict) -> str:
    """Derive the file slug from a destination dict."""
    name = dest.get("display_name", dest.get("name", "unknown"))
    # Convert "Rome, Italy (Summer)" -> "rome-italy-summer"
    slug = name.lower()
    for ch in "(),.'\"!":
        slug = slug.replace(ch, "")
    slug = slug.replace("&", "and")
    parts = slug.split()
    return "-".join(parts)


# ── Initial Weights ──────────────────────────────────────────────────────────

def get_initial_weights(user_prefs: dict) -> list:
    """Derive initial weight vector from user preferences.

    Interest dimensions get weights based on rank position.
    Other dimensions start at 0.
    """
    w = np.zeros(FEATURE_DIM, dtype=np.float64)
    ranked = user_prefs.get("interests_ranked", INTEREST_KEYS)
    for i, interest in enumerate(INTEREST_KEYS):
        if interest in ranked:
            rank_idx = ranked.index(interest)
            w[i] = 1.0 - (rank_idx * 0.12)
        else:
            w[i] = 0.0
    return w.tolist()


# ── Preference Learning (Bradley-Terry with SGD) ────────────────────────────

def _sigmoid(x: float) -> float:
    """Numerically stable sigmoid."""
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    else:
        ex = math.exp(x)
        return ex / (1.0 + ex)


def update_weights(weights: list, f_a: list, f_b: list,
                   choice: str, n_comparisons: int) -> list:
    """Update weight vector based on a pairwise comparison.

    Args:
        weights: current weight vector (list of floats)
        f_a: feature vector for destination A
        f_b: feature vector for destination B
        choice: "a", "b", or "equal"
        n_comparisons: total comparisons done so far (for LR decay)

    Returns:
        Updated weight vector (list of floats)
    """
    w = np.array(weights, dtype=np.float64)
    fa = np.array(f_a, dtype=np.float64)
    fb = np.array(f_b, dtype=np.float64)

    lr = 0.15 / (1.0 + 0.02 * n_comparisons)

    score_a = float(np.dot(w, fa))
    score_b = float(np.dot(w, fb))
    diff = fa - fb

    if choice == "a":
        p_a = _sigmoid(score_a - score_b)
        w += lr * (1.0 - p_a) * diff
    elif choice == "b":
        p_b = _sigmoid(score_b - score_a)
        w += lr * (1.0 - p_b) * (-diff)
    # "equal" → no update

    # L2 regularization
    w *= (1.0 - 0.001)

    return w.tolist()


# ── Scoring ──────────────────────────────────────────────────────────────────

def compute_scores(feature_vectors: dict, weights: list) -> dict:
    """Compute preference scores for all destinations.

    Returns dict mapping slug -> score (higher = more preferred).
    Scores are normalized to 0-100 range.
    """
    w = np.array(weights, dtype=np.float64)
    raw_scores = {}
    for slug, fv in feature_vectors.items():
        raw_scores[slug] = float(np.dot(w, np.array(fv)))

    # Normalize to 0-100
    if not raw_scores:
        return {}
    min_s = min(raw_scores.values())
    max_s = max(raw_scores.values())
    range_s = max_s - min_s
    if range_s == 0:
        return {slug: 50.0 for slug in raw_scores}

    return {
        slug: round((s - min_s) / range_s * 100, 1)
        for slug, s in raw_scores.items()
    }


# ── Pair Selection ───────────────────────────────────────────────────────────

def _get_phase(n_comparisons: int) -> str:
    """Determine the current learning phase."""
    if n_comparisons < 10:
        return "exploration"
    elif n_comparisons < 30:
        return "uncertainty_reduction"
    else:
        return "refinement"


def select_next_pair(feature_vectors: dict, weights: list,
                     history: list) -> tuple:
    """Select the next pair of destinations to compare.

    Args:
        feature_vectors: dict of slug -> feature vector
        weights: current weight vector
        history: list of comparison dicts with slug_a, slug_b

    Returns:
        (slug_a, slug_b, phase)
    """
    slugs = list(feature_vectors.keys())
    if len(slugs) < 2:
        raise ValueError("Need at least 2 destinations")

    n = len(history)
    phase = _get_phase(n)

    # Build set of already-compared pairs
    shown_pairs = set()
    for h in history:
        pair = tuple(sorted([h["slug_a"], h["slug_b"]]))
        shown_pairs.add(pair)

    # Count recent appearances (last 5 comparisons)
    recent_count = {}
    for h in history[-5:]:
        recent_count[h["slug_a"]] = recent_count.get(h["slug_a"], 0) + 1
        recent_count[h["slug_b"]] = recent_count.get(h["slug_b"], 0) + 1

    def is_valid_pair(a, b):
        pair = tuple(sorted([a, b]))
        if pair in shown_pairs:
            return False
        if recent_count.get(a, 0) >= 3 or recent_count.get(b, 0) >= 3:
            return False
        return True

    w = np.array(weights, dtype=np.float64)
    vecs = {s: np.array(v) for s, v in feature_vectors.items()}

    if phase == "exploration":
        # Max feature distance
        best_pair = None
        best_dist = -1
        candidates = [(a, b) for i, a in enumerate(slugs)
                       for b in slugs[i+1:] if is_valid_pair(a, b)]
        # Sample to avoid O(n^2) for large sets
        if len(candidates) > 200:
            candidates = random.sample(candidates, 200)
        for a, b in candidates:
            dist = float(np.linalg.norm(vecs[a] - vecs[b]))
            if dist > best_dist:
                best_dist = dist
                best_pair = (a, b)

    elif phase == "uncertainty_reduction":
        # Min score difference (most uncertain)
        best_pair = None
        best_diff = float("inf")
        candidates = [(a, b) for i, a in enumerate(slugs)
                       for b in slugs[i+1:] if is_valid_pair(a, b)]
        if len(candidates) > 300:
            candidates = random.sample(candidates, 300)
        for a, b in candidates:
            sa = float(np.dot(w, vecs[a]))
            sb = float(np.dot(w, vecs[b]))
            diff = abs(sa - sb)
            if diff < best_diff:
                best_diff = diff
                best_pair = (a, b)

    else:  # refinement
        # Focus on top-20 by score, min score difference
        scores = {s: float(np.dot(w, vecs[s])) for s in slugs}
        top_slugs = sorted(scores, key=scores.get, reverse=True)[:20]
        best_pair = None
        best_diff = float("inf")
        for i, a in enumerate(top_slugs):
            for b in top_slugs[i+1:]:
                if not is_valid_pair(a, b):
                    continue
                diff = abs(scores[a] - scores[b])
                if diff < best_diff:
                    best_diff = diff
                    best_pair = (a, b)

    # Fallback: random valid pair
    if best_pair is None:
        valid = [(a, b) for i, a in enumerate(slugs)
                 for b in slugs[i+1:]
                 if tuple(sorted([a, b])) not in shown_pairs]
        if valid:
            best_pair = random.choice(valid)
        else:
            # All pairs exhausted — pick random
            a, b = random.sample(slugs, 2)
            best_pair = (a, b)

    # Randomize order so A/B position doesn't bias
    if random.random() < 0.5:
        best_pair = (best_pair[1], best_pair[0])

    return best_pair[0], best_pair[1], phase


# ── Similarity ───────────────────────────────────────────────────────────────

def compute_similarity(slug: str, feature_vectors: dict,
                       top_n: int = 10) -> list:
    """Find the most similar destinations to a given one.

    Uses cosine similarity on feature vectors.

    Returns:
        List of (slug, similarity_score) tuples, sorted by similarity desc.
    """
    if slug not in feature_vectors:
        return []

    query = np.array(feature_vectors[slug])
    query_norm = np.linalg.norm(query)
    if query_norm == 0:
        return []

    results = []
    for other_slug, fv in feature_vectors.items():
        if other_slug == slug:
            continue
        other = np.array(fv)
        other_norm = np.linalg.norm(other)
        if other_norm == 0:
            continue
        sim = float(np.dot(query, other) / (query_norm * other_norm))
        results.append((other_slug, round(sim, 4)))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:top_n]
