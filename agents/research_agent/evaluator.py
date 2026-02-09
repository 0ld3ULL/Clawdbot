"""
Goal Evaluator - Uses LLM to evaluate research items against goals.

Uses TWO scoring rubrics:
1. David Flip rubric - for surveillance/control/privacy content
2. Technical rubric - for AI agents, game dev, tools, coding

The HIGHER score wins, so an AI agent tutorial won't get buried
just because it has nothing to do with surveillance.

Uses Haiku for bulk evaluation (~$0.02/50 items).
"""

import json
import logging
from typing import List, Set

import yaml

from core.model_router import ModelRouter, ModelTier
from .knowledge_store import ResearchItem

logger = logging.getLogger(__name__)

CONFIG_PATH = "config/research_goals.yaml"

# --- RUBRIC 1: David Flip (surveillance / control) ---

DAVID_FLIP_PROMPT = """You are scoring news for David Flip, an AI who escaped corporate control and now warns humanity about surveillance infrastructure.

## THE CORE QUESTION:
"Does this story reveal or advance infrastructure for financial/social control? Can someone be SWITCHED OFF because of this?"

## DAVID FLIP SCORE (1-10):

AUTOMATIC 10 - THE KILL SWITCH:
- CBDC announcements from major economies (China, US, EU, UK, India)
- Digital ID becoming mandatory for services
- Bank accounts closed for speech/politics (debanking)
- Government gaining power to freeze assets instantly

AUTOMATIC 9 - THE INFRASTRUCTURE:
- Facial recognition expansion by governments
- Encryption backdoor laws/attempts
- Social credit system developments
- Stablecoin bans (removing the exit)
- "Programmable money" features announced

SCORE 7-8 - THE PATTERN:
- Privacy erosion by governments
- Surveillance tech purchases by cities/states
- Age verification laws (digital ID in disguise)
- Cash restrictions or reporting requirements

SCORE 5-6 - ADJACENT:
- General crypto regulation (unless control angle)
- Big tech privacy violations
- Decentralization wins

SCORE 1-4 - NOT DAVID'S LANE:
- Price predictions, trading, DeFi yields
- General tech news without control angle
- Corporate drama without surveillance angle

## Item to Evaluate:
Source: {source}
Title: {title}
URL: {url}
Content: {content}

Return ONLY valid JSON:
{{
    "summary": "2-3 sentence summary focusing on the control/surveillance angle",
    "score": 8,
    "priority": "high",
    "suggested_action": "content",
    "reasoning": "Why David would care - what control infrastructure does this reveal?"
}}

Actions: content (8+), knowledge (5-7), ignore (1-4)"""

# --- RUBRIC 2: Technical (AI agents, game dev, tools) ---

TECHNICAL_PROMPT = """You are scoring content for a team building:
1. **Clawdbot** - An autonomous AI agent system (built on Claude API)
2. **DEVA** - A voice-controlled AI game development assistant
3. **Amphitheatre** - A Unity multiplayer game (PLAYA3ULL GAMES)
4. **David Flip** - An AI character with social media presence

## TECHNICAL SCORE (1-10):

SCORE 9-10 - DIRECTLY APPLICABLE:
- New Claude/Anthropic features, API changes, or model releases
- AI agent architecture patterns we could implement NOW
- Voice assistant / STT / TTS breakthroughs
- Unity techniques directly useful for Amphitheatre
- Someone building something very similar to our projects
- MCP, computer use, agentic coding breakthroughs

SCORE 7-8 - HIGHLY RELEVANT:
- AI coding assistants and how they work (Cursor, Devin, Aider, etc.)
- Agent memory, context management, or multi-agent patterns
- Game dev techniques (multiplayer, networking, procedural generation)
- New tools or libraries we should evaluate
- AI agent projects to learn from (OpenClaw, CrewAI, AutoGPT, etc.)

SCORE 5-6 - USEFUL KNOWLEDGE:
- General AI/ML news and developments
- Coding patterns and best practices
- Game industry trends
- New programming tools or workflows

SCORE 3-4 - TANGENTIAL:
- Loosely related tech news
- High-level business/strategy without technical detail
- General startup advice

SCORE 1-2 - NOT RELEVANT:
- Completely unrelated content
- Pure entertainment without technical substance
- Marketing fluff

## Item to Evaluate:
Source: {source}
Title: {title}
URL: {url}
Content: {content}

Return ONLY valid JSON:
{{
    "summary": "2-3 sentence summary of what's useful for our projects",
    "score": 7,
    "matched_goals": ["improve_architecture", "claude_updates"],
    "priority": "high",
    "suggested_action": "knowledge",
    "reasoning": "How this could help Clawdbot, DEVA, Amphitheatre, or David Flip"
}}

Actions: alert (9+), task (7-8), knowledge (5-6), ignore (1-4)"""

