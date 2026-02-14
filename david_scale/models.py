"""
David Scale — Database models and seed data.

Separate SQLite DB (data/david_scale.db) for tool registry,
weekly scores, mention tracking, and influencer reviews.

Six scoring pillars:
  Industry (10%) + Influencer (25%) + Customer (25%) +
  Usability (15%) + Value (15%) + Momentum (10%)

Influencer pillar is credibility-weighted:
  Each influencer has an accuracy score (did their past calls match reality?)
  and an experience score (how deeply did they use the tool?).
  Reviews from credible influencers count more.
"""

import os
import sqlite3
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("DAVID_DATA_DIR", "data"))
DB_PATH = DATA_DIR / "david_scale.db"

# Categories for AI tools
CATEGORIES = {
    "llms": "LLMs (Chat)",
    "code": "Code Assistants",
    "vibe-coding": "Vibe Coding",
    "video-gen": "Video Generators",
    "image-gen": "Image Generators",
    "agents": "AI Agents",
    "video-edit": "Video Editing",
    "research": "Research / Search",
}

# Seed data dict list for clarity
# usability: 0-10 how intuitive (10 = grandma could use it)
# learning_hours: hours until average user gets good results
SEED_TOOLS = [
    # LLMs (Chat)
    {"name": "ChatGPT", "slug": "chatgpt", "cat": "llms", "url": "https://chat.openai.com", "desc": "OpenAI's flagship chat model", "bench": 8.5, "usability": 9.0, "hours": 0.5, "price": 20, "price_notes": "Plus plan"},
    {"name": "Claude", "slug": "claude", "cat": "llms", "url": "https://claude.ai", "desc": "Anthropic's conversational AI", "bench": 8.7, "usability": 9.0, "hours": 0.5, "price": 20, "price_notes": "Pro plan"},
    {"name": "Gemini", "slug": "gemini", "cat": "llms", "url": "https://gemini.google.com", "desc": "Google DeepMind's multimodal model", "bench": 8.0, "usability": 8.5, "hours": 0.5, "price": 20, "price_notes": "Advanced plan"},
    {"name": "Llama", "slug": "llama", "cat": "llms", "url": "https://llama.meta.com", "desc": "Meta's open-source LLM family", "bench": 7.5, "usability": 4.0, "hours": 10, "price": 0, "price_notes": "Open source, self-host"},
    {"name": "Mistral", "slug": "mistral", "cat": "llms", "url": "https://mistral.ai", "desc": "European open-weight models", "bench": 7.3, "usability": 5.0, "hours": 5, "price": 0, "price_notes": "Open weights available"},
    {"name": "Grok", "slug": "grok", "cat": "llms", "url": "https://grok.x.ai", "desc": "xAI's conversational model", "bench": 7.0, "usability": 8.0, "hours": 0.5, "price": 8, "price_notes": "X Premium"},
    {"name": "DeepSeek", "slug": "deepseek", "cat": "llms", "url": "https://deepseek.com", "desc": "Chinese open-source reasoning model", "bench": 7.8, "usability": 7.0, "hours": 1, "price": 0, "price_notes": "Free / open source"},
    {"name": "Qwen", "slug": "qwen", "cat": "llms", "url": "https://qwen.ai", "desc": "Alibaba's multilingual model", "bench": 7.2, "usability": 5.0, "hours": 3, "price": 0, "price_notes": "Open source"},

    # Code Assistants
    {"name": "Claude Code", "slug": "claude-code", "cat": "code", "url": "https://claude.ai", "desc": "Anthropic's CLI coding agent", "bench": 8.5, "usability": 7.0, "hours": 2, "price": 20, "price_notes": "Pro plan + API usage"},
    {"name": "Cursor", "slug": "cursor", "cat": "code", "url": "https://cursor.com", "desc": "AI-first code editor", "bench": 8.3, "usability": 8.5, "hours": 1, "price": 20, "price_notes": "Pro plan"},
    {"name": "GitHub Copilot", "slug": "copilot", "cat": "code", "url": "https://github.com/features/copilot", "desc": "GitHub's AI pair programmer", "bench": 7.8, "usability": 9.0, "hours": 0.5, "price": 10, "price_notes": "Individual plan"},
    {"name": "Windsurf", "slug": "windsurf", "cat": "code", "url": "https://codeium.com/windsurf", "desc": "Codeium's AI IDE", "bench": 7.5, "usability": 8.0, "hours": 1, "price": 15, "price_notes": "Pro plan"},
    {"name": "Aider", "slug": "aider", "cat": "code", "url": "https://aider.chat", "desc": "Terminal-based AI coding assistant", "bench": 7.6, "usability": 5.0, "hours": 4, "price": 0, "price_notes": "Free + bring your API key"},
    {"name": "Devin", "slug": "devin", "cat": "code", "url": "https://devin.ai", "desc": "Cognition's autonomous software engineer", "bench": 7.0, "usability": 6.0, "hours": 8, "price": 500, "price_notes": "Team plan"},
    {"name": "Codex", "slug": "codex", "cat": "code", "url": "https://openai.com/codex", "desc": "OpenAI's coding agent", "bench": 7.4, "usability": 7.5, "hours": 1, "price": 20, "price_notes": "ChatGPT Pro"},

    # Vibe Coding (tools built for non-programmers / rapid prototyping)
    {"name": "Replit", "slug": "replit", "cat": "vibe-coding", "url": "https://replit.com", "desc": "Browser IDE with AI agent for building apps from prompts", "bench": 7.5, "usability": 9.0, "hours": 0.5, "price": 25, "price_notes": "Hacker plan"},
    {"name": "Bolt.new", "slug": "bolt-new", "cat": "vibe-coding", "url": "https://bolt.new", "desc": "Full-stack web apps from a single prompt", "bench": 7.0, "usability": 9.5, "hours": 0.1, "price": 20, "price_notes": "Pro plan"},
    {"name": "Lovable", "slug": "lovable", "cat": "vibe-coding", "url": "https://lovable.dev", "desc": "AI app builder — describe it, ship it", "bench": 6.8, "usability": 9.5, "hours": 0.1, "price": 20, "price_notes": "Starter plan"},
    {"name": "v0", "slug": "v0", "cat": "vibe-coding", "url": "https://v0.dev", "desc": "Vercel's AI UI generator", "bench": 7.2, "usability": 9.0, "hours": 0.2, "price": 20, "price_notes": "Premium plan"},
    {"name": "Claude Code (Vibe)", "slug": "claude-code-vibe", "cat": "vibe-coding", "url": "https://claude.ai", "desc": "Anthropic's CLI agent — vibe code in terminal", "bench": 8.5, "usability": 6.5, "hours": 1, "price": 20, "price_notes": "Pro plan + API"},
    {"name": "Cursor (Vibe)", "slug": "cursor-vibe", "cat": "vibe-coding", "url": "https://cursor.com", "desc": "AI-first IDE — vibe coding with Composer", "bench": 8.3, "usability": 8.0, "hours": 0.5, "price": 20, "price_notes": "Pro plan"},

    # Video Generators
    {"name": "Seedance", "slug": "seedance", "cat": "video-gen", "url": "https://seedance.ai", "desc": "ByteDance's video generation model", "bench": 7.5, "usability": 7.0, "hours": 2, "price": None, "price_notes": "Credits-based"},
    {"name": "Kling", "slug": "kling", "cat": "video-gen", "url": "https://kling.ai", "desc": "Kuaishou's AI video generator", "bench": 7.8, "usability": 7.5, "hours": 1, "price": 8, "price_notes": "Standard plan"},
    {"name": "Runway", "slug": "runway", "cat": "video-gen", "url": "https://runwayml.com", "desc": "Gen-3 Alpha video generation", "bench": 8.0, "usability": 8.0, "hours": 1, "price": 15, "price_notes": "Standard plan"},
    {"name": "Pika", "slug": "pika", "cat": "video-gen", "url": "https://pika.art", "desc": "AI video creation platform", "bench": 7.0, "usability": 8.5, "hours": 0.5, "price": 8, "price_notes": "Standard plan"},
    {"name": "Sora", "slug": "sora", "cat": "video-gen", "url": "https://openai.com/sora", "desc": "OpenAI's video generation model", "bench": 7.5, "usability": 8.0, "hours": 1, "price": 20, "price_notes": "ChatGPT Plus"},
    {"name": "Veo", "slug": "veo", "cat": "video-gen", "url": "https://deepmind.google/veo", "desc": "Google DeepMind's video model", "bench": 7.3, "usability": 7.5, "hours": 1, "price": 20, "price_notes": "Gemini Advanced"},
    {"name": "Minimax", "slug": "minimax", "cat": "video-gen", "url": "https://minimax.io", "desc": "Chinese multimodal AI company", "bench": 7.0, "usability": 6.0, "hours": 3, "price": None, "price_notes": "Credits-based"},

    # Image Generators
    {"name": "Midjourney", "slug": "midjourney", "cat": "image-gen", "url": "https://midjourney.com", "desc": "Leading AI image generation", "bench": 9.0, "usability": 6.0, "hours": 5, "price": 10, "price_notes": "Basic plan"},
    {"name": "DALL-E 3", "slug": "dall-e-3", "cat": "image-gen", "url": "https://openai.com/dall-e-3", "desc": "OpenAI's image generator", "bench": 7.5, "usability": 9.0, "hours": 0.5, "price": 20, "price_notes": "ChatGPT Plus"},
    {"name": "Flux", "slug": "flux", "cat": "image-gen", "url": "https://blackforestlabs.ai", "desc": "Black Forest Labs' open model", "bench": 8.0, "usability": 4.0, "hours": 10, "price": 0, "price_notes": "Open source"},
    {"name": "Stable Diffusion", "slug": "stable-diffusion", "cat": "image-gen", "url": "https://stability.ai", "desc": "Stability AI's open-source model", "bench": 7.0, "usability": 3.0, "hours": 20, "price": 0, "price_notes": "Open source, self-host"},
    {"name": "Ideogram", "slug": "ideogram", "cat": "image-gen", "url": "https://ideogram.ai", "desc": "AI image generation with text rendering", "bench": 7.5, "usability": 8.5, "hours": 0.5, "price": 8, "price_notes": "Basic plan"},

    # AI Agents
    {"name": "OpenAI Agents SDK", "slug": "openai-agents", "cat": "agents", "url": "https://openai.com", "desc": "OpenAI's agent framework", "bench": 7.0, "usability": 4.0, "hours": 20, "price": 0, "price_notes": "Free SDK + API costs"},
    {"name": "LangChain", "slug": "langchain", "cat": "agents", "url": "https://langchain.com", "desc": "Popular LLM application framework", "bench": 7.5, "usability": 3.5, "hours": 30, "price": 0, "price_notes": "Open source"},
    {"name": "CrewAI", "slug": "crewai", "cat": "agents", "url": "https://crewai.com", "desc": "Multi-agent orchestration framework", "bench": 7.0, "usability": 5.0, "hours": 15, "price": 0, "price_notes": "Open source"},
    {"name": "AutoGen", "slug": "autogen", "cat": "agents", "url": "https://microsoft.github.io/autogen", "desc": "Microsoft's multi-agent framework", "bench": 6.8, "usability": 4.0, "hours": 20, "price": 0, "price_notes": "Open source"},

    # Video Editing
    {"name": "Focal ML", "slug": "focal-ml", "cat": "video-edit", "url": "https://focalml.com", "desc": "AI video creation and editing", "bench": 7.0, "usability": 7.5, "hours": 2, "price": 30, "price_notes": "Personal plan"},
    {"name": "Descript", "slug": "descript", "cat": "video-edit", "url": "https://descript.com", "desc": "AI-powered video/audio editing", "bench": 7.5, "usability": 8.5, "hours": 1, "price": 24, "price_notes": "Hobbyist plan"},
    {"name": "Kapwing", "slug": "kapwing", "cat": "video-edit", "url": "https://kapwing.com", "desc": "Online AI video editor", "bench": 6.5, "usability": 8.0, "hours": 1, "price": 16, "price_notes": "Pro plan"},

    # Research / Search
    {"name": "Perplexity", "slug": "perplexity", "cat": "research", "url": "https://perplexity.ai", "desc": "AI-powered search engine", "bench": 8.5, "usability": 9.5, "hours": 0.1, "price": 20, "price_notes": "Pro plan"},
    {"name": "Google AI Overview", "slug": "google-ai-overview", "cat": "research", "url": "https://google.com", "desc": "Google's AI search integration", "bench": 7.0, "usability": 10.0, "hours": 0, "price": 0, "price_notes": "Free"},
    {"name": "You.com", "slug": "you-com", "cat": "research", "url": "https://you.com", "desc": "AI search with citations", "bench": 6.5, "usability": 8.5, "hours": 0.1, "price": 15, "price_notes": "YouPro plan"},
]


