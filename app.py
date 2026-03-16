from __future__ import annotations

from flask import Flask, jsonify, request, send_from_directory
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

app = Flask(__name__, static_folder="static")

PROJECT_ROOT = Path(__file__).parent
DATA_DIR = PROJECT_ROOT / "data" / "destinations"
CONFIG_FILE = PROJECT_ROOT / "config" / "user_preferences.json"

# Make lib importable
sys.path.insert(0, str(PROJECT_ROOT / "lib"))
from preference_engine import (
    build_feature_vectors, get_initial_weights, select_next_pair,
    update_weights, compute_scores, compute_similarity, INTEREST_KEYS,
)
from preference_io import load_state, save_state, reset_state, is_initialized
from search_destinations import get_usage as get_search_usage
from check_hotel_prices import get_serpapi_usage


# ── Helpers ──────────────────────────────────────────────────────────────────

def _load_all_destinations() -> list[dict]:
    """Load all destination JSON files."""
    destinations = []
    if DATA_DIR.exists():
        for file in DATA_DIR.glob("*.json"):
            try:
                with open(file, "r", encoding="utf-8") as f:
                    destinations.append(json.load(f))
            except Exception as e:
                print(f"Error loading {file}: {e}")
    return destinations


def _load_destination_by_slug(slug: str) -> dict | None:
    """Load a single destination by its file slug."""
    filepath = DATA_DIR / f"{slug}.json"
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def _find_dest_for_slug(slug: str, destinations: list[dict]) -> dict | None:
    """Find a destination dict matching a feature-vector slug."""
    # The feature vector slugs are derived from display_name, but file slugs
    # are the JSON filenames. Try both approaches.
    filepath = DATA_DIR / f"{slug}.json"
    if filepath.exists():
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    # Fallback: search by matching slugified display_name
    for d in destinations:
        display = d.get("display_name", d.get("name", ""))
        s = display.lower()
        for ch in "(),.'\"!":
            s = s.replace(ch, "")
        s = s.replace("&", "and")
        s = "-".join(s.split())
        if s == slug:
            return d
    return None


# ── Existing Routes ──────────────────────────────────────────────────────────

@app.route("/")
def serve_index():
    return send_from_directory("static", "index.html")


@app.route("/api/config")
def get_config():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return jsonify(json.load(f))
    return jsonify({})


@app.route("/api/destinations")
def get_destinations():
    destinations = _load_all_destinations()
    return jsonify({"destinations": destinations})


# ── Preference API ───────────────────────────────────────────────────────────

@app.route("/api/preference/init", methods=["POST"])
def preference_init():
    """Initialize or reinitialize the preference engine."""
    destinations = _load_all_destinations()
    if not destinations:
        return jsonify({"error": "No destinations found"}), 404

    feature_vectors, norm_stats = build_feature_vectors(destinations)

    # Load existing state to preserve history, or start fresh
    state = load_state()
    old_history = state.get("comparison_history", [])

    # Load user preferences for initial weights
    user_prefs = {}
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            user_prefs = json.load(f)

    # If we have existing weights from prior learning, keep them
    # (unless dimensions changed). Otherwise, use initial weights.
    if state.get("weights") and len(state["weights"]) == len(next(iter(feature_vectors.values()))):
        weights = state["weights"]
    else:
        weights = get_initial_weights(user_prefs)

    state["feature_vectors"] = feature_vectors
    state["norm_stats"] = norm_stats
    state["weights"] = weights
    state["comparison_history"] = old_history
    state["scores"] = compute_scores(feature_vectors, weights)
    if not state.get("initialized_at"):
        state["initialized_at"] = datetime.now(timezone.utc).isoformat()

    save_state(state)

    return jsonify({
        "status": "ok",
        "destination_count": len(feature_vectors),
        "feature_dims": len(weights),
        "comparisons_preserved": len(old_history),
    })


@app.route("/api/preference/next-pair")
def preference_next_pair():
    """Get the next pair of destinations to compare."""
    state = load_state()
    if not is_initialized(state):
        return jsonify({"error": "Engine not initialized. Call POST /api/preference/init first."}), 400

    try:
        slug_a, slug_b, phase = select_next_pair(
            state["feature_vectors"],
            state["weights"],
            state["comparison_history"],
        )
    except ValueError as e:
        return jsonify({"error": str(e)}), 400

    destinations = _load_all_destinations()
    dest_a = _find_dest_for_slug(slug_a, destinations)
    dest_b = _find_dest_for_slug(slug_b, destinations)

    return jsonify({
        "slug_a": slug_a,
        "slug_b": slug_b,
        "destination_a": dest_a,
        "destination_b": dest_b,
        "comparison_number": len(state["comparison_history"]) + 1,
        "phase": phase,
    })