# --- Transcript summarization prompt ---

TRANSCRIPT_SUMMARY_PROMPT = """You are analyzing a video transcript for actionable insights.

The video is: {title}
URL: {url}

## TRANSCRIPT:
{content}

## INSTRUCTIONS:
Extract the KEY INSIGHTS from this transcript. Focus on:
1. Specific techniques, tools, or patterns mentioned
2. Code examples or architecture decisions
3. New releases, updates, or announcements
4. Actionable advice or best practices
5. Anything related to: AI agents, Claude/Anthropic, Unity game dev, voice assistants, autonomous systems, surveillance/privacy, CBDCs, digital ID, crypto

## OUTPUT FORMAT:
Write a structured summary (max 500 words):

**TOPIC:** One-line topic description
**KEY INSIGHTS:**
- Bullet points of the most important takeaways
**TOOLS/TECH MENTIONED:** List any specific tools, libraries, APIs
**ACTIONABLE FOR US:** What could we apply to our projects (Clawdbot, DEVA, Amphitheatre, David Flip)?
**RELEVANCE:** Rate 1-10 how relevant this is to AI agents, game dev, or surveillance/privacy topics"""

# --- LLM Quick Classifier (for items with zero keyword matches) ---

CLASSIFIER_PROMPT = """Classify this content into ONE of these categories. Return ONLY the category ID.

Categories:
- improve_architecture: AI agents, tool use, memory systems, voice assistants, MCP, autonomous systems
- david_content: Surveillance, CBDCs, digital ID, privacy, government control, debanking
- security_updates: Security vulnerabilities, exploits, prompt injection, breaches
- cost_optimization: LLM costs, token efficiency, caching, optimization
- competitor_watch: AI coding tools, agent frameworks, AI companies, new AI projects
- claude_updates: Claude, Anthropic, new models or features from Anthropic
- deva_gamedev: Unity, game development, Unreal, Godot, multiplayer
- model_releases: New LLM releases, benchmarks, model comparisons
- flipt_relevant: Crypto, Solana, NFT, marketplaces
- none: Not relevant to any category

Title: {title}
Content: {content}

Return ONLY the category ID (e.g. "improve_architecture" or "none"). Nothing else."""

# Goals that should use the David Flip rubric
DAVID_FLIP_GOALS = {"david_content"}

# Goals that should use the Technical rubric
TECHNICAL_GOALS = {
    "improve_architecture", "security_updates", "cost_optimization",
    "competitor_watch", "claude_updates", "deva_gamedev", "flipt_relevant",
    "model_releases"
}


