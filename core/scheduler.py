"""
Content Scheduler - Schedule and manage timed content posts.

Uses APScheduler for job management with SQLite persistence.
"""

import json
import logging
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.triggers.date import DateTrigger

logger = logging.getLogger(__name__)

# Default data directory
DATA_DIR = Path(os.environ.get("DAVID_DATA_DIR", "data"))

# Global reference to the active ContentScheduler instance.
# APScheduler pickles job callbacks to SQLite. After a restart, unpickling
# creates a *new* ContentScheduler with empty _executors. This global lets
# us route unpickled jobs back to the real running instance that has executors.
_active_scheduler: Optional['ContentScheduler'] = None


def set_active_scheduler(instance: 'ContentScheduler'):
    """Register the running ContentScheduler so scheduled jobs can find it."""
    global _active_scheduler
    _active_scheduler = instance


async def _dispatch_scheduled_job(job_id: str):
    """Module-level callback for APScheduler — survives pickle/unpickle.

    APScheduler can pickle this plain function without dragging along a
    ContentScheduler instance.  At fire-time it calls back into the real
    running scheduler via the global reference.
    """
    if _active_scheduler is None:
        logger.error(f"Scheduled job {job_id}: no active ContentScheduler — cannot execute")
        return
    await _active_scheduler._execute_scheduled(job_id)


