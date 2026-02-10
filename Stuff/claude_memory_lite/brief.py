"""
Brief Generator - Creates the session brief Claude reads at startup.

The brief is the single most important file. It's what Claude reads
first every session to know who you are, what you're working on,
and what decisions have been made.
"""

from datetime import datetime
from pathlib import Path

from .store import MemoryStore

BRIEF_PATH = Path("claude_brief.md")


def generate_brief(store: MemoryStore = None, output_path: Path = None) -> str:
    """
    Generate a session brief from memories.

    Writes to claude_brief.md in the project root.
    Returns the brief text.
    """
    if store is None:
        store = MemoryStore()

    output_path = output_path or BRIEF_PATH
    memories = store.get_for_brief()
    stats = store.get_stats()

    lines = []
    lines.append("# Claude Session Brief")
    lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append(f"*Memories: {stats['total']} total, {stats['critical']} critical*")
    lines.append("")

    # --- Critical memories (always shown) ---
    if memories["critical"]:
        lines.append("## Critical (Always Remember)")
        lines.append("")
        for m in memories["critical"]:
            lines.append(f"### [{m['category'].upper()}] {m['title']}")
            lines.append(f"{m['content']}")
            lines.append(f"*sig={m['significance']} | {m['session_date']}*")
            lines.append("")

    # --- Important memories (last 30 days) ---
    if memories["important"]:
        lines.append("## Important (Last 30 Days)")
        lines.append("")
        for m in memories["important"]:
            lines.append(f"- **[{m['category']}] {m['title']}**: {m['content']}")
        lines.append("")

    # --- Recent memories (last 7 days) ---
    if memories["recent"]:
        lines.append("## Recent")
        lines.append("")
        for m in memories["recent"]:
            lines.append(f"- [{m['category']}] {m['title']}: {m['content']}")
        lines.append("")

    # --- Stats ---
    if stats["by_category"]:
        lines.append("## Memory Stats")
        lines.append("")
        for cat, count in stats["by_category"].items():
            lines.append(f"- {cat}: {count}")
        lines.append("")

    brief_text = "\n".join(lines)

    # Write to file
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(brief_text)

    return brief_text