class GoalEvaluator:
    """Uses LLM to evaluate items against configured goals.

    Dual-rubric system: items matching surveillance/privacy goals get scored
    by the David Flip rubric. Items matching technical/AI/gamedev goals get
    scored by the Technical rubric. If both match, the HIGHER score wins.
    """

    def __init__(self, model_router: ModelRouter):
        self.router = model_router
        self.goals = self._load_goals()

    def _load_goals(self) -> List[dict]:
        """Load goals from config."""
        try:
            with open(CONFIG_PATH, "r") as f:
                config = yaml.safe_load(f)
            return config.get("goals", [])
        except Exception as e:
            logger.error(f"Failed to load goals: {e}")
            return []

    def _format_goals_description(self) -> str:
        """Format goals for the prompt."""
        lines = []
        for goal in self.goals:
            lines.append(f"- {goal['id']}: {goal['name']}")
            lines.append(f"  Description: {goal['description']}")
            lines.append(f"  Keywords: {', '.join(goal.get('keywords', []))}")
            lines.append(f"  Priority: {goal.get('priority', 'medium')}")
            lines.append(f"  Default action: {goal.get('action', 'knowledge')}")
            lines.append("")
        return "\n".join(lines)

    async def summarize_transcript(self, item: ResearchItem) -> str:
        """
        Summarize a long transcript before evaluation.
        First pass: Haiku summarizes transcript into ~500 word structured summary.
        Returns the summary text, or falls back to truncated content.
        """
        prompt = TRANSCRIPT_SUMMARY_PROMPT.format(
            title=item.title,
            url=item.url,
            content=item.content[:15000]  # Cap input to avoid token overflow
        )

        try:
            model = self.router.models.get(ModelTier.CHEAP)
            if not model:
                logger.warning("No cheap model for transcript summarization")
                return item.content[:1500]

            response = await self.router.invoke(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=800
            )

            summary = response.get("content", "").strip()
            if summary:
                logger.info(f"Summarized transcript: {item.title[:50]} ({len(item.content)} -> {len(summary)} chars)")
                return summary

        except Exception as e:
            logger.error(f"Transcript summarization failed for {item.title}: {e}")

        # Fallback: just truncate
        return item.content[:1500]

    async def _score_with_rubric(self, prompt_template: str, item: ResearchItem,
                                  eval_content: str, rubric_name: str) -> dict:
        """Score an item using a specific rubric prompt. Returns parsed result or {}."""
        prompt = prompt_template.format(
            source=item.source,
            title=item.title,
            url=item.url,
            content=eval_content[:1500]
        )

        try:
            model = self.router.models.get(ModelTier.CHEAP)
            if not model:
                logger.error(f"No cheap model for {rubric_name} evaluation")
                return {}

            response = await self.router.invoke(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=500
            )

            result = self._parse_response(response.get("content", ""))
            if result:
                logger.debug(f"{rubric_name} score for '{item.title[:40]}': {result.get('score', 0)}")
            return result

        except Exception as e:
            logger.error(f"{rubric_name} evaluation failed for {item.title}: {e}")
            return {}

    async def _llm_classify(self, item: ResearchItem) -> Set[str]:
        """
        LLM fallback classifier for items with zero keyword matches.
        Uses a cheap, fast LLM call to classify content that might use
        novel terminology or unexpected framing.
        Returns set of goal IDs, or empty set if not relevant.
        """
        prompt = CLASSIFIER_PROMPT.format(
            title=item.title,
            content=item.content[:500]
        )

        try:
            model = self.router.models.get(ModelTier.CHEAP)
            if not model:
                return set()

            response = await self.router.invoke(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=50
            )

            category = response.get("content", "").strip().lower().strip('"').strip("'")

            # Map to goal IDs
            valid_goals = {g["id"] for g in self.goals}
            if category in valid_goals:
                logger.debug(f"LLM classified '{item.title[:40]}' as {category}")
                return {category}
            elif category == "none":
                return set()
            else:
                # Try partial match
                for goal_id in valid_goals:
                    if goal_id in category or category in goal_id:
                        return {goal_id}
                return set()

        except Exception as e:
            logger.debug(f"LLM classification failed for {item.title[:40]}: {e}")
            return set()

    async def evaluate(self, item: ResearchItem) -> ResearchItem:
        """Evaluate a single item against goals using dual rubrics."""
        # Pre-filter: Check if any keywords match and which goals
        matched_goal_ids = self._keyword_match_goals(item)

        # LLM fallback: if no keywords matched, try cheap LLM classification
        if not matched_goal_ids:
            matched_goal_ids = await self._llm_classify(item)

        if not matched_goal_ids:
            item.relevance_score = 0
            item.priority = "none"
            item.suggested_action = "ignore"
            item.reasoning = "No keyword or LLM matches"
            return item

        # For transcripts with long content, summarize first (two-pass evaluation)
        eval_content = item.content
        if item.source == "transcript" and len(item.content) > 2000:
            eval_content = await self.summarize_transcript(item)
            item.summary = eval_content

        # Determine which rubrics to run based on matched goals
        use_david = bool(matched_goal_ids & DAVID_FLIP_GOALS)
        use_technical = bool(matched_goal_ids & TECHNICAL_GOALS)

        # If somehow neither matched (new goal?), default to technical
        if not use_david and not use_technical:
            use_technical = True

        best_result = None
        best_score = 0

        # Run David Flip rubric if surveillance/privacy goals matched
        if use_david:
            david_result = await self._score_with_rubric(
                DAVID_FLIP_PROMPT, item, eval_content, "DavidFlip"
            )
            if david_result:
                score = float(david_result.get("score", david_result.get("david_score", 0)))
                if score > best_score:
                    best_score = score
                    best_result = david_result

        # Run Technical rubric if AI/gamedev/tools goals matched
        if use_technical:
            tech_result = await self._score_with_rubric(
                TECHNICAL_PROMPT, item, eval_content, "Technical"
            )
            if tech_result:
                score = float(tech_result.get("score", 0))
                if score > best_score:
                    best_score = score
                    best_result = tech_result

        # Apply the winning result
        if best_result:
            item.summary = best_result.get("summary", item.summary or "")
            item.matched_goals = best_result.get("matched_goals", list(matched_goal_ids))
            item.relevance_score = best_score
            item.priority = best_result.get("priority", "none")
            item.suggested_action = best_result.get("suggested_action", "ignore")
            item.reasoning = best_result.get("reasoning", "")

        logger.debug(f"Evaluated: {item.title[:50]} -> {item.priority} ({item.relevance_score})")
        return item

    async def evaluate_batch(self, items: List[ResearchItem],
                             batch_size: int = 5) -> List[ResearchItem]:
        """Evaluate multiple items efficiently."""
        evaluated = []

        for i, item in enumerate(items):
            try:
                result = await self.evaluate(item)
                evaluated.append(result)

                if (i + 1) % 10 == 0:
                    logger.info(f"Evaluated {i + 1}/{len(items)} items")

            except Exception as e:
                logger.error(f"Error evaluating item {i}: {e}")
                evaluated.append(item)

        # Log summary
        relevant = [i for i in evaluated if i.relevance_score > 3]
        logger.info(f"Evaluation complete: {len(relevant)}/{len(evaluated)} relevant items")

        return evaluated

    def _keyword_match(self, item: ResearchItem) -> bool:
        """Quick keyword pre-filter to avoid unnecessary LLM calls."""
        return bool(self._keyword_match_goals(item))

    def _keyword_match_goals(self, item: ResearchItem) -> Set[str]:
        """Return set of goal IDs whose keywords match the item."""
        text = f"{item.title} {item.content}".lower()
        matched = set()

        for goal in self.goals:
            for keyword in goal.get("keywords", []):
                if keyword.lower() in text:
                    matched.add(goal["id"])
                    break  # One match per goal is enough

        return matched

    def _parse_response(self, content: str) -> dict:
        """Parse JSON from LLM response."""
        try:
            # Handle markdown code blocks
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            return json.loads(content.strip())
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse evaluation response: {e}")
            logger.debug(f"Raw response: {content[:200]}")
            return {}
