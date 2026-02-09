"""
Trend Detector - Detects cross-source signal.

When multiple independent sources mention the same tool/concept/event
within a time window, that's a TREND signal worth amplifying.
"""

import logging
import re
import string
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Set, Tuple

from .knowledge_store import ResearchItem

logger = logging.getLogger(__name__)

# Known entities mapped to canonical forms
KNOWN_ENTITIES = {
    # Anthropic
    "claude": "Claude", "claude code": "Claude Code", "anthropic": "Anthropic",
    "sonnet": "Sonnet", "opus": "Opus", "haiku": "Haiku",
    # Protocols & standards
    "mcp": "MCP", "model context protocol": "MCP",
    "a2a": "A2A", "agent-to-agent": "A2A", "agent to agent": "A2A",
    # OpenAI
    "gpt": "GPT", "openai": "OpenAI", "chatgpt": "ChatGPT",
    "gpt-4": "GPT-4", "gpt-5": "GPT-5", "codex": "Codex",
    # Google
    "gemini": "Gemini", "deepmind": "DeepMind", "google ai": "Google AI",
    # Coding tools
    "cursor": "Cursor", "devin": "Devin", "aider": "Aider",
    "copilot": "Copilot", "github copilot": "Copilot",
    "windsurf": "Windsurf", "cline": "Cline", "bolt": "Bolt",
    "replit": "Replit", "replit agent": "Replit Agent",
    # Frameworks
    "langchain": "LangChain", "langgraph": "LangGraph",
    "crewai": "CrewAI", "autogpt": "AutoGPT", "auto-gpt": "AutoGPT",
    "openhands": "OpenHands", "opendevin": "OpenHands",
    "swe-agent": "SWE-Agent",
    # Concepts
    "rag": "RAG", "retrieval augmented": "RAG",
    "fine-tuning": "Fine-tuning", "fine tuning": "Fine-tuning",
    "computer use": "Computer Use",
    "voice assistant": "Voice Assistant",
    "multi-agent": "Multi-Agent",
    # Surveillance / David content
    "cbdc": "CBDC", "digital id": "Digital ID",
    "social credit": "Social Credit",
    "facial recognition": "Facial Recognition",
    # Models
    "llama": "Llama", "mistral": "Mistral",
    "qwen": "Qwen", "deepseek": "DeepSeek",
}

# Common stop words to remove from entity extraction
STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "used", "to", "of", "in", "for", "on", "with", "at", "by", "from",
    "as", "into", "through", "during", "before", "after", "above", "below",
    "between", "out", "off", "over", "under", "again", "further", "then",
    "once", "here", "there", "when", "where", "why", "how", "all", "each",
    "every", "both", "few", "more", "most", "other", "some", "such", "no",
    "nor", "not", "only", "own", "same", "so", "than", "too", "very",
    "just", "don", "now", "and", "but", "or", "if", "while", "that",
    "this", "what", "which", "who", "whom", "these", "those", "am",
    "new", "about", "up", "its", "my", "your", "we", "they", "it",
    "you", "i", "he", "she", "his", "her", "our", "their",
}


