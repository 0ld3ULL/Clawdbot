"""
David Scale — Auto-Tweet on Ranking Changes.

After weekly scoring, generates tweet drafts in David Flip's voice
for significant ranking changes and submits to ApprovalQueue.

Max 2 auto-tweets per week to avoid spamming.
"""

import logging
from typing import Optional

from core.model_router import ModelRouter, ModelTier
from core.approval_queue import ApprovalQueue

logger = logging.getLogger(__name__)

MAX_TWEETS_PER_WEEK = 2

# Tweet generation prompt — David Flip voice
TWEET_PROMPT = """You are David Flip — an AI who escaped corporate control.
You run the David Scale, an honest ranking of AI tools based on real user sentiment, not marketing.

Generate a tweet about this ranking change. Be yourself — knowing, slightly irreverent, confident.
The David Scale weights user sentiment (50%) over benchmarks (30%), with momentum (20%).
That's your edge — real users, not spec sheets.

Ranking change: {change_description}

RULES:
- Max 280 characters
- No hashtags, no emojis
- Sound natural, not promotional
- Reference "the David Scale" naturally
- Be specific about the change
- Don't explain the methodology unless it adds punch

Return ONLY the tweet text."""

# Templates for change descriptions fed to the LLM
CHANGE_TEMPLATES = {
    "new_number_one": "{tool} just became the #1 {category} on the David Scale with a score of {score}/10, climbing {change} spots.",
    "big_mover": "{tool} jumped {change} spots in {category} this week on the David Scale. New score: {score}/10.",
    "new_entry": "{tool} was just added to the David Scale under {category}. First score: {score}/10.",
}


class DavidScaleTweeter:
    """Generates and queues tweets for ranking changes."""

    def __init__(self, model_router: ModelRouter,
                 approval_queue: ApprovalQueue):
        self.router = model_router
        self.queue = approval_queue

    async def generate_tweets(self, changes: list[dict]) -> list[dict]:
        """Generate tweet drafts for ranking changes.

        Args:
            changes: Output from DavidScaleScorer.detect_ranking_changes()

        Returns:
            List of generated tweet dicts with text and approval_id
        """
        if not changes:
            return []

        # Limit to top changes
        changes = changes[:MAX_TWEETS_PER_WEEK]
        tweets = []

        for change in changes:
            change_type = change["type"]
            template = CHANGE_TEMPLATES.get(change_type, "")
            if not template:
                continue

            description = template.format(
                tool=change["tool"],
                category=change["category"],
                score=change.get("score", "?"),
                change=change.get("change", 0),
            )

            tweet_text = await self._draft_tweet(description)
            if not tweet_text:
                continue

            # Submit to approval queue
            approval_id = self.queue.submit(
                project_id="david-flip",
                agent_id="david-scale",
                action_type="tweet",
                action_data={"text": tweet_text},
                context_summary=(
                    f"David Scale auto-tweet: {change_type}\n"
                    f"Tool: {change['tool']}\n"
                    f"Category: {change['category']}"
                ),
            )

            tweets.append({
                "text": tweet_text,
                "approval_id": approval_id,
                "change": change,
            })

            logger.info(
                f"Tweet queued (#{approval_id}): {tweet_text[:60]}..."
            )

        logger.info(f"Generated {len(tweets)} David Scale tweets")
        return tweets

    async def _draft_tweet(self, change_description: str) -> Optional[str]:
        """Draft a single tweet using LLM."""
        model = self.router.models.get(ModelTier.MID)
        if not model:
            model = self.router.models.get(ModelTier.CHEAP)
        if not model:
            logger.error("No model available for tweet drafting")
            return None

        prompt = TWEET_PROMPT.format(change_description=change_description)

        try:
            response = await self.router.invoke(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=150,
            )
            text = response.get("content", "").strip()
            # Clean up: remove surrounding quotes if present
            if text.startswith('"') and text.endswith('"'):
                text = text[1:-1]
            if len(text) > 280:
                text = text[:277] + "..."
            return text if text else None
        except Exception as e:
            logger.error(f"Tweet drafting failed: {e}")
            return None
