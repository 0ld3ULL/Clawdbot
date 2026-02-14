"""
David Scale — Sentiment Pipeline.

Two separate sentiment streams:
1. Customer Sentiment — from forums, Reddit, HN, Discord (the actual users)
2. Influencer Score — from YouTube/TikTok transcripts, blog reviews (referenced)

Reads recent items from Echo's research.db, extracts tool mentions,
classifies sentiment via Haiku, stores in david_scale.db.

Cost: ~$0.02–0.05 per scoring run.
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from core.model_router import ModelRouter, ModelTier
from agents.research_agent.trend_detector import KNOWN_ENTITIES
from david_scale.models import DavidScaleDB

logger = logging.getLogger(__name__)

# Map known entities to David Scale tool names
# Only include actual tools (not concepts like RAG, Fine-tuning)
ENTITY_TO_TOOL = {
    "ChatGPT": "ChatGPT", "GPT": "ChatGPT", "GPT-4": "ChatGPT", "GPT-5": "ChatGPT",
    "Claude": "Claude", "Claude Code": "Claude Code",
    "Gemini": "Gemini",
    "Llama": "Llama", "Mistral": "Mistral", "DeepSeek": "DeepSeek", "Qwen": "Qwen",
    "Cursor": "Cursor", "Devin": "Devin", "Aider": "Aider",
    "Copilot": "GitHub Copilot", "Windsurf": "Windsurf", "Codex": "Codex",
    "LangChain": "LangChain", "CrewAI": "CrewAI", "AutoGPT": "AutoGen",
    "Midjourney": "Midjourney",
    "Runway": "Runway",
    "Perplexity": "Perplexity",
    "Replit": "Replit",
}

# Sources that count as "customer sentiment" (forums, communities)
CUSTOMER_SOURCES = {"reddit", "hackernews", "discord", "github", "rss"}

# Sources that count as "influencer" (video reviews, blogs)
INFLUENCER_SOURCES = {"youtube", "tiktok", "transcript"}

SENTIMENT_PROMPT = """Classify the sentiment toward "{tool_name}" in this text.

Text: {text}

Is the author's opinion of {tool_name} positive, negative, or neutral?
Consider: Are they praising it, complaining about it, or just mentioning it?

Return ONLY one word: positive, negative, or neutral"""

INFLUENCER_REVIEW_PROMPT = """Analyze this video/blog transcript about AI tools.

Transcript excerpt: {text}

For the tool "{tool_name}":
1. What is the reviewer's overall sentiment? (positive/negative/neutral)
2. Summarize their opinion in 1-2 sentences.
3. How deeply did they actually USE the tool? Rate 1-10:
   1-3 = surface level (just read specs, repeated marketing claims, no hands-on)
   4-6 = moderate (tried it briefly, showed a few examples)
   7-10 = deep usage (extensive testing, real projects, detailed comparisons)

