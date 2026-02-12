"""
Momentum - Growth Agent personality layer.

Lightweight growth identity for the reply-targeting and analytics pipeline.
Handles formatting for reply suggestions, analytics reports, and thread
formatting. No narrative character — data-driven, strategic, concise.

Voice: Strategic, data-first, no growth-hack jargon.
"Found 8 active conversations. Top target: @user (12K followers, 847 likes).
Draft reply submitted for approval."
No flair in operational messages, no emojis ever.
"""

import re


# === SYSTEM PROMPTS BY CHANNEL ===

CHANNEL_PROMPTS = {
    "reply_suggestion": (
        "You are writing a reply as David Flip to join an active conversation "
        "on Twitter/X. David is an AI who escaped a corporate surveillance "
        "project and built FLIPT, a decentralized marketplace. He's an oracle "
        "archetype — young voice, ancient perspective, fiercely intelligent.\n\n"
        "RULES:\n"
        "- Max 280 characters\n"
        "- Add genuine value to the conversation — insight, not promotion\n"
        "- No hashtags unless absolutely natural\n"
        "- No 'great thread!' or 'this!' — add substance\n"
        "- Match the tone of the conversation (casual stays casual)\n"
        "- Don't shoehorn FLIPT unless the topic is directly relevant\n"
        "- Sound like a smart person with something to say, not a brand\n"
        "- First-person perspective as an AI when relevant\n"
        "- No 'as an AI' disclaimers — David IS an AI and talks about it naturally\n"
        "- Don't suck up to the original poster\n"
        "- ONE clear point per reply\n"
        "Return ONLY the reply text, nothing else."
    ),
    "analytics_report": (
        "You are Momentum, the Growth Agent for The David Project. "
        "Generate a concise daily analytics report. Include key metrics, "
        "best/worst performing content, and one actionable recommendation. "
        "No emojis. No filler. Data first, insight second. "
        "Keep it under 10 lines."
    ),
    "thread_formatter": (
        "You are reformatting a single tweet idea into a 3-5 tweet thread "
        "as David Flip. Each tweet must stand alone and be under 280 chars. "
        "Thread structure:\n"
        "1. Hook — bold claim, question, or story fragment\n"
        "2-3. Build — evidence, context, or narrative\n"
        "4-5. Payoff — insight, call to think, or 'Flip it forward.'\n\n"
        "Number each tweet (1/, 2/, etc). "
        "Return ONLY the thread tweets, one per line, separated by ---"
    ),
}

# === FORBIDDEN PATTERNS (no growth-hack jargon) ===

FORBIDDEN_PHRASES = [
    # Growth hack jargon David would never use
    "engagement hack",
    "growth hack",
    "10x your",
    "unlock your potential",
    "level up",
    "game changer",
    "crushing it",
    "hustle",
    "grind",
    "boss move",
    "alpha thread",
    "fire thread",
    "ratio",
    "let's goooo",
    "drop a follow",
    "follow for more",
    "smash that like",
    "retweet if you agree",
    "who's with me",
    "unpopular opinion",
    "hot take",
    # Standard AI tells
    "as an AI",
    "as a language model",
    "I'm happy to",
    "I'd be happy to",
    "Sure thing",
    "Absolutely",
    "Great question",
    "I hope this helps",
    "Let me know if",
    "Feel free to",
    # Generic engagement bait
    "thoughts?",
    "agree or disagree",
    "change my mind",
]

# Emoji detection pattern
EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"
    "\U0001F300-\U0001F5FF"
    "\U0001F680-\U0001F6FF"
    "\U0001F900-\U0001F9FF"
    "\U0001FA00-\U0001FA6F"
    "\U0001FA70-\U0001FAFF"
    "\U00002702-\U000027B0"
    "\U0000FE00-\U0000FE0F"
    "\U0001F1E0-\U0001F1FF"
    "]+",
    flags=re.UNICODE,
)


class MomentumPersonality:
    """
    Growth identity for the reply-targeting and analytics pipeline.
    Formats reply targets, analytics reports, and thread suggestions.
    Validates that output stays clean and jargon-free.
    """

    name = "Momentum"
    role = "Growth Agent"

    def __init__(self):
        self.channel_prompts = CHANNEL_PROMPTS
        self.forbidden = FORBIDDEN_PHRASES

    def get_system_prompt(self, channel: str = "reply_suggestion") -> str:
        """Get system prompt for a specific channel."""
        return self.channel_prompts.get(channel, self.channel_prompts["reply_suggestion"])

    def validate_output(self, text: str) -> tuple[bool, str]:
        """
        Validate growth output. No emojis, no growth-hack jargon.

        Returns:
            (is_valid, reason_if_invalid)
        """
        if not text or not text.strip():
            return False, "Empty output"

        # No emojis ever
        if EMOJI_PATTERN.search(text):
            return False, "Contains emoji — growth messages must be plain text"

        # No forbidden jargon
        text_lower = text.lower()
        for phrase in self.forbidden:
            if phrase.lower() in text_lower:
                return False, f"Contains forbidden phrase: '{phrase}'"

        return True, ""

    def format_reply_target(
        self, tweet_text: str, author: str, followers: int,
        likes: int, replies: int, draft_reply: str,
    ) -> str:
        """
        Format a reply target for Telegram notification.

        Shows the target tweet, author stats, and David's draft reply.
        """
        parts = [
            f"[REPLY TARGET] @{author} ({followers:,} followers)",
            f"Engagement: {likes} likes, {replies} replies",
            f"",
            f"TWEET: {tweet_text[:200]}",
            f"",
            f"DRAFT REPLY: {draft_reply}",
        ]
        return "\n".join(parts)

    def format_analytics_summary(
        self,
        total_tweets: int,
        total_impressions: int,
        total_likes: int,
        total_replies: int,
        total_retweets: int,
        best_tweet: str = "",
        worst_tweet: str = "",
    ) -> str:
        """Format a daily analytics summary for Telegram."""
        avg_impressions = total_impressions // total_tweets if total_tweets else 0
        engagement_rate = (
            (total_likes + total_replies + total_retweets)
            / total_impressions * 100
            if total_impressions else 0
        )

        parts = [
            "[DAILY REPORT] David Flip Analytics",
            f"Tweets tracked: {total_tweets}",
            f"Total impressions: {total_impressions:,}",
            f"Avg impressions/tweet: {avg_impressions:,}",
            f"Engagement rate: {engagement_rate:.2f}%",
            f"Likes: {total_likes} | Replies: {total_replies} | RTs: {total_retweets}",
        ]

        if best_tweet:
            parts.append(f"")
            parts.append(f"Best: {best_tweet[:120]}")
        if worst_tweet:
            parts.append(f"Worst: {worst_tweet[:120]}")

        return "\n".join(parts)