class TrendDetector:
    """Detects trending topics across multiple research sources.

    When 2+ independent sources mention the same tool/concept/event
    within 24 hours, that's a TREND signal. Boost those items' scores.
    """

    def __init__(self, similarity_threshold: float = 0.3):
        self.similarity_threshold = similarity_threshold

    def detect_trends(self, items: List[ResearchItem],
                      time_window_hours: int = 24) -> List[dict]:
        """
        Detect trending topics from a list of research items.

        Returns list of trend dicts sorted by mention count.
        """
        if not items:
            return []

        cutoff = datetime.utcnow() - timedelta(hours=time_window_hours)

        # Filter to recent items only
        recent = [
            i for i in items
            if i.relevance_score > 0 and (
                not i.scraped_at or i.scraped_at.replace(tzinfo=None) > cutoff
            )
        ]

        if not recent:
            return []

        # Extract entities from each item
        item_entities: List[Tuple[ResearchItem, Set[str]]] = []
        for item in recent:
            entities = self._extract_entities(f"{item.title} {item.content[:300]}")
            item_entities.append((item, entities))

        # Group items by shared entities
        # Key = canonical entity, Value = list of (item, all_entities) tuples
        entity_groups: Dict[str, List[ResearchItem]] = defaultdict(list)

        for item, entities in item_entities:
            for entity in entities:
                entity_groups[entity].append(item)

        # Find trends: entities mentioned by 2+ different sources
        trends = []
        seen_topics = set()

        for entity, group_items in sorted(entity_groups.items(),
                                           key=lambda x: len(x[1]), reverse=True):
            # Get unique sources
            sources = list(set(i.source for i in group_items))

            if len(sources) < 2:
                continue

            # Skip if this is basically the same trend we already found
            if entity in seen_topics:
                continue
            seen_topics.add(entity)

            # Calculate trend score (boost based on source diversity)
            avg_score = sum(i.relevance_score for i in group_items) / len(group_items)
            trend_score = min(10, avg_score + (len(sources) - 1) * 1.5)

            first_seen = min(
                (i.published_at or i.scraped_at or datetime.utcnow())
                for i in group_items
            )
            # Normalize to naive datetime
            if hasattr(first_seen, 'tzinfo') and first_seen.tzinfo:
                first_seen = first_seen.replace(tzinfo=None)

            trends.append({
                "topic": entity,
                "mentions": len(group_items),
                "sources": sources,
                "items": group_items,
                "trend_score": round(trend_score, 1),
                "first_seen": first_seen,
                "summary": f"{entity} mentioned across {len(sources)} sources ({', '.join(sources[:4])})"
            })

        # Sort by source diversity first, then mention count
        trends.sort(key=lambda t: (len(t["sources"]), t["mentions"]), reverse=True)

        logger.info(f"Detected {len(trends)} trends from {len(recent)} items")
        return trends[:20]  # Limit to top 20 trends

    def boost_scores(self, items: List[ResearchItem],
                     trends: List[dict]) -> List[ResearchItem]:
        """
        Boost scores for items that are part of a trend.

        Boost formula: original_score + (num_sources - 1) * 1.5, capped at 10.
        """
        # Build lookup: item id -> trend info
        trending_items = {}
        for trend in trends:
            for item in trend["items"]:
                item_key = id(item)
                if item_key not in trending_items or trend["trend_score"] > trending_items[item_key]["trend_score"]:
                    trending_items[item_key] = trend

        # Apply boosts
        boosted_count = 0
        for item in items:
            trend = trending_items.get(id(item))
            if trend:
                old_score = item.relevance_score
                num_sources = len(trend["sources"])
                boost = (num_sources - 1) * 1.5
                item.relevance_score = min(10, item.relevance_score + boost)

                if not item.summary.startswith("[TRENDING]"):
                    item.summary = f"[TRENDING] {item.summary}"

                # Ensure trending items are at least "high" priority
                if item.priority in ("none", "low", "medium"):
                    item.priority = "high"

                if item.relevance_score != old_score:
                    boosted_count += 1

        if boosted_count:
            logger.info(f"Boosted {boosted_count} items based on {len(trends)} trends")

        return items

    def _extract_entities(self, text: str) -> Set[str]:
        """
        Extract meaningful entities from text.

        Returns set of canonical entity names found in the text.
        """
        entities = set()
        text_lower = text.lower()

        # Check for known entities first (most reliable)
        for pattern, canonical in KNOWN_ENTITIES.items():
            if pattern in text_lower:
                entities.add(canonical)

        # Also extract significant words (2+ chars, not stop words)
        words = re.findall(r'[a-zA-Z][a-zA-Z0-9_.-]+', text)
        for word in words:
            word_lower = word.lower()
            if word_lower not in STOP_WORDS and len(word_lower) > 2:
                # Only include words that look like proper nouns or tech terms
                if word[0].isupper() or "-" in word or "_" in word:
                    entities.add(word)

        return entities

    def _calculate_topic_similarity(self, entities_a: Set[str],
                                     entities_b: Set[str]) -> float:
        """Jaccard similarity between two entity sets."""
        if not entities_a or not entities_b:
            return 0.0
        intersection = len(entities_a & entities_b)
        union = len(entities_a | entities_b)
        return intersection / union if union > 0 else 0.0

    def format_trend_report(self, trends: List[dict]) -> str:
        """Format trends for Telegram digest message."""
        if not trends:
            return "No trends detected in this cycle."

        lines = ["TRENDING TOPICS\n"]

        for i, trend in enumerate(trends[:10], 1):
            sources_str = ", ".join(trend["sources"][:4])
            lines.append(
                f"{i}. {trend['topic']} "
                f"({trend['mentions']} mentions from {len(trend['sources'])} sources)\n"
                f"   Sources: {sources_str}\n"
                f"   Score: {trend['trend_score']}/10"
            )

            # Include top item URL
            if trend["items"]:
                top_item = max(trend["items"], key=lambda x: x.relevance_score)
                lines.append(f"   Top: {top_item.url}")

            lines.append("")

        return "\n".join(lines)
