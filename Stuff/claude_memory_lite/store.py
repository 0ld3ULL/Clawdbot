"""
Memory Store - SQLite backend for Claude's persistent memory.

Simple, no dependencies beyond Python stdlib.
Drop into any project, run with: python -m claude_memory brief
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Default DB location — sits in project's data/ folder
DB_PATH = Path("data/claude_memory.db")


class MemoryStore:
    """
    Persistent memory for Claude across sessions.

    Categories:
        decision    — "We decided to use Photon not Netcode"
        architecture — "Inventory system uses ScriptableObjects"
        bug         — "Physics breaks below 30fps"
        idea        — "Maybe add crafting system"
        context     — "Jet wants UI to feel like Zelda BOTW"
        person      — Who Claude is working with, their preferences
        task        — What's being worked on, what's done
        session     — Session summaries and conversation highlights

    Significance (1-10):
        8-10  — Critical. Always shown in brief. Never forgotten.
        5-7   — Important. Shown in brief for 30 days.
        1-4   — Minor. Shown in brief for 7 days.
    """

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self):
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                title TEXT NOT NULL,
                content TEXT NOT NULL,
                significance INTEGER DEFAULT 5,
                session_date TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # FTS for fast searching
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                title, content, category,
                content='memories',
                content_rowid='id'
            )
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, title, content, category)
                VALUES (new.id, new.title, new.content, new.category);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                INSERT INTO memories_fts(memories_fts, rowid, title, content, category)
                VALUES('delete', old.id, old.title, old.content, old.category);
            END
        """)

        conn.commit()
        conn.close()

    def add(self, category: str, title: str, content: str,
            significance: int = 5) -> int:
        """Add a memory. Returns the memory ID."""
        significance = max(1, min(10, significance))
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now()

        cursor.execute("""
            INSERT INTO memories (category, title, content, significance,
                                  session_date, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (category, title, content, significance,
              now.strftime("%Y-%m-%d"), now.isoformat()))

        memory_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return memory_id

    def search(self, query: str, limit: int = 10) -> list[dict]:
        """Search memories by text."""
        conn = self._get_conn()
        cursor = conn.cursor()
        safe_query = query.replace('"', '""')

        try:
            cursor.execute("""
                SELECT m.* FROM memories m
                JOIN memories_fts fts ON m.id = fts.rowid
                WHERE memories_fts MATCH ?
                ORDER BY m.significance DESC, m.created_at DESC
                LIMIT ?
            """, (f'"{safe_query}"', limit))
        except sqlite3.OperationalError:
            cursor.execute("""
                SELECT * FROM memories
                WHERE title LIKE ? OR content LIKE ?
                ORDER BY significance DESC, created_at DESC
                LIMIT ?
            """, (f"%{query}%", f"%{query}%", limit))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_for_brief(self) -> dict:
        """
        Get memories organized for the session brief.

        Returns:
            {
                "critical": [...],   # sig 8-10, all time
                "important": [...],  # sig 5-7, last 30 days
                "recent": [...],     # sig 1-4, last 7 days
            }
        """
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now()

        # Critical — always shown
        cursor.execute("""
            SELECT * FROM memories WHERE significance >= 8
            ORDER BY significance DESC, created_at DESC
        """)
        critical = [dict(row) for row in cursor.fetchall()]

        # Important — last 30 days
        cutoff_30 = (now - timedelta(days=30)).isoformat()
        cursor.execute("""
            SELECT * FROM memories
            WHERE significance BETWEEN 5 AND 7 AND created_at > ?
            ORDER BY significance DESC, created_at DESC
        """, (cutoff_30,))
        important = [dict(row) for row in cursor.fetchall()]

        # Recent — last 7 days, low significance
        cutoff_7 = (now - timedelta(days=7)).isoformat()
        cursor.execute("""
            SELECT * FROM memories
            WHERE significance < 5 AND created_at > ?
            ORDER BY created_at DESC
        """, (cutoff_7,))
        recent = [dict(row) for row in cursor.fetchall()]

        conn.close()
        return {"critical": critical, "important": important, "recent": recent}

    def get_stats(self) -> dict:
        """Get memory statistics."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("SELECT COUNT(*) FROM memories")
        total = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM memories WHERE significance >= 8")
        critical = cursor.fetchone()[0]

        cursor.execute("""
            SELECT category, COUNT(*) as count FROM memories
            GROUP BY category ORDER BY count DESC
        """)
        by_category = {row["category"]: row["count"] for row in cursor.fetchall()}

        cursor.execute("SELECT MIN(created_at) FROM memories")
        first = cursor.fetchone()[0]

        conn.close()
        return {
            "total": total,
            "critical": critical,
            "by_category": by_category,
            "first_memory": first,
        }

    def delete(self, memory_id: int):
        """Delete a memory by ID."""
        conn = self._get_conn()
        conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        conn.commit()
        conn.close()
