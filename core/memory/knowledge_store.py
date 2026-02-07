"""
Knowledge Store - David's FLIPT company knowledge.

Things David MUST know as CEO/Founder. Never fades.
- Product features
- Pricing, fees, tokenomics
- Roadmap decisions
- Company values
- Technical architecture
- Lessons learned
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = Path("data/knowledge.db")


@dataclass
class Knowledge:
    """A piece of FLIPT knowledge."""
    id: int
    category: str  # product, pricing, roadmap, values, technical, lesson
    topic: str
    content: str
    source: str  # where David learned this
    confidence: float  # 0-1, how sure is he
    tags: list[str]
    created_at: str
    updated_at: str


class KnowledgeStore:
    """David's company knowledge. Never fades - he IS the company."""

    CATEGORIES = [
        "product",    # What FLIPT does
        "pricing",    # Fees, tokenomics
        "roadmap",    # Future plans
        "values",     # What David/FLIPT stands for
        "technical",  # How things work
        "lesson",     # Things David learned on the job
        "decision",   # Decisions made and why
    ]

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL,
                topic TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT '',
                confidence REAL DEFAULT 1.0,
                tags TEXT DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Full-text search
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_fts USING fts5(
                topic, content, tags,
                content='knowledge',
                content_rowid='id'
            )
        """)

        # Triggers to keep FTS in sync
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS knowledge_ai AFTER INSERT ON knowledge BEGIN
                INSERT INTO knowledge_fts(rowid, topic, content, tags)
                VALUES (new.id, new.topic, new.content, new.tags);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS knowledge_ad AFTER DELETE ON knowledge BEGIN
                INSERT INTO knowledge_fts(knowledge_fts, rowid, topic, content, tags)
                VALUES('delete', old.id, old.topic, old.content, old.tags);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS knowledge_au AFTER UPDATE ON knowledge BEGIN
                INSERT INTO knowledge_fts(knowledge_fts, rowid, topic, content, tags)
                VALUES('delete', old.id, old.topic, old.content, old.tags);
                INSERT INTO knowledge_fts(rowid, topic, content, tags)
                VALUES (new.id, new.topic, new.content, new.tags);
            END
        """)

        conn.commit()
        conn.close()
        logger.info(f"Knowledge database initialized at {self.db_path}")

    def add(self, category: str, topic: str, content: str,
            source: str = "", confidence: float = 1.0, tags: list = None) -> int:
        """Add knowledge David should never forget."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO knowledge (category, topic, content, source, confidence, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (category, topic, content, source, confidence, json.dumps(tags or []), now, now))

        knowledge_id = cursor.lastrowid
        conn.commit()
        conn.close()
        logger.info(f"Added knowledge: [{category}] {topic}")
        return knowledge_id

    def search(self, query: str, category: str = None, limit: int = 10) -> list[Knowledge]:
        """Search David's knowledge."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Escape special FTS5 characters
        safe_query = query.replace('"', '""')
        safe_query = f'"{safe_query}"'

        if category:
            cursor.execute("""
                SELECT k.* FROM knowledge k
                JOIN knowledge_fts fts ON k.id = fts.rowid
                WHERE knowledge_fts MATCH ? AND k.category = ?
                ORDER BY rank LIMIT ?
            """, (safe_query, category, limit))
        else:
            cursor.execute("""
                SELECT k.* FROM knowledge k
                JOIN knowledge_fts fts ON k.id = fts.rowid
                WHERE knowledge_fts MATCH ?
                ORDER BY rank LIMIT ?
            """, (safe_query, limit))

        results = [self._to_knowledge(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_by_category(self, category: str, limit: int = 20) -> list[Knowledge]:
        """Get all knowledge in a category."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM knowledge WHERE category = ?
            ORDER BY updated_at DESC LIMIT ?
        """, (category, limit))

        results = [self._to_knowledge(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_context(self, query: str) -> str:
        """Get relevant knowledge for David's response."""
        results = self.search(query, limit=5)
        if not results:
            return ""

        context = "**FLIPT Knowledge:**\n"
        for k in results:
            context += f"- [{k.category}] {k.topic}: {k.content[:150]}\n"
        return context

    def update(self, knowledge_id: int, content: str = None, confidence: float = None):
        """Update existing knowledge."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        updates = ["updated_at = ?"]
        values = [now]

        if content:
            updates.append("content = ?")
            values.append(content)
        if confidence is not None:
            updates.append("confidence = ?")
            values.append(confidence)

        values.append(knowledge_id)
        cursor.execute(f"UPDATE knowledge SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
        conn.close()

    def learn(self, topic: str, content: str, source: str = "experience"):
        """David learns something new about being a CEO/Founder."""
        return self.add(
            category="lesson",
            topic=topic,
            content=content,
            source=source,
            confidence=0.8,
            tags=["learned", "experience"]
        )

    def get_stats(self) -> dict:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM knowledge")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT category, COUNT(*) FROM knowledge GROUP BY category")
        by_category = dict(cursor.fetchall())
        conn.close()
        return {"total_knowledge": total, "by_category": by_category}

    def _to_knowledge(self, row) -> Knowledge:
        return Knowledge(
            id=row["id"], category=row["category"], topic=row["topic"],
            content=row["content"], source=row["source"],
            confidence=row["confidence"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            created_at=row["created_at"], updated_at=row["updated_at"]
        )
