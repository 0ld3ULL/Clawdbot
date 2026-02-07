"""
Event Store - David's memory of world events.

Events are ranked 1-10 for significance:
- 10: "Where were you when" moments (9/11, Bitcoin whitepaper) - NEVER fade
- 8-9: Major shifts - very slow fade
- 5-7: Notable events - slow fade, "rings a bell"
- 2-4: Minor events - fast fade, "let me look that up"
- 1: Noise - gone in days

Lower scored events can be looked up - David doesn't need to remember everything.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = Path("data/events.db")


@dataclass
class Event:
    """A world event David knows about."""
    id: int
    title: str
    summary: str
    significance: int  # 1-10 scale
    category: str  # surveillance, crypto, regulation, tech, world
    source: str
    url: str
    event_date: str
    recall_strength: float  # 0-1, decays over time, boosted on recall
    recalled_count: int  # times David has remembered this
    tags: list[str]
    created_at: str


class EventStore:
    """David's memory of events. Fades based on significance."""

    # Decay rates per week (subtracted from recall_strength)
    DECAY_RATES = {
        10: 0.00,   # Never fades - "where were you when"
        9: 0.01,    # Almost never
        8: 0.02,    # Very slow
        7: 0.05,    # Slow
        6: 0.08,    # Medium-slow
        5: 0.10,    # Medium
        4: 0.15,    # Medium-fast
        3: 0.20,    # Fast
        2: 0.30,    # Very fast
        1: 0.50,    # Gone in 2 weeks
    }

    # Boost when David recalls an event
    RECALL_BOOST = 0.15

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
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                summary TEXT NOT NULL,
                significance INTEGER DEFAULT 5,
                category TEXT DEFAULT 'world',
                source TEXT DEFAULT '',
                url TEXT DEFAULT '',
                event_date TEXT,
                recall_strength REAL DEFAULT 1.0,
                recalled_count INTEGER DEFAULT 0,
                last_recalled TEXT,
                tags TEXT DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # FTS for searching
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
                title, summary, tags,
                content='events',
                content_rowid='id'
            )
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS events_ai AFTER INSERT ON events BEGIN
                INSERT INTO events_fts(rowid, title, summary, tags)
                VALUES (new.id, new.title, new.summary, new.tags);
            END
        """)

        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS events_ad AFTER DELETE ON events BEGIN
                INSERT INTO events_fts(events_fts, rowid, title, summary, tags)
                VALUES('delete', old.id, old.title, old.summary, old.tags);
            END
        """)

        conn.commit()
        conn.close()
        logger.info(f"Events database initialized at {self.db_path}")

    def add(self, title: str, summary: str, significance: int = 5,
            category: str = "world", source: str = "", url: str = "",
            event_date: str = None, tags: list = None) -> int:
        """Record an event David witnessed/learned about."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        # Clamp significance to 1-10
        significance = max(1, min(10, significance))

        cursor.execute("""
            INSERT INTO events (title, summary, significance, category, source, url,
                              event_date, recall_strength, tags, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (title, summary, significance, category, source, url,
              event_date or now[:10], 1.0, json.dumps(tags or []), now))

        event_id = cursor.lastrowid
        conn.commit()
        conn.close()

        level = "HISTORIC" if significance >= 8 else "notable" if significance >= 5 else "minor"
        logger.info(f"Added {level} event [{significance}/10]: {title}")
        return event_id

    def recall(self, query: str, min_strength: float = 0.3) -> tuple[list[Event], str]:
        """
        Try to recall events matching query.

        Returns:
            (events, memory_state) where memory_state is one of:
            - "clear": Strong recall, confident
            - "fuzzy": "Rings a bell", partial recall
            - "blank": Nothing comes to mind
        """
        conn = self._get_conn()
        cursor = conn.cursor()

        # Escape special FTS5 characters
        safe_query = query.replace('"', '""')
        safe_query = f'"{safe_query}"'

        try:
            cursor.execute("""
                SELECT e.* FROM events e
                JOIN events_fts fts ON e.id = fts.rowid
                WHERE events_fts MATCH ? AND e.recall_strength >= ?
                ORDER BY e.significance DESC, e.recall_strength DESC
                LIMIT 5
            """, (safe_query, min_strength))

            events = [self._to_event(row) for row in cursor.fetchall()]
        except sqlite3.OperationalError:
            # FTS query failed, fall back to LIKE
            cursor.execute("""
                SELECT * FROM events
                WHERE (title LIKE ? OR summary LIKE ?) AND recall_strength >= ?
                ORDER BY significance DESC, recall_strength DESC
                LIMIT 5
            """, (f"%{query}%", f"%{query}%", min_strength))
            events = [self._to_event(row) for row in cursor.fetchall()]

        conn.close()

        # Determine memory state
        if not events:
            return [], "blank"

        best = events[0]
        if best.recall_strength >= 0.7 and best.significance >= 6:
            state = "clear"
        elif best.recall_strength >= 0.4:
            state = "fuzzy"
        else:
            state = "blank"

        # Boost recall strength for remembered events
        for event in events:
            self._boost_recall(event.id)

        return events, state

    def _boost_recall(self, event_id: int):
        """Boost recall strength when David remembers something."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute("""
            UPDATE events
            SET recall_strength = MIN(1.0, recall_strength + ?),
                recalled_count = recalled_count + 1,
                last_recalled = ?
            WHERE id = ?
        """, (self.RECALL_BOOST, now, event_id))

        conn.commit()
        conn.close()

    def decay_memories(self):
        """Apply decay to all events based on their significance. Run daily."""
        conn = self._get_conn()
        cursor = conn.cursor()

        for significance, decay_rate in self.DECAY_RATES.items():
            if decay_rate == 0:
                continue  # No decay for this level

            cursor.execute("""
                UPDATE events
                SET recall_strength = MAX(0, recall_strength - ?)
                WHERE significance = ? AND recall_strength > 0
            """, (decay_rate, significance))

        conn.commit()

        # Count what's faded to near-zero
        cursor.execute("SELECT COUNT(*) FROM events WHERE recall_strength < 0.1")
        faded = cursor.fetchone()[0]

        conn.close()
        logger.info(f"Memory decay applied. {faded} events have nearly faded.")
        return faded

    def prune_forgotten(self, min_strength: float = 0.05):
        """Remove events that have completely faded (except high significance)."""
        conn = self._get_conn()
        cursor = conn.cursor()

        # Only prune low-significance events
        cursor.execute("""
            DELETE FROM events
            WHERE recall_strength < ? AND significance < 5
        """, (min_strength,))

        pruned = cursor.rowcount
        conn.commit()
        conn.close()

        if pruned > 0:
            logger.info(f"Pruned {pruned} forgotten events")
        return pruned

    def get_historic(self, limit: int = 20) -> list[Event]:
        """Get 'where were you when' moments (significance 8+)."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM events
            WHERE significance >= 8
            ORDER BY event_date DESC
            LIMIT ?
        """, (limit,))

        events = [self._to_event(row) for row in cursor.fetchall()]
        conn.close()
        return events

    def get_recent(self, days: int = 7, limit: int = 20) -> list[Event]:
        """Get recent events David might remember."""
        conn = self._get_conn()
        cursor = conn.cursor()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()

        cursor.execute("""
            SELECT * FROM events
            WHERE created_at > ? AND recall_strength > 0.3
            ORDER BY significance DESC, created_at DESC
            LIMIT ?
        """, (cutoff, limit))

        events = [self._to_event(row) for row in cursor.fetchall()]
        conn.close()
        return events

    def get_context(self, query: str) -> tuple[str, str]:
        """
        Get context about an event for David's response.

        Returns:
            (context_text, memory_phrase) where memory_phrase is what David says:
            - "clear": just speaks confidently
            - "fuzzy": "That rings a bell... " or "It's on the tip of my tongue..."
            - "blank": "Not a 'where were you when' moment for me."
        """
        events, state = self.recall(query)

        if state == "blank":
            return "", "blank"

        if state == "fuzzy":
            context = f"[Vague memory] {events[0].title}: {events[0].summary[:100]}"
            return context, "fuzzy"

        # Clear recall
        context = f"[Event] {events[0].title}: {events[0].summary}"
        if len(events) > 1:
            context += f"\n[Related] {events[1].title}"
        return context, "clear"

    def get_stats(self) -> dict:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM events")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM events WHERE significance >= 8")
        historic = cursor.fetchone()[0]
        cursor.execute("SELECT COUNT(*) FROM events WHERE recall_strength < 0.3")
        fading = cursor.fetchone()[0]
        cursor.execute("SELECT AVG(recall_strength) FROM events")
        avg_strength = cursor.fetchone()[0] or 0
        conn.close()
        return {
            "total_events": total,
            "historic_events": historic,
            "fading_events": fading,
            "avg_recall_strength": round(avg_strength, 2)
        }

    def _to_event(self, row) -> Event:
        return Event(
            id=row["id"], title=row["title"], summary=row["summary"],
            significance=row["significance"], category=row["category"],
            source=row["source"], url=row["url"], event_date=row["event_date"],
            recall_strength=row["recall_strength"], recalled_count=row["recalled_count"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            created_at=row["created_at"]
        )