class DavidScaleDB:
    """Database helper for the David Scale."""

    def __init__(self, db_path: Optional[Path] = None):
        self.db_path = db_path or DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _init_db(self):
        """Create tables if they don't exist."""
        with self._connect() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tools (
                    id INTEGER PRIMARY KEY,
                    name TEXT UNIQUE NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    category TEXT NOT NULL,
                    website TEXT,
                    description TEXT,
                    benchmark_score REAL DEFAULT 0,
                    usability_score REAL DEFAULT 5,
                    learning_hours REAL,
                    price_monthly REAL,
                    price_notes TEXT,
                    active BOOLEAN DEFAULT TRUE
                );

                CREATE TABLE IF NOT EXISTS scores (
                    id INTEGER PRIMARY KEY,
                    tool_id INTEGER REFERENCES tools(id),
                    week_date DATE NOT NULL,
                    industry REAL,
                    influencer REAL,
                    customer REAL,
                    usability REAL,
                    value REAL,
                    momentum REAL,
                    david_score REAL,
                    rank_in_category INTEGER,
                    mentions_count INTEGER,
                    UNIQUE(tool_id, week_date)
                );

                CREATE TABLE IF NOT EXISTS mentions (
                    id INTEGER PRIMARY KEY,
                    tool_id INTEGER REFERENCES tools(id),
                    source TEXT,
                    source_url TEXT,
                    sentiment TEXT,
                    snippet TEXT,
                    scraped_at DATETIME
                );

                CREATE INDEX IF NOT EXISTS idx_scores_week
                    ON scores(week_date);
                CREATE INDEX IF NOT EXISTS idx_scores_tool_week
                    ON scores(tool_id, week_date);
                CREATE INDEX IF NOT EXISTS idx_mentions_tool
                    ON mentions(tool_id);
                CREATE INDEX IF NOT EXISTS idx_mentions_scraped
                    ON mentions(scraped_at);

                CREATE TABLE IF NOT EXISTS influencers (
                    id INTEGER PRIMARY KEY,
                    name TEXT NOT NULL,
                    slug TEXT UNIQUE NOT NULL,
                    platform TEXT NOT NULL,
                    channel_url TEXT,
                    accuracy_score REAL DEFAULT 5.0,
                    experience_score REAL DEFAULT 5.0,
                    credibility_score REAL DEFAULT 5.0,
                    correct_calls INTEGER DEFAULT 0,
                    total_calls INTEGER DEFAULT 0,
                    review_count INTEGER DEFAULT 0,
                    first_seen DATETIME,
                    last_seen DATETIME
                );

                CREATE INDEX IF NOT EXISTS idx_influencer_slug
                    ON influencers(slug);

                CREATE TABLE IF NOT EXISTS influencer_reviews (
                    id INTEGER PRIMARY KEY,
                    tool_id INTEGER REFERENCES tools(id),
                    influencer_id INTEGER REFERENCES influencers(id),
                    influencer_name TEXT NOT NULL,
                    platform TEXT NOT NULL,
                    video_url TEXT,
                    sentiment TEXT,
                    summary TEXT,
                    snippet TEXT,
                    experience_depth REAL DEFAULT 5.0,
                    reviewed_at DATETIME,
                    scraped_at DATETIME
                );

                CREATE INDEX IF NOT EXISTS idx_influencer_reviews_tool
                    ON influencer_reviews(tool_id);
                CREATE INDEX IF NOT EXISTS idx_influencer_reviews_scraped
                    ON influencer_reviews(scraped_at);
                CREATE INDEX IF NOT EXISTS idx_influencer_reviews_influencer
                    ON influencer_reviews(influencer_id);

                CREATE TABLE IF NOT EXISTS listing_applications (
                    id INTEGER PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    website TEXT NOT NULL,
                    category TEXT NOT NULL,
                    description TEXT,
                    contact_email TEXT NOT NULL,
                    contact_name TEXT,
                    price_info TEXT,
                    why_list TEXT,
                    status TEXT DEFAULT 'pending',
                    submitted_at DATETIME,
                    reviewed_at DATETIME,
                    notes TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_listing_status
                    ON listing_applications(status);
            """)

    def seed(self):
        """Seed the database with initial tools. Skips existing."""
        with self._connect() as conn:
            for t in SEED_TOOLS:
                try:
                    conn.execute(
                        """INSERT OR IGNORE INTO tools
                           (name, slug, category, website, description,
                            benchmark_score, usability_score, learning_hours,
                            price_monthly, price_notes)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (t["name"], t["slug"], t["cat"], t["url"], t["desc"],
                         t["bench"], t.get("usability", 5), t.get("hours"),
                         t.get("price"), t.get("price_notes", ""))
                    )
                except sqlite3.IntegrityError:
                    pass
            conn.commit()
        logger.info(f"Seeded {len(SEED_TOOLS)} tools")

    def get_tools(self, category: Optional[str] = None,
                  active_only: bool = True) -> list[dict]:
        """Get all tools, optionally filtered by category."""
        with self._connect() as conn:
            query = "SELECT * FROM tools"
            params = []
            clauses = []
            if active_only:
                clauses.append("active = 1")
            if category:
                clauses.append("category = ?")
                params.append(category)
            if clauses:
                query += " WHERE " + " AND ".join(clauses)
            query += " ORDER BY name"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_tool_by_slug(self, slug: str) -> Optional[dict]:
        """Get a single tool by slug."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tools WHERE slug = ?", (slug,)
            ).fetchone()
            return dict(row) if row else None

    def get_tool_by_name(self, name: str) -> Optional[dict]:
        """Get a single tool by exact name."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM tools WHERE name = ?", (name,)
            ).fetchone()
            return dict(row) if row else None

    def save_mention(self, tool_id: int, source: str, source_url: str,
                     sentiment: str, snippet: str,
                     scraped_at: Optional[datetime] = None):
        """Save a mention of a tool."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO mentions
                   (tool_id, source, source_url, sentiment, snippet, scraped_at)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (tool_id, source, source_url, sentiment, snippet,
                 (scraped_at or datetime.utcnow()).isoformat())
            )

    def save_score(self, tool_id: int, week_date: str,
                   industry: float, influencer: float, customer: float,
                   usability: float, value: float, momentum: float,
                   david_score: float,
                   rank_in_category: int, mentions_count: int):
        """Save or update a weekly score."""
        with self._connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO scores
                   (tool_id, week_date, industry, influencer, customer,
                    usability, value, momentum,
                    david_score, rank_in_category, mentions_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (tool_id, week_date, industry, influencer, customer,
                 usability, value, momentum,
                 david_score, rank_in_category, mentions_count)
            )

    def get_or_create_influencer(self, name: str, platform: str,
                                    channel_url: str = "") -> int:
        """Get or create an influencer record. Returns influencer id."""
        import re
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        now = datetime.utcnow().isoformat()

        with self._connect() as conn:
            row = conn.execute(
                "SELECT id FROM influencers WHERE slug = ?", (slug,)
            ).fetchone()

            if row:
                conn.execute(
                    "UPDATE influencers SET last_seen = ? WHERE id = ?",
                    (now, row["id"])
                )
                return row["id"]

            cursor = conn.execute(
                """INSERT INTO influencers
                   (name, slug, platform, channel_url, first_seen, last_seen)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (name, slug, platform, channel_url, now, now)
            )
            return cursor.lastrowid

    def save_influencer_review(self, tool_id: int, influencer_name: str,
                                platform: str, video_url: str,
                                sentiment: str, summary: str,
                                snippet: str = "",
                                experience_depth: float = 5.0,
                                reviewed_at: Optional[datetime] = None,
                                scraped_at: Optional[datetime] = None):
        """Save an influencer review of a tool, linked to influencer profile."""
        influencer_id = self.get_or_create_influencer(
            influencer_name, platform, video_url
        )

        with self._connect() as conn:
            conn.execute(
                """INSERT INTO influencer_reviews
                   (tool_id, influencer_id, influencer_name, platform, video_url,
                    sentiment, summary, snippet, experience_depth,
                    reviewed_at, scraped_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (tool_id, influencer_id, influencer_name, platform, video_url,
                 sentiment, summary, snippet, experience_depth,
                 (reviewed_at or datetime.utcnow()).isoformat(),
                 (scraped_at or datetime.utcnow()).isoformat())
            )

            # Update influencer review count
            conn.execute(
                """UPDATE influencers SET review_count = review_count + 1
                   WHERE id = ?""",
                (influencer_id,)
            )

    def get_influencer_reviews(self, tool_id: int, days: int = 7,
                                limit: int = 50) -> list[dict]:
        """Get recent influencer reviews for a tool, with credibility data."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT ir.*, i.accuracy_score, i.experience_score,
                          i.credibility_score, i.review_count as influencer_review_count
                   FROM influencer_reviews ir
                   LEFT JOIN influencers i ON ir.influencer_id = i.id
                   WHERE ir.tool_id = ?
                   AND ir.scraped_at >= datetime('now', ?)
                   ORDER BY ir.scraped_at DESC LIMIT ?""",
                (tool_id, f"-{days} days", limit)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_influencer_reviews_count(self, tool_id: int,
                                      days: int = 7) -> int:
        """Count recent influencer reviews for a tool."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM influencer_reviews
                   WHERE tool_id = ?
                   AND scraped_at >= datetime('now', ?)""",
                (tool_id, f"-{days} days")
            ).fetchone()
            return row["cnt"] if row else 0

    def update_influencer_accuracy(self, influencer_id: int,
                                     was_correct: bool):
        """Update an influencer's accuracy after verifying against reality.

        Called after scoring: compare influencer's sentiment call
        against actual customer sentiment for the same tool.
        - Influencer said "positive" + customer sentiment > 6.0 = correct
        - Influencer said "negative" + customer sentiment < 4.0 = correct
        - Influencer said "neutral" + customer sentiment 4.0-6.0 = correct
        """
        with self._connect() as conn:
            conn.execute(
                """UPDATE influencers SET
                   total_calls = total_calls + 1,
                   correct_calls = correct_calls + ?,
                   accuracy_score = CASE
                       WHEN total_calls + 1 > 0
                       THEN ROUND((correct_calls + ?) * 10.0 / (total_calls + 1), 2)
                       ELSE 5.0
                   END,
                   credibility_score = ROUND(
                       (CASE
                           WHEN total_calls + 1 > 0
                           THEN (correct_calls + ?) * 10.0 / (total_calls + 1)
                           ELSE 5.0
                       END) * 0.5 + experience_score * 0.5, 2)
                   WHERE id = ?""",
                (1 if was_correct else 0,
                 1 if was_correct else 0,
                 1 if was_correct else 0,
                 influencer_id)
            )

    def update_influencer_experience(self, influencer_id: int,
                                       experience_depth: float):
        """Update an influencer's experience score (rolling average)."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT experience_score, review_count FROM influencers WHERE id = ?",
                (influencer_id,)
            ).fetchone()

            if row:
                # Exponential moving average — recent reviews matter more
                old = row["experience_score"] or 5.0
                count = row["review_count"] or 1
                alpha = min(0.3, 1.0 / count)  # Higher alpha for fewer reviews
                new_exp = round(old * (1 - alpha) + experience_depth * alpha, 2)

                conn.execute(
                    """UPDATE influencers SET
                       experience_score = ?,
                       credibility_score = ROUND(accuracy_score * 0.5 + ? * 0.5, 2)
                       WHERE id = ?""",
                    (new_exp, new_exp, influencer_id)
                )

    def get_influencer(self, influencer_id: int) -> Optional[dict]:
        """Get an influencer profile by ID."""
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM influencers WHERE id = ?", (influencer_id,)
            ).fetchone()
            return dict(row) if row else None

    def get_top_influencers(self, limit: int = 20) -> list[dict]:
        """Get influencers ranked by credibility score."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM influencers
                   WHERE review_count >= 3
                   ORDER BY credibility_score DESC LIMIT ?""",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_latest_scores(self, category: Optional[str] = None,
                          limit: int = 50) -> list[dict]:
        """Get the most recent scores for all tools, optionally by category."""
        with self._connect() as conn:
            query = """
                SELECT s.*, t.name, t.slug, t.category, t.website,
                       t.description, t.benchmark_score
                FROM scores s
                JOIN tools t ON s.tool_id = t.id
                WHERE s.week_date = (SELECT MAX(week_date) FROM scores)
            """
            params = []
            if category:
                query += " AND t.category = ?"
                params.append(category)
            query += " ORDER BY s.david_score DESC"
            if limit:
                query += f" LIMIT {limit}"
            rows = conn.execute(query, params).fetchall()
            return [dict(r) for r in rows]

    def get_score_history(self, tool_id: int, weeks: int = 12) -> list[dict]:
        """Get score history for a tool."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM scores
                   WHERE tool_id = ?
                   ORDER BY week_date DESC LIMIT ?""",
                (tool_id, weeks)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_previous_scores(self, week_date: str) -> list[dict]:
        """Get the scores from the week before the given date."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT s.*, t.name, t.slug, t.category
                   FROM scores s
                   JOIN tools t ON s.tool_id = t.id
                   WHERE s.week_date = (
                       SELECT MAX(week_date) FROM scores
                       WHERE week_date < ?
                   )
                   ORDER BY s.david_score DESC""",
                (week_date,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_mentions_count(self, tool_id: int, days: int = 7) -> int:
        """Count recent mentions for a tool."""
        with self._connect() as conn:
            row = conn.execute(
                """SELECT COUNT(*) as cnt FROM mentions
                   WHERE tool_id = ?
                   AND scraped_at >= datetime('now', ?)""",
                (tool_id, f"-{days} days")
            ).fetchone()
            return row["cnt"] if row else 0

    def get_mentions(self, tool_id: int, days: int = 7,
                     limit: int = 50) -> list[dict]:
        """Get recent mentions for a tool."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM mentions
                   WHERE tool_id = ?
                   AND scraped_at >= datetime('now', ?)
                   ORDER BY scraped_at DESC LIMIT ?""",
                (tool_id, f"-{days} days", limit)
            ).fetchall()
            return [dict(r) for r in rows]

    def save_listing_application(self, tool_name: str, website: str,
                                    category: str, description: str,
                                    contact_email: str, contact_name: str = "",
                                    price_info: str = "", why_list: str = ""):
        """Save a new listing application."""
        with self._connect() as conn:
            conn.execute(
                """INSERT INTO listing_applications
                   (tool_name, website, category, description,
                    contact_email, contact_name, price_info, why_list,
                    status, submitted_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?)""",
                (tool_name, website, category, description,
                 contact_email, contact_name, price_info, why_list,
                 datetime.utcnow().isoformat())
            )

    def get_listing_applications(self, status: str = "pending") -> list[dict]:
        """Get listing applications filtered by status."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT * FROM listing_applications
                   WHERE status = ? ORDER BY submitted_at DESC""",
                (status,)
            ).fetchall()
            return [dict(r) for r in rows]

    def get_categories_with_counts(self) -> list[dict]:
        """Get categories with tool counts."""
        with self._connect() as conn:
            rows = conn.execute(
                """SELECT category, COUNT(*) as count
                   FROM tools WHERE active = 1
                   GROUP BY category ORDER BY count DESC"""
            ).fetchall()
            result = []
            for row in rows:
                cat = row["category"]
                result.append({
                    "slug": cat,
                    "name": CATEGORIES.get(cat, cat),
                    "count": row["count"],
                })
            return result


# Quick test entry point
if __name__ == "__main__":
    db = DavidScaleDB()
    db.seed()
    tools = db.get_tools()
    print(f"Seeded {len(tools)} tools:")
    for t in tools:
        price = f"${t['price_monthly']}/mo" if t.get('price_monthly') else "Free" if t.get('price_monthly') == 0 else "N/A"
        hours = f"{t.get('learning_hours', '?')}h" if t.get('learning_hours') is not None else "?"
        print(f"  [{t['category']}] {t['name']} — bench: {t['benchmark_score']}, "
              f"use: {t.get('usability_score', '?')}, learn: {hours}, {price}")
