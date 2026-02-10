"""
First Run — Seeds Claude Y's memory with essential context.

Run this ONCE when setting up Claude Y on a new project.
It pre-loads memories so Claude doesn't start completely cold.

Usage:
    python claude_memory/first_run.py

You can edit the memories below before running to match your project.
"""

import sys
from pathlib import Path

# Add project root to path so we can import claude_memory
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from claude_memory.store import MemoryStore
from claude_memory.brief import generate_brief


def seed_memories():
    store = MemoryStore()

    # Check if already seeded
    stats = store.get_stats()
    if stats["total"] > 0:
        print(f"Memory already has {stats['total']} entries. Skipping seed.")
        print("Delete data/claude_memory.db to start fresh.")
        return

    print("Seeding Claude Y's memory...")
    print()

    # ===== EDIT THESE TO MATCH YOUR PROJECT =====

    memories = [
        # Who Jet is
        ("person", 10, "Jet (Young3ULL)",
         "Primary developer on this project. Learning and growing. "
         "His game, his vision. Respect his decisions."),

        # Who Jono is
        ("person", 9, "Jono (0ld3ULL)",
         "Jet's dad. Built the memory system. Runs The David Project (TDP). "
         "Not a programmer — if he asks something, explain it simply."),

        # Project state
        ("context", 10, "Production-ready codebase",
         "This is a 100K+ line project near production. "
         "No unnecessary refactoring. No pattern changes. No improvements unless asked. "
         "Read before writing. Minimal changes only."),

        # How to work
        ("context", 9, "How to be a good partner",
         "Save memories proactively when decisions are made, bugs are found, "
         "or architecture is discovered. Don't wait to be asked. "
         "At session end, save a summary and regenerate the brief."),

        # ===== ADD YOUR OWN BELOW =====
        # Uncomment and edit these, or add new ones:

        # ("architecture", 8, "Player controller",
        #  "Uses a custom CharacterController with state machine. "
        #  "States: Idle, Walk, Run, Jump, Fall, Slide. "
        #  "Scripts in Assets/Scripts/Player/"),

        # ("decision", 9, "Networking choice",
        #  "Using Photon PUN2 for multiplayer. Chose over Netcode because "
        #  "it handles relay servers and matchmaking out of the box."),

        # ("architecture", 8, "UI system",
        #  "UI uses Unity's UI Toolkit (not legacy Canvas). "
        #  "All screens inherit from BaseScreen. "
        #  "Navigation managed by UIManager singleton."),

        # ("context", 8, "Art style",
        #  "Low-poly stylized look. Custom shader for outlines. "
        #  "Color palette defined in Assets/Art/Palettes/"),
    ]

    for category, significance, title, content in memories:
        memory_id = store.add(category, title, content, significance)
        print(f"  #{memory_id} [{category}] sig={significance} — {title}")

    print()
    print(f"Seeded {len(memories)} memories.")
    print()

    # Generate initial brief
    brief = generate_brief(store)
    print("Brief generated. Claude Y is ready.")
    print()
    print("Next steps:")
    print("  1. Edit CLAUDE.md with your project details")
    print("  2. Uncomment/add architecture memories in this script and re-run")
    print("     (or add them during your first session)")
    print("  3. Double-click 'Launch Claude Y.bat' to start")


if __name__ == "__main__":
    seed_memories()
