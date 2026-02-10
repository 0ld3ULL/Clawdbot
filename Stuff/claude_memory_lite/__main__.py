"""
CLI for Claude Memory Lite.

Usage:
    python -m claude_memory brief
    python -m claude_memory add <category> <significance> "title" "content"
    python -m claude_memory search "query"
    python -m claude_memory status
    python -m claude_memory delete <id>

Categories: decision, architecture, bug, idea, context, person, task, session
Significance: 1-10 (8+ = critical/permanent, 5-7 = important, 1-4 = minor)

Examples:
    python -m claude_memory add decision 9 "Use Photon for networking" "Chose Photon PUN2 over Netcode because it handles relay servers and is battle-tested for indie games"
    python -m claude_memory add bug 6 "Physics jitter at low FPS" "Rigidbody interpolation breaks below 30fps on the player controller"
    python -m claude_memory add context 8 "Jet is learning" "Jet is getting started with game dev. Explain things clearly, no jargon without context"
    python -m claude_memory search "networking"
"""

import sys

from .store import MemoryStore
from .brief import generate_brief


def main():
    store = MemoryStore()
    args = sys.argv[1:]

    if not args:
        print(__doc__)
        return

    command = args[0]

    if command == "brief":
        brief = generate_brief(store)
        print(f"Brief generated ({len(brief)} chars)")
        print("---")
        print(brief)

    elif command == "add":
        if len(args) < 5:
            print("Usage: python -m claude_memory add <category> <significance> \"title\" \"content\"")
            print()
            print("Categories: decision, architecture, bug, idea, context, person, task, session")
            print("Significance: 1-10")
            return

        category = args[1]
        try:
            significance = int(args[2])
        except ValueError:
            print(f"Significance must be a number 1-10, got: {args[2]}")
            return

        title = args[3]
        content = args[4]

        memory_id = store.add(category, title, content, significance)
        print(f"Added memory #{memory_id}: [{category}] sig={significance} - {title}")

    elif command == "search":
        if len(args) < 2:
            print("Usage: python -m claude_memory search \"query\"")
            return

        query = " ".join(args[1:])
        results = store.search(query)

        if not results:
            print(f"No memories found for: {query}")
            return

        print(f"Found {len(results)} memories:")
        print()
        for m in results:
            print(f"  #{m['id']} [{m['category']}] sig={m['significance']} | {m['title']}")
            print(f"    {m['content'][:100]}")
            print(f"    ({m['session_date']})")
            print()

    elif command == "status":
        stats = store.get_stats()
        print("Claude Memory Status")
        print("=" * 40)
        print(f"Total memories: {stats['total']}")
        print(f"Critical (sig 8+): {stats['critical']}")
        print(f"First memory: {stats['first_memory'] or 'none'}")
        print()
        if stats["by_category"]:
            print("By category:")
            for cat, count in stats["by_category"].items():
                print(f"  {cat}: {count}")

    elif command == "delete":
        if len(args) < 2:
            print("Usage: python -m claude_memory delete <id>")
            return
        try:
            memory_id = int(args[1])
            store.delete(memory_id)
            print(f"Deleted memory #{memory_id}")
        except ValueError:
            print(f"Invalid ID: {args[1]}")

    else:
        print(f"Unknown command: {command}")
        print()
        print("Commands: brief, add, search, status, delete")


if __name__ == "__main__":
    main()