@app.route("/api/preference/compare", methods=["POST"])
def preference_compare():
    """Submit a comparison result."""
    state = load_state()
    if not is_initialized(state):
        return jsonify({"error": "Engine not initialized"}), 400

    body = request.get_json()
    if not body:
        return jsonify({"error": "JSON body required"}), 400

    slug_a = body.get("slug_a")
    slug_b = body.get("slug_b")
    choice = body.get("choice")

    if not all([slug_a, slug_b, choice]):
        return jsonify({"error": "slug_a, slug_b, and choice are required"}), 400
    if choice not in ("a", "b", "equal"):
        return jsonify({"error": "choice must be 'a', 'b', or 'equal'"}), 400

    fv = state["feature_vectors"]
    if slug_a not in fv or slug_b not in fv:
        return jsonify({"error": "Unknown destination slug"}), 400

    # Update weights
    n = len(state["comparison_history"])
    state["weights"] = update_weights(
        state["weights"], fv[slug_a], fv[slug_b], choice, n
    )

    # Record comparison
    state["comparison_history"].append({
        "slug_a": slug_a,
        "slug_b": slug_b,
        "choice": choice,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })

    # Recompute scores
    state["scores"] = compute_scores(fv, state["weights"])

    save_state(state)

    return jsonify({
        "status": "ok",
        "comparisons_done": len(state["comparison_history"]),
        "phase": select_next_pair.__module__ and (
            "exploration" if n + 1 < 10 else
            "uncertainty_reduction" if n + 1 < 30 else
            "refinement"
        ),
    })


@app.route("/api/preference/scores")
def preference_scores():
    """Get preference scores for all destinations."""
    state = load_state()
    if not is_initialized(state):
        return jsonify({"error": "Engine not initialized"}), 400

    scores = state.get("scores", {})
    destinations = _load_all_destinations()

    result = []
    for slug, score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        dest = _find_dest_for_slug(slug, destinations)
        name = dest.get("display_name", slug) if dest else slug
        result.append({
            "slug": slug,
            "name": name,
            "score": score,
        })

    # Add rank
    for i, item in enumerate(result):
        item["rank"] = i + 1

    return jsonify({"scores": result, "comparisons_done": len(state.get("comparison_history", []))})


@app.route("/api/preference/similar")
def preference_similar():
    """Get destinations similar to a given one."""
    state = load_state()
    if not is_initialized(state):
        return jsonify({"error": "Engine not initialized"}), 400

    slug = request.args.get("slug", "")
    n = int(request.args.get("n", 10))

    if not slug:
        return jsonify({"error": "slug parameter required"}), 400

    similar = compute_similarity(slug, state["feature_vectors"], top_n=n)
    destinations = _load_all_destinations()

    result = []
    for sim_slug, sim_score in similar:
        dest = _find_dest_for_slug(sim_slug, destinations)
        name = dest.get("display_name", sim_slug) if dest else sim_slug
        result.append({
            "slug": sim_slug,
            "name": name,
            "similarity": sim_score,
        })

    return jsonify({"query": slug, "similar": result})


@app.route("/api/preference/status")
def preference_status():
    """Get learning progress status."""
    state = load_state()
    initialized = is_initialized(state)
    n = len(state.get("comparison_history", []))

    response = {
        "initialized": initialized,
        "comparisons_done": n,
        "phase": (
            "not_started" if not initialized else
            "exploration" if n < 10 else
            "uncertainty_reduction" if n < 30 else
            "refinement"
        ),
        "destination_count": len(state.get("feature_vectors", {})),
    }

    if initialized and state.get("scores"):
        scores = state["scores"]
        top = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:5]
        destinations = _load_all_destinations()
        response["top_destinations"] = [
            {
                "slug": s,
                "name": (_find_dest_for_slug(s, destinations) or {}).get("display_name", s),
                "score": sc,
            }
            for s, sc in top
        ]

    return jsonify(response)


@app.route("/api/preference/reset", methods=["POST"])
def preference_reset():
    """Reset all learned preferences."""
    reset_state()
    return jsonify({"status": "ok"})


# ── Search API Usage ─────────────────────────────────────────────────────────

@app.route("/api/usage")
def api_usage():
    """Return search API usage stats for all providers."""
    usage = get_search_usage()
    usage["serpapi"] = get_serpapi_usage()
    return jsonify(usage)


# ── Static Fallback ──────────────────────────────────────────────────────────

@app.route("/<path:path>")
def serve_static(path):
    return send_from_directory("static", path)


if __name__ == "__main__":
    app.run(debug=True, port=5000)
