"""
Knowledge Store - SQLite storage for research items.

Stores scraped items, evaluation results, and tracks what's been seen.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Database path
DB_PATH = Path(__file__).parent.parent.parent / "data" / "research.db"


@dataclass
class ResearchItem:
    """A single research item from any source."""
    source: str  # github, youtube, twitter, reddit, rss
    source_id: str  # unique ID from source
    url: str
    title: str
    content: str  # full content or description
    published_at: Optional[datetime] = None

    # Filled in after evaluation
    summary: str = ""
    matched_goals: List[str] = field(default_factory=list)
    relevance_score: float = 0.0
    priority: str = "none"  # critical, high, medium, low, none
    suggested_action: str = "ignore"  # alert, task, content, knowledge, ignore
    reasoning: str = ""

    # Processing status
    id: Optional[int] = None
    scraped_at: Optional[datetime] = None
    processed: bool = False
    action_taken: Optional[str] = None
    action_id: Optional[str] = None


class KnowledgeStore:
    """SQLite storage for research items and deduplication."""

    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Initialize database tables."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Research items table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS research_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                source_id TEXT,
                url TEXT,
                title TEXT,
                content TEXT,
                summary TEXT,
                published_at DATETIME,
                scraped_at DATETIME DEFAULT CURRENT_TIMESTAMP,

                -- Evaluation results
                matched_goals TEXT,
                relevance_score REAL DEFAULT 0,
                priority TEXT DEFAULT 'none',
                suggested_action TEXT DEFAULT 'ignore',
                reasoning TEXT,

                -- Processing status
                processed BOOLEAN DEFAULT FALSE,
                action_taken TEXT,
                action_id TEXT,

                UNIQUE(source, source_id)
            )
        """)

        # Seen items for deduplication
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS seen_items (
                source TEXT,
                source_id TEXT,
                first_seen DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (source, source_id)
            )
        """)

        # Daily digest tracking
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS digests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date DATE UNIQUE,
                items_scraped INTEGER DEFAULT 0,
                items_relevant INTEGER DEFAULT 0,
                alerts_sent INTEGER DEFAULT 0,
                tasks_created INTEGER DEFAULT 0,
                content_drafted INTEGER DEFAULT 0,
                summary TEXT,
                sent_at DATETIME
            )
        """)

        # Index for faster queries
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_research_items_scraped
            ON research_items(scraped_at)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_research_items_priority
            ON research_items(priority, processed)
        """)

        conn.commit()
        conn.close()
        logger.info(f"Knowledge store initialized at {self.db_path}")

    def has_seen(self, source: str, source_id: str) -> bool:
        """Check if we've already seen this item."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM seen_items WHERE source = ? AND source_id = ?",
            (source, source_id)
        )
        result = cursor.fetchone() is not None
        conn.close()
        return result

    def mark_seen(self, source: str, source_id: str):
        """Mark an item as seen."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO seen_items (source, source_id) VALUES (?, ?)",
            (source, source_id)
        )
        conn.commit()
        conn.close()

    def filter_new(self, items: List[ResearchItem]) -> List[ResearchItem]:
        """Filter out items we've already seen."""
        new_items = []
        for item in items:
            if not self.has_seen(item.source, item.source_id):
                new_items.append(item)
                self.mark_seen(item.source, item.source_id)
        logger.info(f"Filtered {len(items)} items to {len(new_items)} new items")
        return new_items

    def save(self, item: ResearchItem) -> int:
        """Save a research item to the database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT OR REPLACE INTO research_items (
                source, source_id, url, title, content, summary,
                published_at, matched_goals, relevance_score,
                priority, suggested_action, reasoning,
                processed, action_taken, action_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            item.source,
            item.source_id,
            item.url,
            item.title,
            item.content,
            item.summary,
            item.published_at.isoformat() if item.published_at else None,
            json.dumps(item.matched_goals),
            item.relevance_score,
            item.priority,
            item.suggested_action,
            item.reasoning,
            item.processed,
            item.action_taken,
            item.action_id
        ))

        item_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return item_id

    def save_batch(self, items: List[ResearchItem]):
        """Save multiple items efficiently."""
        for item in items:
            self.save(item)
        logger.info(f"Saved {len(items)} research items")

    def get_unprocessed(self, limit: int = 100) -> List[ResearchItem]:
        """Get items that haven't been processed yet."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM research_items
            WHERE processed = FALSE
            ORDER BY scraped_at DESC
            LIMIT ?
        """, (limit,))

        items = [self._row_to_item(row) for row in cursor.fetchall()]
        conn.close()
        return items

    def get_by_priority(self, priority: str, limit: int = 50) -> List[ResearchItem]:
        """Get items by priority level."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM research_items
            WHERE priority = ?
            ORDER BY scraped_at DESC
            LIMIT ?
        """, (priority, limit))

        items = [self._row_to_item(row) for row in cursor.fetchall()]
        conn.close()
        return items

    def get_recent(self, hours: int = 24, min_relevance: float = 0) -> List[ResearchItem]:
        """Get recent items above a relevance threshold."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        since = datetime.now() - timedelta(hours=hours)
        cursor.execute("""
            SELECT * FROM research_items
            WHERE scraped_at > ? AND relevance_score >= ?
            ORDER BY relevance_score DESC, scraped_at DESC
        """, (since.isoformat(), min_relevance))

        items = [self._row_to_item(row) for row in cursor.fetchall()]
        conn.close()
        return items

    def mark_processed(self, item_id: int, action_taken: str, action_id: str = None):
        """Mark an item as processed with the action taken."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE research_items
            SET processed = TRUE, action_taken = ?, action_id = ?
            WHERE id = ?
        """, (action_taken, action_id, item_id))
        conn.commit()
        conn.close()

    def _row_to_item(self, row: sqlite3.Row) -> ResearchItem:
        """Convert a database row to a ResearchItem."""
        return ResearchItem(
            id=row["id"],
            source=row["source"],
            source_id=row["source_id"],
            url=row["url"],
            title=row["title"],
            content=row["content"],
            summary=row["summary"] or "",
            published_at=datetime.fromisoformat(row["published_at"]) if row["published_at"] else None,
            scraped_at=datetime.fromisoformat(row["scraped_at"]) if row["scraped_at"] else None,
            matched_goals=json.loads(row["matched_goals"]) if row["matched_goals"] else [],
            relevance_score=row["relevance_score"] or 0,
            priority=row["priority"] or "none",
            suggested_action=row["suggested_action"] or "ignore",
            reasoning=row["reasoning"] or "",
            processed=bool(row["processed"]),
            action_taken=row["action_taken"],
            action_id=row["action_id"]
        )

    # --- Digest Tracking ---

    def record_digest(self, stats: dict):
        """Record a daily digest."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        today = datetime.now().date().isoformat()
        cursor.execute("""
            INSERT OR REPLACE INTO digests (
                date, items_scraped, items_relevant, alerts_sent,
                tasks_created, content_drafted, summary, sent_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            today,
            stats.get("items_scraped", 0),
            stats.get("items_relevant", 0),
            stats.get("alerts_sent", 0),
            stats.get("tasks_created", 0),
            stats.get("content_drafted", 0),
            stats.get("summary", ""),
            datetime.now().isoformat()
        ))

        conn.commit()
        conn.close()

    def get_digest_stats(self, days: int = 7) -> List[dict]:
        """Get digest stats for the last N days."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM digests
            ORDER BY date DESC
            LIMIT ?
        """, (days,))

        stats = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return stats
