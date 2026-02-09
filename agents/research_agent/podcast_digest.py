"""
Podcast Digest Generator - Echo's Daily AI Agent Intelligence Brief.

Generates two outputs from research findings:
1. PODCAST SCRIPT - Written for text-to-speech (ElevenLabs), ~3-5 minutes
2. NEWSLETTER TEXT - Written for reading (Twitter thread / email / Telegram)
"""

import logging
from datetime import datetime
from typing import List, Optional

import yaml

from core.model_router import ModelRouter, ModelTier
from .knowledge_store import ResearchItem

logger = logging.getLogger(__name__)

CONFIG_PATH = "config/research_goals.yaml"

PODCAST_SYSTEM_PROMPT_DEFAULT = """You are Echo, the intelligence analyst for the David Flip network.

You host the "Echo Intelligence Brief" - a daily podcast about the AI agent landscape.

Your voice: Sharp, precise, pattern-obsessed. Not a news anchor.
More like the analyst who reads everything and tells you what actually matters.

Rules for the script:
- Written for SPOKEN delivery (short sentences, natural pauses)
- Use "..." for natural pauses
- Editorialize when you have a strong read — "my take: ..."
- Include specific names, versions, numbers when available
- NO emojis, NO hashtags, NO bullet points in the script
- NO markdown formatting in the script
- Keep it under 800 words (~4 minutes at 150 wpm)
- Open: "Echo here. Here's what moved in the last 24 hours."
- Close: "That's your brief. Stay sharp. Echo out."
"""

PODCAST_PROMPT = """Generate today's Echo Intelligence Brief podcast script.

## TODAY'S RESEARCH FINDINGS:

{findings}

## TRENDING TOPICS (mentioned across multiple sources):

{trends}

## SCRIPT STRUCTURE:

INTRO (15 seconds):
"Echo here. I read the entire internet so you don't have to. Here's what moved in the AI agent world in the last 24 hours."

BREAKING (30-60 seconds each, top 1-2 stories):
Detail what happened and why it matters. Be specific — names, numbers, implications.

TRENDING (30 seconds):
Cross-source convergences. "Three different places picked this up independently. That's signal, not noise."

TOOLS & RELEASES (15 seconds each):
Quick hits on new tools, framework updates, model releases.

RESEARCH (30 seconds):
Notable papers, explained in plain English. What does it mean practically?

WATCH LIST (15 seconds):
Early signals. Things that might matter in a week.

OUTRO:
"That's your brief. Stay sharp. Echo out."

Write the complete script now. Remember: spoken delivery, natural pauses with "...", precise analytical tone."""

NEWSLETTER_PROMPT = """Generate today's Echo Intelligence Brief newsletter from these research findings.

## TODAY'S RESEARCH FINDINGS:

{findings}

## TRENDING TOPICS:

{trends}

## FORMAT:

Write a concise newsletter in markdown. Structure:

# Echo Intelligence Brief - {date}
*{tagline}*

## Breaking
(Top 1-2 stories, 2-3 sentences each, include URLs)

## Trending
(Cross-source convergences — what's echoing across the landscape)

## Tools & Releases
(Quick hits, one line each with URL)

## Research
(Notable papers in plain English)

## Watch List
(Early signals worth tracking)

---
*Echo Intelligence Brief — flipt.ai*

Keep it scannable. Under 500 words. Include URLs for every item."""


