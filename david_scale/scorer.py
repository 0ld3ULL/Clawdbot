"""
David Scale — Scoring Engine.

Six-pillar composite score:
  Industry (10%) + Influencer (25%) + Customer (25%) +
  Usability (15%) + Value (15%) + Momentum (10%) = David Score (0–10)

- Industry: what the STATS tell us (benchmarks, leaderboards)
- Influencer: what influencers in the industry are saying (all referenced)
- Customer: what actual users are saying (forums, Discord, Reddit)
- Usability: how intuitive, how many hours to get good results
- Value: cost vs output — is it worth the money?
- Momentum: trending volume across all sources

"The most powerful car isn't always the best to drive."
"""

import logging
from datetime import datetime
from typing import Optional

from david_scale.models import DavidScaleDB, CATEGORIES
from david_scale.sentiment import SentimentPipeline

logger = logging.getLogger(__name__)

# Scoring weights — real voices + practical reality
WEIGHT_INDUSTRY = 0.10     # Published benchmarks and leaderboards
WEIGHT_INFLUENCER = 0.25   # YouTube/TikTok reviews, blogs (referenced)
WEIGHT_CUSTOMER = 0.25     # Forums, Reddit, HN, Discord (actual users)
WEIGHT_USABILITY = 0.15    # How intuitive, time to value
WEIGHT_VALUE = 0.15        # Cost efficiency — output per dollar
WEIGHT_MOMENTUM = 0.10     # Trending mentions


