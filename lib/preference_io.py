#!/usr/bin/env python3
"""
Persistence layer for preference learning state.

State file: data/preference_state.json
"""

import json
from datetime import datetime, timezone
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
STATE_FILE = PROJECT_ROOT / "data" / "preference_state.json"


def _default_state() -> dict:
    """Return a fresh empty state."""
    return {
        "version": 1,
        "weights": [],
        "comparison_history": [],
        "feature_vectors": {},
        "norm_stats": {},
        "scores": {},
        "initialized_at": None,
        "last_updated": None,
    }


def load_state() -> dict:
    """Load preference state from disk. Returns default if not found."""
    if STATE_FILE.exists():
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return _default_state()


def save_state(state: dict) -> None:
    """Write preference state to disk."""
    state["last_updated"] = datetime.now(timezone.utc).isoformat()
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def reset_state() -> None:
    """Clear all learned preferences."""
    save_state(_default_state())


def is_initialized(state: dict) -> bool:
    """Check if the engine has been initialized with feature vectors."""
    return bool(state.get("feature_vectors")) and bool(state.get("weights"))
