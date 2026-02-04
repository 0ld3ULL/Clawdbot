"""
Token budget manager.

Enforces prepaid-only token budgets with daily caps per project.
Ganzak principle: no auto-billing, add small amounts, monitor closely.
"""

import sqlite3
from datetime import datetime, date
from pathlib import Path


class TokenBudgetManager:

    def __init__(self, db_path: str = "data/token_budget.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        with self._connect() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS token_usage (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    project_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    tokens_input INTEGER DEFAULT 0,
                    tokens_output INTEGER DEFAULT 0,
                    cost_usd REAL DEFAULT 0.0,
                    task_type TEXT DEFAULT '',
                    agent_id TEXT DEFAULT '',
                    timestamp TEXT NOT NULL
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS budgets (
                    project_id TEXT PRIMARY KEY,
                    daily_limit REAL NOT NULL,
                    monthly_limit REAL NOT NULL
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_usage_project_date
                ON token_usage(project_id, timestamp)
            """)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def set_budget(self, project_id: str, daily: float, monthly: float):
        """Set budget limits for a project."""
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO budgets
                   (project_id, daily_limit, monthly_limit)
                   VALUES (?, ?, ?)""",
                (project_id, daily, monthly)
            )

    def has_budget(self, project_id: str) -> bool:
        """Check if project has remaining daily budget."""
        daily_spend = self.get_daily_spend(project_id)
        daily_limit = self.get_daily_limit(project_id)
        return daily_spend < daily_limit

    def get_daily_limit(self, project_id: str) -> float:
        """Get daily budget limit for a project."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT daily_limit FROM budgets WHERE project_id=?",
                (project_id,)
            ).fetchone()
            return row["daily_limit"] if row else 10.0  # Default $10/day

    def get_daily_spend(self, project_id: str) -> float:
        """Get total spend for today."""
        today = date.today().isoformat()
        with self._connect() as conn:
            row = conn.execute(
                """SELECT COALESCE(SUM(cost_usd), 0) as total
                   FROM token_usage
                   WHERE project_id=? AND DATE(timestamp)=?""",
                (project_id, today)
            ).fetchone()
            return row["total"]

    def record_usage(self, project_id: str, model: str,
                     tokens_in: int, tokens_out: int,
                     cost: float, task_type: str = "",
                     agent_id: str = ""):
        """Record token usage."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO token_usage
                   (project_id, model, tokens_input, tokens_output,
                    cost_usd, task_type, agent_id, timestamp)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (project_id, model, tokens_in, tokens_out,
                 cost, task_type, agent_id,
                 datetime.now().isoformat())
            )

    def calculate_cost(self, model: str, tokens_in: int,
                       tokens_out: int) -> float:
        """Calculate cost based on model pricing."""
        # Pricing per 1M tokens (input, output)
        pricing = {
            "llama3.2:8b": (0.0, 0.0),
            "claude-3-5-haiku-20241022": (0.80, 4.00),
            "claude-sonnet-4-20250514": (3.00, 15.00),
            "claude-opus-4-5-20251101": (15.00, 75.00),
            "gpt-4o-mini": (0.15, 0.60),
        }
        in_price, out_price = pricing.get(model, (3.00, 15.00))
        return (tokens_in * in_price + tokens_out * out_price) / 1_000_000

    def get_daily_report(self, project_id: str) -> dict:
        """Generate daily cost report."""
        today = date.today().isoformat()
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT model,
                          SUM(tokens_input) as total_in,
                          SUM(tokens_output) as total_out,
                          SUM(cost_usd) as total_cost,
                          COUNT(*) as call_count
                   FROM token_usage
                   WHERE project_id=? AND DATE(timestamp)=?
                   GROUP BY model""",
                (project_id, today)
            ).fetchall()

            total_cost = sum(r["total_cost"] for r in rows)
            daily_limit = self.get_daily_limit(project_id)

            return {
                "date": today,
                "project_id": project_id,
                "total_cost": total_cost,
                "daily_limit": daily_limit,
                "remaining": daily_limit - total_cost,
                "by_model": [dict(r) for r in rows],
            }

    def get_weekly_report(self, project_id: str) -> list[dict]:
        """Get daily totals for the last 7 days."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT DATE(timestamp) as day,
                          SUM(cost_usd) as total_cost,
                          SUM(tokens_input + tokens_output) as total_tokens,
                          COUNT(*) as call_count
                   FROM token_usage
                   WHERE project_id=?
                     AND timestamp >= datetime('now', '-7 days')
                   GROUP BY DATE(timestamp)
                   ORDER BY day DESC""",
                (project_id,)
            ).fetchall()
            return [dict(r) for r in rows]