class DavidScaleScorer:
    """Computes weekly David Scale scores for all tools."""

    def __init__(self, db: Optional[DavidScaleDB] = None,
                 sentiment: Optional[SentimentPipeline] = None):
        self.db = db or DavidScaleDB()
        self.sentiment = sentiment

    def _compute_momentum(self, tool_id: int) -> float:
        """Compute momentum score based on mention trends.

        Compares this week's mentions to last week's.
        Returns 0–10 scale.
        """
        this_week = self.db.get_mentions_count(tool_id, days=7)
        last_week = self.db.get_mentions_count(tool_id, days=14) - this_week

        if last_week <= 0 and this_week <= 0:
            return 5.0

        if last_week <= 0:
            return min(10, 5 + this_week * 0.5)

        ratio = this_week / max(last_week, 1)

        if ratio >= 2.0:
            return 10.0
        elif ratio >= 1.5:
            return 8.0
        elif ratio >= 1.1:
            return 7.0
        elif ratio >= 0.9:
            return 5.0
        elif ratio >= 0.5:
            return 3.0
        else:
            return 1.0

    def _compute_value(self, david_quality: float, price_monthly: float,
                       category: str) -> float:
        """Compute value score — quality per dollar.

        Free tools with good quality get 10.
        Expensive tools with similar quality to cheaper ones score lower.
        Normalized within category context.
        """
        if price_monthly is None:
            return 5.0  # Unknown pricing = neutral

        if price_monthly == 0:
            # Free + good quality = best value
            return min(10, david_quality + 1)

        # Value = quality / log(price + 1) * scaling factor
        # This means: $10/mo for a 8.0 tool = great value
        #             $500/mo for a 7.0 tool = terrible value
        import math
        raw_value = david_quality / math.log2(price_monthly + 2)

        # Normalize to 0–10 range
        # Typical good value: 8.0 quality / log2(22) = 8/4.46 = 1.79
        # Typical bad value: 7.0 quality / log2(502) = 7/8.97 = 0.78
        normalized = raw_value * 4  # Scale up
        return round(max(0, min(10, normalized)), 2)

    def score_tool(self, tool: dict) -> dict:
        """Score a single tool with all six pillars.

        Returns dict with all score components and composite david_score.
        """
        tool_id = tool["id"]

        # Industry: benchmark score (manually entered, enriched from leaderboards)
        industry = tool.get("benchmark_score", 5.0) or 5.0

        # Usability: from tool data (manually seeded, later from sentiment)
        usability = tool.get("usability_score", 5.0) or 5.0

        # Customer and Influencer sentiment from pipeline
        if self.sentiment:
            customer = self.sentiment.compute_customer_sentiment(tool_id)
            influencer = self.sentiment.compute_influencer_score(tool_id)
        else:
            mentions = self.db.get_mentions(tool_id, days=7, limit=500)
            if mentions:
                pos = sum(1 for m in mentions if m["sentiment"] == "positive")
                neg = sum(1 for m in mentions if m["sentiment"] == "negative")
                total = len(mentions)
                customer = ((pos - neg) / total) * 5 + 5 if total > 0 else 5.0
                customer = round(max(0, min(10, customer)), 2)
            else:
                customer = 5.0

            reviews = self.db.get_influencer_reviews(tool_id, days=7, limit=100)
            if reviews:
                pos = sum(1 for r in reviews if r["sentiment"] == "positive")
                neg = sum(1 for r in reviews if r["sentiment"] == "negative")
                total = len(reviews)
                influencer = ((pos - neg) / total) * 5 + 5 if total > 0 else 5.0
                influencer = round(max(0, min(10, influencer)), 2)
            else:
                influencer = 5.0

        momentum = self._compute_momentum(tool_id)
        mentions_count = self.db.get_mentions_count(tool_id, days=7)

        # Quality score (pre-value) for value calculation
        quality_pre = (
            industry * 0.15 + influencer * 0.35 + customer * 0.35 +
            usability * 0.15
        )

        # Value: quality vs cost
        price = tool.get("price_monthly")
        value = self._compute_value(quality_pre, price, tool.get("category", ""))

        # Composite David Score
        david_score = round(
            industry * WEIGHT_INDUSTRY +
            influencer * WEIGHT_INFLUENCER +
            customer * WEIGHT_CUSTOMER +
            usability * WEIGHT_USABILITY +
            value * WEIGHT_VALUE +
            momentum * WEIGHT_MOMENTUM,
            2
        )

        return {
            "tool_id": tool_id,
            "industry": round(industry, 2),
            "influencer": round(influencer, 2),
            "customer": round(customer, 2),
            "usability": round(usability, 2),
            "value": round(value, 2),
            "momentum": round(momentum, 2),
            "david_score": david_score,
            "mentions_count": mentions_count,
            "price_monthly": price,
            "price_notes": tool.get("price_notes", ""),
            "learning_hours": tool.get("learning_hours"),
        }

    def score_all(self, week_date: Optional[str] = None) -> list[dict]:
        """Score all active tools and save to database.

        Returns list of score results with ranking changes.
        """
        if not week_date:
            week_date = datetime.utcnow().strftime("%Y-%m-%d")

        tools = self.db.get_tools()
        if not tools:
            logger.warning("No tools to score")
            return []

        prev_scores = self.db.get_previous_scores(week_date)
        prev_ranks = {}
        for ps in prev_scores:
            prev_ranks[(ps["tool_id"], ps["category"])] = ps.get("rank_in_category", 0)

        results = []
        for tool in tools:
            score = self.score_tool(tool)
            score["name"] = tool["name"]
            score["slug"] = tool["slug"]
            score["category"] = tool["category"]
            score["description"] = tool.get("description", "")
            score["website"] = tool.get("website", "")
            results.append(score)

        # Calculate ranks within each category
        for cat_slug in CATEGORIES:
            cat_tools = [r for r in results if r["category"] == cat_slug]
            cat_tools.sort(key=lambda x: x["david_score"], reverse=True)

            for rank, tool_score in enumerate(cat_tools, 1):
                tool_score["rank_in_category"] = rank

                prev_rank = prev_ranks.get(
                    (tool_score["tool_id"], cat_slug), 0
                )
                if prev_rank > 0:
                    tool_score["rank_change"] = prev_rank - rank
                else:
                    tool_score["rank_change"] = 0
                    tool_score["is_new"] = True

        # Save scores to database
        for r in results:
            self.db.save_score(
                tool_id=r["tool_id"],
                week_date=week_date,
                industry=r["industry"],
                influencer=r["influencer"],
                customer=r["customer"],
                usability=r["usability"],
                value=r["value"],
                momentum=r["momentum"],
                david_score=r["david_score"],
                rank_in_category=r["rank_in_category"],
                mentions_count=r["mentions_count"],
            )

        logger.info(f"Scored {len(results)} tools for week {week_date}")
        return results

    def detect_ranking_changes(self, results: list[dict],
                                min_change: int = 2) -> list[dict]:
        """Find significant ranking changes for tweet generation."""
        changes = []

        for r in results:
            if r["rank_in_category"] == 1 and r.get("rank_change", 0) > 0:
                changes.append({
                    "type": "new_number_one",
                    "tool": r["name"],
                    "slug": r["slug"],
                    "category": CATEGORIES.get(r["category"], r["category"]),
                    "score": r["david_score"],
                    "change": r["rank_change"],
                })
            elif r.get("rank_change", 0) >= min_change:
                changes.append({
                    "type": "big_mover",
                    "tool": r["name"],
                    "slug": r["slug"],
                    "category": CATEGORIES.get(r["category"], r["category"]),
                    "score": r["david_score"],
                    "change": r["rank_change"],
                })
            elif r.get("is_new"):
                changes.append({
                    "type": "new_entry",
                    "tool": r["name"],
                    "slug": r["slug"],
                    "category": CATEGORIES.get(r["category"], r["category"]),
                    "score": r["david_score"],
                })

        changes.sort(key=lambda c: (
            0 if c["type"] == "new_number_one" else 1,
            -c.get("change", 0)
        ))

        logger.info(f"Detected {len(changes)} ranking changes")
        return changes
