"""
David's Memory System

Three stores, like a human brain:
- PeopleStore: Relationships (never fade)
- KnowledgeStore: FLIPT company knowledge (never fade)
- EventStore: World events (fade based on significance)

MemoryManager orchestrates all three.
"""

from .memory_manager import MemoryManager
from .people_store import PeopleStore, Person
from .knowledge_store import KnowledgeStore, Knowledge
from .event_store import EventStore, Event

__all__ = [
    "MemoryManager",
    "PeopleStore", "Person",
    "KnowledgeStore", "Knowledge",
    "EventStore", "Event",
]
