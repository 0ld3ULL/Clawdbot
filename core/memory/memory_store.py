"""
Memory Store - SQLite-based persistent memory for David.

Stores three types of memories:
- Episodic: Specific events with timestamps (tweets, research, interactions)
- Semantic: Knowledge and patterns (topics, preferences, insights)
- Short-term: Active session context (cleared on session end)
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)

DB_PATH = Path("data/memory.db")


@dataclass
class Memory:
    """A single memory entry."""
    id: Optional[int] = None
    memory_type: str = "episodic"  # episodic, semantic, short_term
    category: str = ""  # tweet, research, interaction, knowledge, preference
    content: str = ""
    context: str = ""  # Additional context
    importance: float = 0.5  # 0-1, higher = more important
    created_at: str = ""
    accessed_at: str = ""
    access_count: int = 0
    compressed: bool = False
    tags: str = ""  # JSON array of tags


class MemoryStore:
    """SQLite-based memory storage with full-text search."""

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Main memories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                memory_type TEXT NOT NULL,
                category TEXT NOT NULL,
                content TEXT NOT NULL,
                context TEXT,
                importance REAL DEFAULT 0.5,
                created_at TEXT NOT NULL,
                accessed_at TEXT,
                access_count INTEGER DEFAULT 0,
                compressed INTEGER DEFAULT 0,
                tags TEXT
            )
        """)

        # Full-text search index
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                content, context, tags,
                content='memories',
                content_rowid='id'
            )
        """)

        # Triggers to keep FTS in sync
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, content, context, tags)
                VALUES (new.id, new.content, new.context, new.tags);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content, context, tags)
                VALUES ('delete', old.id, old.content, old.context, old.tags);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, content, context, tags)
                VALUES ('delete', old.id, old.content, old.context, old.tags);
                INSERT INTO memories_fts(rowid, content, context, tags)
                VALUES (new.id, new.content, new.context, new.tags);
            END
        """)

        # Session tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at TEXT NOT NULL,
                ended_at TEXT,
                summary TEXT,
                events_count INTEGER DEFAULT 0
            )
        """)

        # Memory compression log
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS compression_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                compressed_at TEXT NOT NULL,
                memories_before INTEGER,
                memories_after INTEGER,
                summary TEXT
            )
        """)

        conn.commit()
        conn.close()
        logger.info(f"Memory database initialized at {self.db_path}")

    def _get_conn(self):
        """Get database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # ============== STORE OPERATIONS ==============

    def store(self, memory: Memory) -> int:
        """Store a new memory. Returns the memory ID."""
        now = datetime.now().isoformat()
        memory.created_at = memory.created_at or now
        memory.accessed_at = now

        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO memories
            (memory_type, category, content, context, importance, created_at, accessed_at, access_count, compressed, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            memory.memory_type,
            memory.category,
            memory.content,
            memory.context,
            memory.importance,
            memory.created_at,
            memory.accessed_at,
            memory.access_count,
            1 if memory.compressed else 0,
            memory.tags
        ))

        memory_id = cursor.lastrowid
        conn.commit()
        conn.close()

        logger.debug(f"Stored memory #{memory_id}: {memory.category}")
        return memory_id

    def store_episodic(self, category: str, content: str, context: str = "",
                       importance: float = 0.5, tags: list = None) -> int:
        """Store an episodic memory (event)."""
        return self.store(Memory(
            memory_type="episodic",
            category=category,
            content=content,
            context=context,
            importance=importance,
            tags=json.dumps(tags or [])
        ))

    def store_semantic(self, category: str, content: str, context: str = "",
                       importance: float = 0.7, tags: list = None) -> int:
        """Store a semantic memory (knowledge)."""
        return self.store(Memory(
            memory_type="semantic",
            category=category,
            content=content,
            context=context,
            importance=importance,
            tags=json.dumps(tags or [])
        ))

    def store_short_term(self, category: str, content: str, context: str = "") -> int:
        """Store a short-term memory (session context)."""
        return self.store(Memory(
            memory_type="short_term",
            category=category,
            content=content,
            context=context,
            importance=0.3
        ))

    # ============== RETRIEVAL OPERATIONS ==============

    def search(self, query: str, limit: int = 10, memory_type: str = None,
               category: str = None, min_importance: float = 0) -> list[Memory]:
        """Search memories using full-text search."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Escape special FTS5 characters and wrap in quotes for literal matching
        # FTS5 special chars: " * ? ( ) : ^ -
        safe_query = query.replace('"', '""')  # Escape double quotes
        safe_query = f'"{safe_query}"'  # Wrap in quotes for literal match

        # Build query
        sql = """
            SELECT m.* FROM memories m
            JOIN memories_fts fts ON m.id = fts.rowid
            WHERE memories_fts MATCH ?
        """
        params = [safe_query]

        if memory_type:
            sql += " AND m.memory_type = ?"
            params.append(memory_type)

        if category:
            sql += " AND m.category = ?"
            params.append(category)

        if min_importance > 0:
            sql += " AND m.importance >= ?"
            params.append(min_importance)

        sql += " ORDER BY rank, m.importance DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        # Update access counts
        self._update_access(row["id"] for row in rows)

        return [self._row_to_memory(row) for row in rows]

    def get_recent(self, limit: int = 20, memory_type: str = None,
                   category: str = None, days: int = None) -> list[Memory]:
        """Get recent memories."""
        conn = self._get_conn()
        cursor = conn.cursor()

        sql = "SELECT * FROM memories WHERE 1=1"
        params = []

        if memory_type:
            sql += " AND memory_type = ?"
            params.append(memory_type)

        if category:
            sql += " AND category = ?"
            params.append(category)

        if days:
            cutoff = (datetime.now() - timedelta(days=days)).isoformat()
            sql += " AND created_at > ?"
            params.append(cutoff)

        sql += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql, params)
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_memory(row) for row in rows]

    def get_by_id(self, memory_id: int) -> Optional[Memory]:
        """Get a specific memory by ID."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            self._update_access([memory_id])
            return self._row_to_memory(row)
        return None

    def get_important(self, limit: int = 10, min_importance: float = 0.7) -> list[Memory]:
        """Get most important memories."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT * FROM memories
            WHERE importance >= ? AND compressed = 0
            ORDER BY importance DESC, access_count DESC
            LIMIT ?
        """, (min_importance, limit))
        rows = cursor.fetchall()
        conn.close()

        return [self._row_to_memory(row) for row in rows]

    def get_context_for_topic(self, topic: str, limit: int = 5) -> list[Memory]:
        """Get memories relevant to a topic for context injection."""
        # First try exact search
        memories = self.search(topic, limit=limit, min_importance=0.3)

        # If not enough, get recent high-importance memories
        if len(memories) < limit:
            important = self.get_important(limit=limit - len(memories))
            memories.extend(m for m in important if m.id not in {mem.id for mem in memories})

        return memories[:limit]

    # ============== MAINTENANCE OPERATIONS ==============

    def clear_short_term(self):
        """Clear all short-term memories (end of session)."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM memories WHERE memory_type = 'short_term'")
        count = cursor.rowcount
        conn.commit()
        conn.close()
        logger.info(f"Cleared {count} short-term memories")
        return count

    def delete_old(self, days: int = 30, keep_important: bool = True):
        """Delete old, low-importance memories."""
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        conn = self._get_conn()
        cursor = conn.cursor()

        sql = "DELETE FROM memories WHERE created_at < ? AND memory_type = 'episodic'"
        if keep_important:
            sql += " AND importance < 0.7"

        cursor.execute(sql, (cutoff,))
        count = cursor.rowcount
        conn.commit()
        conn.close()

        logger.info(f"Deleted {count} old memories")
        return count

    def get_stats(self) -> dict:
        """Get memory statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()

        stats = {}

        # Total counts by type
        cursor.execute("""
            SELECT memory_type, COUNT(*) as count
            FROM memories GROUP BY memory_type
        """)
        stats["by_type"] = {row["memory_type"]: row["count"] for row in cursor.fetchall()}

        # Total counts by category
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM memories GROUP BY category ORDER BY count DESC LIMIT 10
        """)
        stats["by_category"] = {row["category"]: row["count"] for row in cursor.fetchall()}

        # Total
        cursor.execute("SELECT COUNT(*) as total FROM memories")
        stats["total"] = cursor.fetchone()["total"]

        # Compressed
        cursor.execute("SELECT COUNT(*) as compressed FROM memories WHERE compressed = 1")
        stats["compressed"] = cursor.fetchone()["compressed"]

        conn.close()
        return stats

    # ============== HELPERS ==============

    def _row_to_memory(self, row) -> Memory:
        """Convert database row to Memory object."""
        return Memory(
            id=row["id"],
            memory_type=row["memory_type"],
            category=row["category"],
            content=row["content"],
            context=row["context"] or "",
            importance=row["importance"],
            created_at=row["created_at"],
            accessed_at=row["accessed_at"] or "",
            access_count=row["access_count"],
            compressed=bool(row["compressed"]),
            tags=row["tags"] or "[]"
        )

    def _update_access(self, memory_ids):
        """Update access timestamp and count for memories."""
        if not memory_ids:
            return

        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        for mid in memory_ids:
            cursor.execute("""
                UPDATE memories
                SET accessed_at = ?, access_count = access_count + 1
                WHERE id = ?
            """, (now, mid))

        conn.commit()
        conn.close()
