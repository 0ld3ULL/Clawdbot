"""
Activity audit log.

Every action the system takes is recorded. This provides:
1. Full audit trail for security review
2. Error routing to Telegram (Ganzak Rule 7)
3. Severity-based alerting (Ganzak Rule 8)
"""

import sqlite3
from datetime import datetime, date
from pathlib import Path


class AuditLog:

    def __init__(self, db_path: str = "data/audit_log.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._alert_callback = None
        self._init_db()

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    project_id TEXT NOT NULL,
                    agent_id TEXT DEFAULT '',
                    severity TEXT NOT NULL,
                    category TEXT NOT NULL,
                    action TEXT NOT NULL,
                    details TEXT DEFAULT '',
                    tokens_used INTEGER DEFAULT 0,
                    cost_usd REAL DEFAULT 0.0,
                    model TEXT DEFAULT '',
                    success INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_severity
                ON audit_log(severity)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_project_date
                ON audit_log(project_id, timestamp)
            """)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def set_alert_callback(self, callback):
        """Set callback for high-severity alerts (e.g., Telegram notify)."""
        self._alert_callback = callback

    def log(self, project_id: str, severity: str,
            category: str, action: str,
            details: str = "", agent_id: str = "",
            tokens: int = 0, cost: float = 0.0,
            model: str = "", success: bool = True):
        """
        Log an event.

        Severity levels (Ganzak Rule 8):
            info     - Informational, logged only
            warn     - Warning, logged + continue
            block    - Blocked but recoverable
            reject   - Rejected, user intervention needed
            critical - STOP EVERYTHING, alert immediately
        """
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO audit_log
                   (timestamp, project_id, agent_id, severity,
                    category, action, details, tokens_used,
                    cost_usd, model, success)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (datetime.now().isoformat(), project_id, agent_id,
                 severity, category, action, details, tokens,
                 cost, model, 1 if success else 0)
            )

        # Alert on high severity (Ganzak Rule 7: pipe errors to messenger)
        if severity in ("block", "reject", "critical") and self._alert_callback:
            self._alert_callback(
                f"[{severity.upper()}] {category}: {action}\n{details}"
            )

    def get_daily_summary(self, project_id: str) -> dict:
        """Generate daily summary for reporting."""
        today = date.today().isoformat()
        with self._connect() as conn:
            total = conn.execute(
                """SELECT COUNT(*) as cnt FROM audit_log
                   WHERE project_id=? AND DATE(timestamp)=?""",
                (project_id, today)
            ).fetchone()["cnt"]

            cost = conn.execute(
                """SELECT COALESCE(SUM(cost_usd), 0) as total
                   FROM audit_log
                   WHERE project_id=? AND DATE(timestamp)=?""",
                (project_id, today)
            ).fetchone()["total"]

            errors = conn.execute(
                """SELECT COUNT(*) as cnt FROM audit_log
                   WHERE project_id=? AND DATE(timestamp)=?
                   AND success=0""",
                (project_id, today)
            ).fetchone()["cnt"]

            by_severity = {}
            for sev in ("info", "warn", "block", "reject", "critical"):
                cnt = conn.execute(
                    """SELECT COUNT(*) as cnt FROM audit_log
                       WHERE project_id=? AND DATE(timestamp)=?
                       AND severity=?""",
                    (project_id, today, sev)
                ).fetchone()["cnt"]
                if cnt > 0:
                    by_severity[sev] = cnt

            return {
                "date": today,
                "total_actions": total,
                "total_cost": cost,
                "errors": errors,
                "by_severity": by_severity,
            }

    def get_recent(self, project_id: str | None = None,
                   limit: int = 50) -> list[dict]:
        """Get recent log entries."""
        with self._connect() as conn:
            if project_id:
                rows = conn.execute(
                    """SELECT * FROM audit_log
                       WHERE project_id=?
                       ORDER BY timestamp DESC LIMIT ?""",
                    (project_id, limit)
                ).fetchall()
            else:
                rows = conn.execute(
                    """SELECT * FROM audit_log
                       ORDER BY timestamp DESC LIMIT ?""",
                    (limit,)
                ).fetchall()
            return [dict(r) for r in rows]
