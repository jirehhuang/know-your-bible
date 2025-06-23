# app/utils/harmony.py

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

## Allow relative imports when running as a standalone script
sys.path.append(str(Path(__file__).resolve().parents[2]))

from data.references.get_resource_references import extract_references

HARMONY_PATH = os.path.join("data", "harmony", "harmony.json")

# Load harmony data globally
with open(HARMONY_PATH, "r", encoding="utf-8") as f:
    HARMONY_DATA = json.load(f)

GOSPELS = {"Matthew", "Mark", "Luke", "John"}


def ref_in_range(ref: str, target: str) -> bool:
    """
    Returns True if `ref` (e.g., "Luke 5:4") is included in `target` (e.g., "Luke 5:1-6").
    """
    ref_parsed = extract_references(ref)
    target_parsed = extract_references(target)

    if not ref_parsed or not target_parsed:
        return False

    ref_verse = ref_parsed[0]["verses"][0]
    target_verses = target_parsed[0]["verses"]

    return ref_verse in target_verses


def get_harmony_entries_for_verse(actual_ref: str) -> List[Dict[str, Any]]:
    """
    Given a reference string like 'Matthew 12:4',
    returns a list of harmony entries (category, subject, references)
    that include this verse and are found in the loaded harmony data.
    """
    extracted = extract_references(actual_ref)
    if not extracted:
        return []

    verse_info = extracted[0]
    book = verse_info["book"]
    verse = verse_info["verses"][0]

    if book not in GOSPELS:
        return []

    matching_entries = []
    for entry in HARMONY_DATA:
        for ref in entry.get("references", []):
            if ref_in_range(verse, ref):
                matching_entries.append({
                    "category": entry.get("category"),
                    "subject": entry.get("subject"),
                    "references": entry.get("references")
                })
                break
    return matching_entries


# === Standalone Testing ===

def _print_entries(title: str, entries: List[Dict[str, Any]]):
    print(f"\n=== {title} ===")
    for e in entries:
        print(f"- [{e['category']}] {e['subject']}")
        print(f"  → {e['references']}")


if __name__ == "__main__":
    print("Running harmony tests...")

    # Test ref_in_range
    assert ref_in_range("Luke 5:4", "Luke 5:4"), "Direct match failed"
    assert ref_in_range("Luke 5:4", "Luke 5:1-6"), "Range match failed"
    assert not ref_in_range("Luke 5:4", "Luke 6:1-6"), "Incorrect match passed"

    # Test Matthew 5:15 should match 2 entries
    matt_entries = get_harmony_entries_for_verse("Matthew 5:15")
    assert len(matt_entries) == 2, f"Expected 2 entries, got {len(matt_entries)}"
    _print_entries("Matthew 5:15", matt_entries)

    # Test Luke 5:4 should match relevant entries
    luke_entries = get_harmony_entries_for_verse("Luke 5:4")
    _print_entries("Luke 5:4", luke_entries)

    print("\n✅ All tests passed.")
