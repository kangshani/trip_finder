---
name: audit-attractions
description: Detect and fix attraction names that are action phrases or sentences instead of proper nouns
argument-hint: [--single slug] [--json] [--fix]
disable-model-invocation: true
---

# Audit & Fix Attraction Names

## Objective
Detect and fix attraction names that read as action phrases, sentences, or marketing copy instead of proper noun-form place/experience names. A good attraction name is something you'd see on a map or in a guidebook index — not a sentence telling you what to do.

## Why This Matters
Attraction names sourced from travel blogs often come in imperative form ("Set out on your Safari Game Drive") because blog headings are written as calls to action. These need to be normalized to proper noun-form names ("Safari Game Drive") for a clean, professional data set.

## Inputs
- Destination JSON files in `data/destinations/`

## Script
- `scripts/audit_attractions.py` — scans attraction names and flags quality issues

## Issue Types Detected

| Issue | Example (Bad) | Example (Good) |
|-------|---------------|-----------------|
| `imperative` | "Visit The Anne Frank House" | "Anne Frank House" |
| `pronoun` | "Set out on your Safari Game Drive" | "Safari Game Drive" |
| `too_long` | 60+ char names that are sentences | Concise place name |
| `has_description` | "Acropolis: legends carved in marble" | "The Acropolis" |

## Steps

### 1. Run the audit
```bash
python .claude/skills/audit-attractions/scripts/audit_attractions.py
```
This prints a grouped report of all flagged attraction names.

Optional flags:
```bash
# Audit a single destination
python .claude/skills/audit-attractions/scripts/audit_attractions.py --single masai-mara-kenya-summer

# Get machine-readable output
python .claude/skills/audit-attractions/scripts/audit_attractions.py --json

# Generate a fix plan showing each name that needs rewriting
python .claude/skills/audit-attractions/scripts/audit_attractions.py --fix
```

### 2. Review and fix flagged names
For each flagged attraction, rewrite the name to be a proper noun-form attraction name:

**Rewriting rules:**
1. **Strip imperative verbs** — "Explore the Jordaan" -> "The Jordaan"
2. **Remove pronouns** — "Set out on your Safari Game Drive" -> "Safari Game Drive"
3. **Drop embedded descriptions** — "Wat Pho - The Reclining Buddha" -> "Wat Pho (Reclining Buddha)" or just "Wat Pho"
4. **Extract the actual place/experience name** — "Savor the Best Meat of Your Life at an Asado" -> "Traditional Asado"
5. **Keep it recognizable** — The fixed name should still be something a traveler would recognize and could search for

**Use judgment on edge cases:**
- "Witness the Wildebeest Migration" -> "Great Wildebeest Migration" (the event is the attraction)
- "Hot Air Balloon over the Mara" is fine as-is (it's descriptive but noun-form)
- "Changing of the Guards" is a proper name for that ceremony — keep it

### 3. Apply fixes to destination JSON files
Edit each destination file's `key_attractions[].name` field with the corrected name. Preserve all other fields (images, etc.) unchanged.

### 4. Re-run the audit to verify
```bash
python .claude/skills/audit-attractions/scripts/audit_attractions.py
```
Confirm that the issue count has dropped. Some names may still be flagged if the best name genuinely starts with a verb (e.g., "Changing of the Guards") — that's fine as long as it's been reviewed.

## When to Run
- After running `/enrich-attractions` on new destinations
- After bulk imports via `/batch-discover`
- Periodically as a data quality check

## Edge Cases
- **False positives on articles:** "The Acropolis" is fine — articles at the start of proper names are expected and not flagged
- **False positives on legitimate verb-form names:** "Changing of the Guards" technically starts with a verb but is the official name. Review and leave as-is.
- **Names that are purely generic:** "Get your ticket" or "Relax on Tropical Islands" need complete rewriting, not just verb stripping. Use destination context to pick a proper name.
- **Cultural experiences vs. places:** "Traditional Asado" or "Tango Show" are valid noun-form names for experiences that aren't physical places.