class ContentScheduler:
    """Manages scheduled content posts."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DATA_DIR / "scheduler.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # APScheduler with SQLite persistence
        jobstores = {
            'default': SQLAlchemyJobStore(url=f'sqlite:///{self.db_path}')
        }
        self.scheduler = AsyncIOScheduler(jobstores=jobstores)

        # Callbacks for different content types
        self._executors: dict[str, Callable] = {}

        # Initialize metadata database
        self._init_db()

    def __getstate__(self):
        """Exclude unpicklable APScheduler instance for job serialization."""
        state = self.__dict__.copy()
        state.pop('scheduler', None)
        state.pop('_executors', None)
        return state

    def __setstate__(self, state):
        """Restore from pickle — scheduler and executors are re-wired on startup."""
        self.__dict__.update(state)
        self.scheduler = None
        self._executors = {}

    def _init_db(self):
        """Initialize the metadata database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS scheduled_content (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT UNIQUE NOT NULL,
                content_type TEXT NOT NULL,
                content_data TEXT NOT NULL,
                scheduled_time TEXT NOT NULL,
                created_at TEXT NOT NULL,
                status TEXT DEFAULT 'pending',
                executed_at TEXT,
                result TEXT
            )
        """)
        conn.commit()
        conn.close()

    def register_executor(self, content_type: str, executor: Callable):
        """Register an executor function for a content type."""
        self._executors[content_type] = executor
        logger.info(f"Registered executor for content type: {content_type}")

    async def start(self):
        """Start the scheduler."""
        self.scheduler.start()
        logger.info("Content scheduler started")

    async def stop(self):
        """Stop the scheduler."""
        self.scheduler.shutdown(wait=False)
        logger.info("Content scheduler stopped")

    def schedule(
        self,
        content_type: str,
        content_data: dict,
        scheduled_time: datetime,
        job_id: Optional[str] = None,
    ) -> str:
        """
        Schedule content for posting.

        Args:
            content_type: Type of content (e.g., "tweet", "video_tweet")
            content_data: Content payload
            scheduled_time: When to post
            job_id: Optional custom job ID

        Returns:
            Job ID
        """
        if not job_id:
            job_id = f"{content_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{os.urandom(4).hex()}"

        # Store metadata
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """INSERT INTO scheduled_content
               (job_id, content_type, content_data, scheduled_time, created_at)
               VALUES (?, ?, ?, ?, ?)""",
            (
                job_id,
                content_type,
                json.dumps(content_data),
                scheduled_time.isoformat(),
                datetime.now().isoformat(),
            )
        )
        conn.commit()
        conn.close()

        # Schedule the job — uses module-level function so APScheduler
        # doesn't pickle 'self' (which loses _executors on unpickle).
        self.scheduler.add_job(
            _dispatch_scheduled_job,
            trigger=DateTrigger(run_date=scheduled_time),
            args=[job_id],
            id=job_id,
            replace_existing=True,
        )

        logger.info(f"Scheduled {content_type} for {scheduled_time}: {job_id}")
        return job_id

    async def _execute_scheduled(self, job_id: str):
        """Execute a scheduled job."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.execute(
            "SELECT content_type, content_data FROM scheduled_content WHERE job_id = ?",
            (job_id,)
        )
        row = cursor.fetchone()
        conn.close()

        if not row:
            logger.error(f"Scheduled job not found: {job_id}")
            return

        content_type, content_data_json = row
        content_data = json.loads(content_data_json)

        executor = self._executors.get(content_type)
        if not executor:
            logger.error(f"No executor for content type: {content_type}")
            self._update_status(job_id, "failed", "No executor registered")
            return

        try:
            logger.info(f"Executing scheduled job: {job_id}")
            result = await executor(content_data)
            self._update_status(job_id, "executed", json.dumps(result) if result else None)
            logger.info(f"Executed scheduled job: {job_id}")
        except Exception as e:
            logger.error(f"Failed to execute scheduled job {job_id}: {e}")
            self._update_status(job_id, "failed", str(e))

    def _update_status(self, job_id: str, status: str, result: Optional[str] = None):
        """Update job status in database."""
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            """UPDATE scheduled_content
               SET status = ?, executed_at = ?, result = ?
               WHERE job_id = ?""",
            (status, datetime.now().isoformat(), result, job_id)
        )
        conn.commit()
        conn.close()

    def cancel(self, job_id: str) -> bool:
        """Cancel a scheduled job."""
        try:
            self.scheduler.remove_job(job_id)
            self._update_status(job_id, "cancelled")
            logger.info(f"Cancelled scheduled job: {job_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to cancel job {job_id}: {e}")
            return False

    def get_pending(self) -> list[dict]:
        """Get all pending scheduled content."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """SELECT * FROM scheduled_content
               WHERE status = 'pending'
               ORDER BY scheduled_time ASC"""
        )
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def get_upcoming(self, hours: int = 24) -> list[dict]:
        """Get content scheduled for the next N hours."""
        cutoff = (datetime.now() + timedelta(hours=hours)).isoformat()
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute(
            """SELECT * FROM scheduled_content
               WHERE status = 'pending' AND scheduled_time <= ?
               ORDER BY scheduled_time ASC""",
            (cutoff,)
        )
        rows = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return rows

    def reschedule(self, job_id: str, new_time: datetime) -> bool:
        """Reschedule an existing job."""
        try:
            self.scheduler.reschedule_job(
                job_id,
                trigger=DateTrigger(run_date=new_time)
            )
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "UPDATE scheduled_content SET scheduled_time = ? WHERE job_id = ?",
                (new_time.isoformat(), job_id)
            )
            conn.commit()
            conn.close()
            logger.info(f"Rescheduled {job_id} to {new_time}")
            return True
        except Exception as e:
            logger.error(f"Failed to reschedule {job_id}: {e}")
            return False


# Platform-specific optimal posting times (UTC) — targeting US audience peaks.
# Twitter:  13, 16, 19, 22 UTC = 8am, 11am, 2pm, 5pm ET
# YouTube:  18, 21, 0 UTC     = 1pm, 4pm, 7pm ET
# TikTok:   16, 19, 23, 1 UTC = 11am, 2pm, 6pm, 8pm ET
# Must match dashboard/app.py PLATFORM_OPTIMAL_HOURS
PLATFORM_OPTIMAL_HOURS = {
    "twitter": [13, 16, 19, 22],
    "youtube": [18, 21, 0],
    "tiktok": [16, 19, 23, 1],
}


def suggest_time_slots(count: int = 4, platforms: list[str] | None = None) -> list[datetime]:
    """
    Suggest optimal posting times based on platform engagement research.

    Uses UTC hours. Returns the soonest slots at least 30 minutes from now.
    """
    if platforms is None:
        platforms = ["twitter", "youtube", "tiktok"]

    now = datetime.utcnow()
    min_post_time = now + timedelta(minutes=30)

    candidate_hours = set()
    for platform in platforms:
        hours = PLATFORM_OPTIMAL_HOURS.get(platform, [12, 18])
        candidate_hours.update(hours)

    slots = []
    for hour in sorted(candidate_hours):
        slot = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if slot <= min_post_time:
            slot += timedelta(days=1)
        slots.append(slot)

    slots.sort()
    return slots[:count]