Return ONLY valid JSON:
{{"sentiment": "positive", "summary": "The reviewer praised X for...", "experience_depth": 7}}"""


class SentimentPipeline:
    """Extract customer + influencer sentiment for David Scale tools."""

    def __init__(self, model_router: ModelRouter,
                 david_db: Optional[DavidScaleDB] = None,
                 research_db_path: str = "data/research.db"):
        self.router = model_router
        self.db = david_db or DavidScaleDB()
        self.research_db_path = Path(research_db_path)

    def _connect_research(self) -> Optional[sqlite3.Connection]:
        """Connect to Echo's research.db."""
        if not self.research_db_path.exists():
            logger.warning(f"research.db not found at {self.research_db_path}")
            return None
        conn = sqlite3.connect(str(self.research_db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _get_recent_items(self, days: int = 7) -> list[dict]:
        """Get recent research items from Echo's database."""
        conn = self._connect_research()
        if not conn:
            return []

        try:
            cutoff = (datetime.utcnow() - timedelta(days=days)).isoformat()
            rows = conn.execute(
                """SELECT id, source, url, title, content, summary, scraped_at
                   FROM research_items
                   WHERE scraped_at >= ?
                   ORDER BY scraped_at DESC""",
                (cutoff,)
            ).fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"Failed to query research.db: {e}")
            return []
        finally:
            conn.close()

    def _extract_tool_mentions(self, text: str) -> set[str]:
        """Find which David Scale tools are mentioned in text.

        Uses the same entity extraction logic as TrendDetector.
        Returns set of canonical tool names.
        """
        mentioned = set()
        text_lower = text.lower()

        for pattern, canonical in KNOWN_ENTITIES.items():
            if pattern in text_lower:
                tool_name = ENTITY_TO_TOOL.get(canonical)
                if tool_name:
                    mentioned.add(tool_name)

        return mentioned

    async def _classify_sentiment(self, tool_name: str,
                                   text: str) -> str:
        """Use Haiku to classify sentiment. Returns positive/negative/neutral."""
        model = self.router.models.get(ModelTier.CHEAP)
        if not model:
            return "neutral"

        prompt = SENTIMENT_PROMPT.format(
            tool_name=tool_name,
            text=text[:500]
        )

        try:
            response = await self.router.invoke(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=10
            )
            result = response.get("content", "").strip().lower()
            if result in ("positive", "negative", "neutral"):
                return result
            if "positive" in result:
                return "positive"
            if "negative" in result:
                return "negative"
            return "neutral"
        except Exception as e:
            logger.error(f"Sentiment classification failed: {e}")
            return "neutral"

    async def _analyze_influencer_review(self, tool_name: str,
                                          text: str) -> dict:
        """Extract influencer opinion with summary. Returns {sentiment, summary}."""
        model = self.router.models.get(ModelTier.CHEAP)
        if not model:
            return {"sentiment": "neutral", "summary": ""}

        prompt = INFLUENCER_REVIEW_PROMPT.format(
            tool_name=tool_name,
            text=text[:1500]
        )

        try:
            response = await self.router.invoke(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150
            )
            content = response.get("content", "").strip()

            # Parse JSON response
            import json
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            result = json.loads(content.strip())
            sentiment = result.get("sentiment", "neutral").lower()
            if sentiment not in ("positive", "negative", "neutral"):
                sentiment = "neutral"

            # Parse experience depth (1-10, default 5)
            exp = result.get("experience_depth", 5)
            try:
                exp = max(1, min(10, float(exp)))
            except (ValueError, TypeError):
                exp = 5.0

            return {
                "sentiment": sentiment,
                "summary": result.get("summary", ""),
                "experience_depth": exp,
            }
        except Exception as e:
            logger.error(f"Influencer review analysis failed: {e}")
            return {"sentiment": "neutral", "summary": ""}

    def _extract_influencer_name(self, item: dict) -> str:
        """Try to extract the influencer/channel name from a research item."""
        title = item.get("title", "")
        url = item.get("url", "")

        # YouTube: often has channel name in title or URL
        # For now, use the title as a rough proxy
        # Future: use YouTube API to get channel name
        if "youtube.com" in url or "youtu.be" in url:
            # Extract from title — often "Topic by ChannelName" or just the channel
            return title.split(" - ")[-1].strip() if " - " in title else "Unknown Creator"
        if "tiktok.com" in url:
            # TikTok URLs often have @username
            parts = url.split("@")
            if len(parts) > 1:
                username = parts[1].split("/")[0].split("?")[0]
                return f"@{username}"
        return item.get("source", "Unknown")

    async def run(self, days: int = 7) -> dict:
        """Run the full sentiment pipeline.

        Processes both customer sentiment (forums/Reddit/HN/Discord)
        and influencer reviews (YouTube/TikTok transcripts).

        Returns stats dict.
        """
        stats = {
            "items_scanned": 0,
            "customer_mentions": 0,
            "influencer_reviews": 0,
            "api_calls": 0,
        }

        tools = {t["name"]: t for t in self.db.get_tools()}
        if not tools:
            logger.warning("No tools in registry. Run seed first.")
            return stats

        items = self._get_recent_items(days=days)
        stats["items_scanned"] = len(items)
        logger.info(f"Scanning {len(items)} research items for tool mentions")

        for item in items:
            text = f"{item.get('title', '')} {item.get('content', '')} {item.get('summary', '')}"
            mentioned_tools = self._extract_tool_mentions(text)
            source = item.get("source", "unknown").lower()

            for tool_name in mentioned_tools:
                tool = tools.get(tool_name)
                if not tool:
                    continue

                if source in INFLUENCER_SOURCES:
                    # Influencer review — deeper analysis with summary + experience
                    review = await self._analyze_influencer_review(tool_name, text)
                    stats["api_calls"] += 1
                    stats["influencer_reviews"] += 1

                    influencer_name = self._extract_influencer_name(item)
                    exp_depth = review.get("experience_depth", 5.0)

                    self.db.save_influencer_review(
                        tool_id=tool["id"],
                        influencer_name=influencer_name,
                        platform=source,
                        video_url=item.get("url", ""),
                        sentiment=review["sentiment"],
                        summary=review["summary"],
                        snippet=text[:300].strip(),
                        experience_depth=exp_depth,
                        scraped_at=datetime.fromisoformat(item["scraped_at"])
                        if item.get("scraped_at") else None,
                    )

                    # Update influencer's experience score
                    influencer_id = self.db.get_or_create_influencer(
                        influencer_name, source, item.get("url", "")
                    )
                    self.db.update_influencer_experience(
                        influencer_id, exp_depth
                    )
                else:
                    # Customer sentiment — quick classification
                    sentiment = await self._classify_sentiment(tool_name, text)
                    stats["api_calls"] += 1
                    stats["customer_mentions"] += 1

                    self.db.save_mention(
                        tool_id=tool["id"],
                        source=source,
                        source_url=item.get("url", ""),
                        sentiment=sentiment,
                        snippet=text[:300].strip(),
                        scraped_at=datetime.fromisoformat(item["scraped_at"])
                        if item.get("scraped_at") else None,
                    )

        logger.info(
            f"Sentiment pipeline complete: {stats['items_scanned']} items, "
            f"{stats['customer_mentions']} customer mentions, "
            f"{stats['influencer_reviews']} influencer reviews, "
            f"{stats['api_calls']} API calls"
        )
        return stats

    def compute_customer_sentiment(self, tool_id: int,
                                    days: int = 7) -> float:
        """Compute customer sentiment score from forum/community mentions.

        Formula: (positive - negative) / total * 5 + 5 → range 0–10
        """
        mentions = self.db.get_mentions(tool_id, days=days, limit=500)
        if not mentions:
            return 5.0

        positive = sum(1 for m in mentions if m["sentiment"] == "positive")
        negative = sum(1 for m in mentions if m["sentiment"] == "negative")
        total = len(mentions)

        if total == 0:
            return 5.0

        score = ((positive - negative) / total) * 5 + 5
        return round(max(0, min(10, score)), 2)

    def compute_influencer_score(self, tool_id: int,
                                  days: int = 7) -> float:
        """Compute credibility-weighted influencer score.

        Not all influencer opinions are equal. Each review is weighted
        by the influencer's credibility score (accuracy + experience).

        An influencer who deeply used the tool AND has a track record of
        accurate calls carries more weight than a surface-level hype review.

        Formula:
          weighted_sum = sum(credibility * sentiment_value) for each review
          weighted_total = sum(credibility) for each review
          score = (weighted_sum / weighted_total) * 5 + 5 → 0-10
        """
        reviews = self.db.get_influencer_reviews(tool_id, days=days, limit=100)
        if not reviews:
            return 5.0

        weighted_sum = 0.0
        weighted_total = 0.0

        for r in reviews:
            # Credibility from the influencer profile (default 5.0 for unknown)
            credibility = r.get("credibility_score") or 5.0
            # Also factor in this specific review's experience depth
            review_depth = r.get("experience_depth") or 5.0
            # Combined weight: influencer credibility + this review's depth
            weight = (credibility * 0.6 + review_depth * 0.4)

            sentiment = r.get("sentiment", "neutral")
            if sentiment == "positive":
                value = 1.0
            elif sentiment == "negative":
                value = -1.0
            else:
                value = 0.0

            weighted_sum += weight * value
            weighted_total += weight

        if weighted_total == 0:
            return 5.0

        score = (weighted_sum / weighted_total) * 5 + 5
        return round(max(0, min(10, score)), 2)

    def verify_influencer_accuracy(self, tool_id: int,
                                     customer_sentiment: float,
                                     days: int = 7):
        """After scoring, check if influencers' calls matched reality.

        Compare each influencer's sentiment against actual customer sentiment:
        - Positive call + customer > 6.0 = correct
        - Negative call + customer < 4.0 = correct
        - Neutral call + customer 4.0-6.0 = correct
        """
        reviews = self.db.get_influencer_reviews(tool_id, days=days)
        for r in reviews:
            if not r.get("influencer_id"):
                continue

            sentiment = r.get("sentiment", "neutral")
            if sentiment == "positive":
                correct = customer_sentiment > 6.0
            elif sentiment == "negative":
                correct = customer_sentiment < 4.0
            else:
                correct = 4.0 <= customer_sentiment <= 6.0

            self.db.update_influencer_accuracy(
                r["influencer_id"], correct
            )
