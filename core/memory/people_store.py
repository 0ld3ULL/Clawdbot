"""
People Store - David's relationship memory.

People NEVER fade - relationships are core to David's work.
"""

import json
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DB_PATH = Path("data/people.db")


@dataclass
class Person:
    """A person David knows."""
    id: int
    name: str
    handle: Optional[str]  # @twitter, Discord, etc.
    role: str  # investor, community, journalist, operator
    description: str
    first_met: str
    last_interaction: str
    interaction_count: int
    sentiment: str  # friendly, neutral, skeptic, trusted
    importance: float  # 0-1
    notes: str
    tags: list[str]


class PeopleStore:
    """David's memory of people. Never fades."""

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
            CREATE TABLE IF NOT EXISTS people (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                handle TEXT,
                role TEXT DEFAULT 'unknown',
                description TEXT DEFAULT '',
                first_met TEXT,
                last_interaction TEXT,
                interaction_count INTEGER DEFAULT 0,
                sentiment TEXT DEFAULT 'unknown',
                importance REAL DEFAULT 0.5,
                notes TEXT DEFAULT '',
                tags TEXT DEFAULT '[]',
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS interactions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                person_id INTEGER NOT NULL,
                channel TEXT,
                summary TEXT,
                timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (person_id) REFERENCES people(id)
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_people_name ON people(name)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_people_handle ON people(handle)")

        conn.commit()
        conn.close()
        logger.info(f"People database initialized at {self.db_path}")

    def add_person(self, name: str, handle: str = None, role: str = "unknown",
                   description: str = "", sentiment: str = "unknown",
                   importance: float = 0.5, notes: str = "", tags: list = None) -> int:
        """Add someone David met."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO people (name, handle, role, description, first_met,
                              last_interaction, sentiment, importance, notes, tags)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, handle, role, description, now, now, sentiment, importance,
              notes, json.dumps(tags or [])))

        person_id = cursor.lastrowid
        conn.commit()
        conn.close()
        logger.info(f"Added person: {name}")
        return person_id

    def find(self, query: str) -> list[Person]:
        """Search for someone by name or handle."""
        conn = self._get_conn()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM people
            WHERE name LIKE ? OR handle LIKE ? OR description LIKE ?
            ORDER BY importance DESC LIMIT 10
        """, (f"%{query}%", f"%{query}%", f"%{query}%"))

        people = [self._to_person(row) for row in cursor.fetchall()]
        conn.close()
        return people

    def get(self, person_id: int = None, handle: str = None) -> Optional[Person]:
        """Get a specific person."""
        conn = self._get_conn()
        cursor = conn.cursor()

        if person_id:
            cursor.execute("SELECT * FROM people WHERE id = ?", (person_id,))
        elif handle:
            cursor.execute("SELECT * FROM people WHERE handle = ?", (handle,))
        else:
            return None

        row = cursor.fetchone()
        conn.close()
        return self._to_person(row) if row else None

    def record_interaction(self, person_id: int, summary: str, channel: str = "telegram"):
        """Record that David talked to someone."""
        conn = self._get_conn()
        cursor = conn.cursor()
        now = datetime.now().isoformat()

        cursor.execute("""
            INSERT INTO interactions (person_id, channel, summary, timestamp)
            VALUES (?, ?, ?, ?)
        """, (person_id, channel, summary, now))

        cursor.execute("""
            UPDATE people SET last_interaction = ?, interaction_count = interaction_count + 1
            WHERE id = ?
        """, (now, person_id))

        conn.commit()
        conn.close()

    def get_context(self, query: str) -> str:
        """Get context about a person for David's response."""
        people = self.find(query)
        if not people:
            return ""

        person = people[0]
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT summary, timestamp FROM interactions
            WHERE person_id = ? ORDER BY timestamp DESC LIMIT 3
        """, (person.id,))
        interactions = cursor.fetchall()
        conn.close()

        context = f"[{person.name}] {person.role}. {person.description}"
        if person.notes:
            context += f" Notes: {person.notes}"
        if interactions:
            context += " Recent: " + "; ".join([i[0][:50] for i in interactions])

        return context

    def update(self, person_id: int, **kwargs):
        """Update a person's info."""
        if not kwargs:
            return
        conn = self._get_conn()
        cursor = conn.cursor()

        updates = []
        values = []
        for k, v in kwargs.items():
            if k == "tags":
                v = json.dumps(v)
            updates.append(f"{k} = ?")
            values.append(v)
        values.append(person_id)

        cursor.execute(f"UPDATE people SET {', '.join(updates)} WHERE id = ?", values)
        conn.commit()
        conn.close()

    def get_stats(self) -> dict:
        conn = self._get_conn()
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM people")
        total = cursor.fetchone()[0]
        cursor.execute("SELECT SUM(interaction_count) FROM people")
        interactions = cursor.fetchone()[0] or 0
        conn.close()
        return {"total_people": total, "total_interactions": interactions}

    def _to_person(self, row) -> Person:
        return Person(
            id=row["id"], name=row["name"], handle=row["handle"],
            role=row["role"], description=row["description"],
            first_met=row["first_met"], last_interaction=row["last_interaction"],
            interaction_count=row["interaction_count"], sentiment=row["sentiment"],
            importance=row["importance"], notes=row["notes"],
            tags=json.loads(row["tags"]) if row["tags"] else []
        )
