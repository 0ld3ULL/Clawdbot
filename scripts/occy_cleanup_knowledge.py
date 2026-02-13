"""
One-time cleanup: wipe garbage exploration entries from Occy's knowledge DB.

Problem: 49 of 64 entries are raw browser debug dumps like
'AgentHistoryList(all_results=[ActionResult(is_done=False...'
These are useless. Delete them and reset feature_map confidence so
Occy re-explores everything with the new Haiku distillation pipeline.

Keeps the 15 course/tutorial entries (source = 'youtube_tutorials').

Usage:
    venv/Scripts/python.exe scripts/occy_cleanup_knowledge.py
"""

import json
import sqlite3
import sys
from pathlib import Path

DB_PATH = Path("data/occy_knowledge.db")
FEATURE_MAP_PATH = Path("data/occy_feature_map.json")

GARBAGE_SOURCES = {"occy_exploration", "pixel_exploration"}


def main():
    if not DB_PATH.exists():
        print(f"Database not found at {DB_PATH} — nothing to clean")
        sys.exit(0)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    # Count before
    cursor.execute("SELECT COUNT(*) FROM knowledge")
    total_before = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM knowledge WHERE source IN (?, ?)",
        tuple(GARBAGE_SOURCES),
    )
    garbage_count = cursor.fetchone()[0]

    print(f"Knowledge DB: {total_before} total entries")
    print(f"  Garbage exploration entries: {garbage_count}")
    print(f"  Course/other entries (keeping): {total_before - garbage_count}")

    if garbage_count == 0:
        print("Nothing to clean — DB is already clean")
        sys.exit(0)

    # Delete garbage entries
    cursor.execute(
        "DELETE FROM knowledge WHERE source IN (?, ?)",
        tuple(GARBAGE_SOURCES),
    )
    deleted = cursor.rowcount
    print(f"\nDeleted {deleted} garbage entries")

    # Rebuild FTS index
    print("Rebuilding FTS index...")
    cursor.execute("INSERT INTO knowledge_fts(knowledge_fts) VALUES('rebuild')")

    conn.commit()

    # Verify
    cursor.execute("SELECT COUNT(*) FROM knowledge")
    total_after = cursor.fetchone()[0]
    print(f"Entries remaining: {total_after}")

    conn.close()

    # Reset feature_map confidence scores
    if FEATURE_MAP_PATH.exists():
        print(f"\nResetting feature_map confidence scores...")
        with open(FEATURE_MAP_PATH) as f:
            feature_map = json.load(f)

        reset_count = 0
        for cat_name, cat_data in feature_map.get("categories", {}).items():
            for feat in cat_data.get("features", []):
                if feat.get("confidence", 0) > 0:
                    feat["confidence"] = 0.0
                    feat["explored_count"] = 0
                    feat["last_explored"] = None
                    feat["knowledge_ids"] = []
                    reset_count += 1

        with open(FEATURE_MAP_PATH, "w") as f:
            json.dump(feature_map, f, indent=2)

        print(f"Reset {reset_count} feature confidence scores to 0.0")
    else:
        print(f"\nNo feature_map at {FEATURE_MAP_PATH} — skipping reset")

    print("\nDone! Occy will re-explore all features with Haiku distillation.")


if __name__ == "__main__":
    main()
