"""
Claude Memory Lite - Persistent memory for Claude Code sessions.

Drop this folder into any project root. Claude remembers
decisions, architecture, bugs, ideas, and context across sessions.

Usage:
    python -m claude_memory brief          # Generate session brief
    python -m claude_memory add            # Add a memory (see help)
    python -m claude_memory search "query" # Search memories
    python -m claude_memory status         # Memory stats
"""

from .store import MemoryStore
from .brief import generate_brief

__all__ = ["MemoryStore", "generate_brief"]
