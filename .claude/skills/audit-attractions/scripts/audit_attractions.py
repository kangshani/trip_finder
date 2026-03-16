#!/usr/bin/env python3
"""
Audit attraction names across all destination JSON files for quality issues.

Detects:
  - Imperative/action phrases ("Visit the Colosseum" → "Colosseum")
  - Pronouns making names sound like suggestions ("Set out on your Safari")
  - Overly long names (> 60 chars, likely sentences)
  - Embedded descriptions after colons/dashes ("Acropolis: legends carved in marble")
  - Generic/vague names ("Get your ticket", "Relax on Tropical Islands")

Usage:
    python tools/audit_attractions.py                     # Report all issues
    python tools/audit_attractions.py --single masai-mara-kenya-summer
    python tools/audit_attractions.py --fix               # Auto-fix and write changes
    python tools/audit_attractions.py --fix --dry-run     # Preview fixes without writing
"""

import argparse
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.parent  # scripts/ -> audit-attractions/ -> skills/ -> .claude/ -> project root
DATA_DIR = PROJECT_ROOT / "data" / "destinations"

# ── Detection Rules ──────────────────────────────────────────────────────────

# Verbs that commonly start imperative/action-style attraction names
IMPERATIVE_VERBS = (
    "admire", "bask", "be amazed", "browse", "capture", "catch", "chase",
    "climb", "create", "cruise", "delight", "discover", "dive", "embark",
    "embrace", "enjoy", "experience", "explore", "feast", "find", "get",
    "go", "grab", "head", "hike", "hover", "hunt", "immerse", "indulge",
    "join", "learn", "make", "marvel", "paddle", "photograph", "pick",
    "relax", "ride", "roam", "sail", "sample", "savor", "see", "seek",
    "set out", "shop", "snap", "soak", "stroll", "surf", "swim", "take",
    "taste", "trek", "try your hand", "uncover", "venture", "visit",
    "walk", "wander", "watch", "witness",
)

# Build regex: match verb at start of string followed by a word boundary
_verb_pattern = "|".join(re.escape(v) for v in sorted(IMPERATIVE_VERBS, key=len, reverse=True))
RE_IMPERATIVE = re.compile(rf"^({_verb_pattern})\b", re.IGNORECASE)

RE_PRONOUN = re.compile(r"\b(your|you|our|we)\b", re.IGNORECASE)
RE_DESCRIPTION = re.compile(r"[–—]|:\s+\w+\s+\w+\s+\w+")

MAX_NAME_LENGTH = 60


def audit_attraction(name: str) -> list[str]:
    """Return a list of issue tags for a given attraction name."""
    issues = []
    if RE_IMPERATIVE.search(name):
        issues.append("imperative")
    if RE_PRONOUN.search(name):
        issues.append("pronoun")
    if len(name) > MAX_NAME_LENGTH:
        issues.append("too_long")
    if RE_DESCRIPTION.search(name):
        issues.append("has_description")
    return issues


# ── Reporting ────────────────────────────────────────────────────────────────

def audit_file(filepath: Path) -> list[dict]:
    """Audit a single destination file. Returns list of issue dicts."""
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    display = data.get("display_name", data.get("name", filepath.stem))
    results = []

    for attr in data.get("key_attractions", []):
        name = attr["name"]
        issues = audit_attraction(name)
        if issues:
            results.append({
                "destination": display,
                "file": filepath.name,
                "name": name,
                "issues": issues,
            })
    return results


def print_report(all_issues: list[dict]) -> None:
    """Print a human-readable audit report."""
    if not all_issues:
        print("No issues found. All attraction names look clean.")
        return

    # Group by destination
    by_dest: dict[str, list[dict]] = {}
    for issue in all_issues:
        by_dest.setdefault(issue["destination"], []).append(issue)

    print(f"\n{'='*70}")
    print(f"ATTRACTION NAME AUDIT REPORT")
    print(f"{'='*70}")
    print(f"Total issues: {len(all_issues)} across {len(by_dest)} destinations\n")

    for dest, issues in sorted(by_dest.items()):
        print(f"  {dest} ({len(issues)} issues)")
        for issue in issues:
            tags = ", ".join(issue["issues"])
            print(f"    [{tags}] \"{issue['name']}\"")
        print()


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Audit attraction names for quality issues")
    parser.add_argument("--single", "-s", help="Audit a single destination by slug")
    parser.add_argument("--fix", action="store_true",
                        help="Generate a fix report (names flagged for agent review)")
    parser.add_argument("--dry-run", action="store_true",
                        help="With --fix, preview changes without writing")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON (for piping to other tools)")
    args = parser.parse_args()

    if not DATA_DIR.exists():
        print(f"Error: {DATA_DIR} not found", file=sys.stderr)
        sys.exit(1)

    if args.single:
        filepath = DATA_DIR / f"{args.single}.json"
        if not filepath.exists():
            print(f"Error: {filepath} not found", file=sys.stderr)
            sys.exit(1)
        files = [filepath]
    else:
        files = sorted(DATA_DIR.glob("*.json"))

    all_issues = []
    for f in files:
        all_issues.extend(audit_file(f))

    if args.json:
        print(json.dumps(all_issues, indent=2, ensure_ascii=False))
    elif args.fix:
        # Output a structured fix plan for the agent to review and apply
        if not all_issues:
            print("No issues to fix.")
            return

        by_file: dict[str, list[dict]] = {}
        for issue in all_issues:
            by_file.setdefault(issue["file"], []).append(issue)

        print(f"\nFix plan: {len(all_issues)} attraction names across {len(by_file)} files")
        print("Each name below needs to be rewritten as a proper noun-form attraction name.\n")

        for filename, issues in sorted(by_file.items()):
            print(f"File: {filename}")
            for issue in issues:
                tags = ", ".join(issue["issues"])
                print(f"  CURRENT:  \"{issue['name']}\"")
                print(f"  ISSUES:   {tags}")
                print(f"  ACTION:   Rewrite as noun-form attraction name")
                print()
    else:
        print_report(all_issues)

    # Summary stats
    total_files = len(files)
    total_attractions = 0
    for f in files:
        with open(f) as fh:
            d = json.load(fh)
        total_attractions += len(d.get("key_attractions", []))

    clean = total_attractions - len(all_issues)
    pct = (clean / total_attractions * 100) if total_attractions else 0
    print(f"\nSummary: {clean}/{total_attractions} attractions clean ({pct:.0f}%)")


if __name__ == "__main__":
    main()