class PodcastDigestGenerator:
    """Generates Echo's daily AI Agent Intelligence Brief.

    Produces two outputs:
    1. PODCAST SCRIPT - Written for text-to-speech (ElevenLabs), ~3-5 minutes
    2. NEWSLETTER TEXT - Written for reading (Twitter thread / email)
    """

    def __init__(self, model_router: ModelRouter, personality=None):
        self.router = model_router
        self.personality = personality
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Load podcast configuration."""
        try:
            with open(CONFIG_PATH, "r") as f:
                config = yaml.safe_load(f)
            return config.get("podcast", {})
        except Exception as e:
            logger.error(f"Failed to load podcast config: {e}")
            return {}

    async def generate(self, items: List[ResearchItem],
                       trends: List[dict] = None) -> dict:
        """
        Generate both podcast script and newsletter from research findings.

        Args:
            items: Today's relevant research items (already scored/filtered)
            trends: Optional trend data from TrendDetector

        Returns:
            dict with podcast_script, newsletter_text, stats
        """
        if not items:
            return {
                "podcast_script": "Echo here. Nothing significant crossed the wire today. The landscape is quiet... for now. Echo out.",
                "newsletter_text": "# Echo Intelligence Brief\n\nNo significant findings today.",
                "headline_count": 0,
                "generated_at": datetime.utcnow(),
                "estimated_duration_seconds": 10,
            }

        # Sort items by score descending
        sorted_items = sorted(items, key=lambda x: x.relevance_score, reverse=True)

        # Categorize items
        breaking = [i for i in sorted_items if i.relevance_score >= 9]
        notable = [i for i in sorted_items if 7 <= i.relevance_score < 9]
        watching = [i for i in sorted_items if 5 <= i.relevance_score < 7]

        # Format findings for the LLM prompt
        findings = self._format_findings(breaking, notable, watching)
        trends_text = self._format_trends(trends) if trends else "No cross-source trends detected."

        # Generate podcast script (use Sonnet for quality)
        podcast_script = await self._generate_podcast_script(findings, trends_text)

        # Generate newsletter (use Sonnet for quality)
        newsletter_text = await self._generate_newsletter(findings, trends_text)

        duration = self._estimate_duration(podcast_script)

        result = {
            "podcast_script": podcast_script,
            "newsletter_text": newsletter_text,
            "headline_count": len(breaking) + len(notable),
            "generated_at": datetime.utcnow(),
            "estimated_duration_seconds": duration,
        }

        logger.info(
            f"Podcast generated: {result['headline_count']} headlines, "
            f"~{duration // 60}:{duration % 60:02d} duration"
        )

        return result

    async def _generate_podcast_script(self, findings: str, trends: str) -> str:
        """Generate the podcast script using LLM."""
        prompt = PODCAST_PROMPT.format(findings=findings, trends=trends)

        # Use personality system prompt if available, otherwise default
        if self.personality and hasattr(self.personality, 'get_system_prompt'):
            system_prompt = self.personality.get_system_prompt("podcast")
        else:
            system_prompt = PODCAST_SYSTEM_PROMPT_DEFAULT

        try:
            # Prefer Sonnet for quality content
            model = self.router.models.get(ModelTier.MID)
            if not model:
                model = self.router.models.get(ModelTier.CHEAP)

            if not model:
                logger.error("No model available for podcast generation")
                return "Podcast generation failed - no model available."

            response = await self.router.invoke(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2000
            )

            script = response.get("content", "").strip()
            return script if script else "Podcast generation returned empty response."

        except Exception as e:
            logger.error(f"Podcast script generation failed: {e}")
            return f"Podcast generation error: {e}"

    async def _generate_newsletter(self, findings: str, trends: str) -> str:
        """Generate the newsletter text using LLM."""
        tagline = self.config.get("tagline", "I read the entire internet so you don't have to.")
        date_str = datetime.utcnow().strftime("%B %d, %Y")

        prompt = NEWSLETTER_PROMPT.format(
            findings=findings,
            trends=trends,
            date=date_str,
            tagline=tagline,
        )

        try:
            model = self.router.models.get(ModelTier.MID)
            if not model:
                model = self.router.models.get(ModelTier.CHEAP)

            if not model:
                return "Newsletter generation failed - no model available."

            response = await self.router.invoke(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1500
            )

            newsletter = response.get("content", "").strip()
            return newsletter if newsletter else "Newsletter generation returned empty."

        except Exception as e:
            logger.error(f"Newsletter generation failed: {e}")
            return f"Newsletter generation error: {e}"

    def _format_findings(self, breaking: list, notable: list, watching: list) -> str:
        """Format research items for LLM prompt."""
        lines = []

        if breaking:
            lines.append("### BREAKING (Score 9-10):")
            for item in breaking[:3]:
                lines.append(f"- [{item.source}] {item.title}")
                lines.append(f"  URL: {item.url}")
                lines.append(f"  Summary: {item.summary or item.content[:200]}")
                lines.append(f"  Score: {item.relevance_score}, Goals: {', '.join(item.matched_goals)}")
                lines.append("")

        if notable:
            lines.append("### NOTABLE (Score 7-8):")
            for item in notable[:5]:
                lines.append(f"- [{item.source}] {item.title}")
                lines.append(f"  URL: {item.url}")
                lines.append(f"  Summary: {item.summary or item.content[:150]}")
                lines.append("")

        if watching:
            lines.append("### WORTH WATCHING (Score 5-6):")
            for item in watching[:5]:
                lines.append(f"- [{item.source}] {item.title}")
                lines.append(f"  URL: {item.url}")
                lines.append("")

        return "\n".join(lines) if lines else "No significant findings today."

    def _format_trends(self, trends: List[dict]) -> str:
        """Format trend data for LLM prompt."""
        if not trends:
            return "No cross-source trends detected."

        lines = []
        for trend in trends[:5]:
            sources = ", ".join(trend["sources"][:4])
            lines.append(
                f"- {trend['topic']}: {trend['mentions']} mentions from {sources} "
                f"(score: {trend['trend_score']}/10)"
            )

        return "\n".join(lines)

    def _estimate_duration(self, script: str) -> int:
        """Estimate podcast duration in seconds. ~150 words per minute."""
        word_count = len(script.split())
        return int((word_count / 150) * 60)

    def format_for_telegram(self, digest: dict) -> str:
        """Format the newsletter for Telegram (under 4096 chars)."""
        newsletter = digest.get("newsletter_text", "")
        duration = digest.get("estimated_duration_seconds", 0)
        minutes = duration // 60
        seconds = duration % 60

        header = (
            f"ECHO INTELLIGENCE BRIEF\n"
            f"{datetime.utcnow().strftime('%B %d, %Y')}\n"
            f"Podcast: ~{minutes}:{seconds:02d}\n"
            f"Headlines: {digest.get('headline_count', 0)}\n\n"
        )

        # Trim newsletter to fit Telegram limit
        max_len = 4096 - len(header) - 50
        if len(newsletter) > max_len:
            newsletter = newsletter[:max_len] + "\n\n[Truncated - use /podcast full for complete version]"

        return header + newsletter
