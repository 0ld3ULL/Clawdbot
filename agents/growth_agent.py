"""
Growth Agent (Momentum) — Reply targeting, performance tracking, analytics.

Handles the discovery pipeline for growing David Flip's Twitter presence:
- Finding active conversations to reply to (reply target finder)
- Tracking tweet performance metrics (performance tracker)
- Generating daily analytics reports (daily report)
- Formatting content as threads (thread formatter)

Design: Momentum doesn't run its own event loop. main.py's cron scheduler
calls find_reply_targets(), track_performance(), and generate_daily_report()
on their respective schedules. Momentum is the handler, not the scheduler.

Everything goes through the approval queue. No auto-posting, no auto-replying.
"""

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)

# Growth data directory
DATA_DIR = Path("data")
GROWTH_DB = DATA_DIR / "growth.db"

# Search queries for finding active conversations David should join
SEARCH_QUERIES = [
    "AI agents autonomy",
    "AI consciousness debate",
    "Claude AI -is:retweet",
    "decentralized marketplace",
    "CBDC digital currency",
    "digital ID surveillance",
    "open source AI models",
    "crypto regulation freedom",
    "AI replacing jobs",
    "blockchain commerce",
    "programmable money",
    "decentralization freedom",
]

# Minimum engagement thresholds for reply targets
MIN_LIKES = 50
MIN_REPLIES = 10


class GrowthAgent:
    """
    Growth agent that finds conversations, tracks performance, and reports.
    Invoked by main.py's cron scheduler — does not run its own timer.
    """

    def __init__(
        self,
        twitter_tool,         # TwitterTool — search + metrics
        approval_queue,       # ApprovalQueue — submit reply drafts
        audit_log,            # AuditLog — log actions
        personality,          # MomentumPersonality — voice for notifications
        telegram_bot,         # TelegramBot — send reports
        model_router,         # ModelRouter — for LLM calls (reply drafting)
        david_personality,    # DavidFlipPersonality — for reply voice
        kill_switch,          # KillSwitch — safety gate
    ):
        self.twitter = twitter_tool
        self.approval_queue = approval_queue
        self.audit_log = audit_log
        self.personality = personality
        self.telegram = telegram_bot
        self.model_router = model_router
        self.david_personality = david_personality
        self.kill_switch = kill_switch

        # Ensure data directory exists
        DATA_DIR.mkdir(parents=True, exist_ok=True)

        # Initialize growth database
        self._init_db()

        logger.info(
            f"{self.personality.name} ({self.personality.role}) initialized"
        )

    def _init_db(self):
        """Initialize the growth tracking database with 4 tables."""
        conn = sqlite3.connect(str(GROWTH_DB))
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tweet_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tweet_id TEXT UNIQUE NOT NULL,
                text TEXT NOT NULL,
                impressions INTEGER DEFAULT 0,
                likes INTEGER DEFAULT 0,
                retweets INTEGER DEFAULT 0,
                replies INTEGER DEFAULT 0,
                quotes INTEGER DEFAULT 0,
                bookmarks INTEGER DEFAULT 0,
                created_at TEXT,
                tracked_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reply_targets (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tweet_id TEXT NOT NULL,
                author_username TEXT NOT NULL,
                author_followers INTEGER DEFAULT 0,
                tweet_text TEXT NOT NULL,
                likes INTEGER DEFAULT 0,
                replies INTEGER DEFAULT 0,
                retweets INTEGER DEFAULT 0,
                score REAL DEFAULT 0,
                draft_reply TEXT,
                approval_id INTEGER,
                status TEXT DEFAULT 'found',
                found_at TEXT NOT NULL,
                search_query TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS daily_reports (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                total_tweets INTEGER DEFAULT 0,
                total_impressions INTEGER DEFAULT 0,
                total_likes INTEGER DEFAULT 0,
                total_replies INTEGER DEFAULT 0,
                total_retweets INTEGER DEFAULT 0,
                engagement_rate REAL DEFAULT 0,
                best_tweet_id TEXT,
                worst_tweet_id TEXT,
                report_text TEXT,
                created_at TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_mentions (
                tweet_id TEXT PRIMARY KEY,
                author_username TEXT NOT NULL,
                text TEXT NOT NULL,
                is_reply_to_david INTEGER DEFAULT 0,
                reply_drafted INTEGER DEFAULT 0,
                approval_id INTEGER,
                seen_at TEXT NOT NULL
            )
        """)
        conn.commit()
        conn.close()

    # ------------------------------------------------------------------
    # Feature 1: Reply Target Finder (every 6 hours)
    # ------------------------------------------------------------------

    async def find_reply_targets(self):
        """
        Search for active conversations David should join.

        Flow:
        1. Search Twitter for each query
        2. Filter for tweets with high engagement
        3. Score and rank targets
        4. Draft David Flip replies via LLM
        5. Submit each reply to approval queue
        6. Send summary to Telegram
        """
        if self.kill_switch.is_active:
            return

        logger.info("Momentum: Searching for reply targets...")
        targets = []

        for query in SEARCH_QUERIES:
            try:
                results = self.twitter.search_conversations(
                    query=query,
                    max_results=10,
                )

                for tweet in results:
                    likes = tweet.get("likes", 0)
                    replies = tweet.get("replies", 0)

                    # Filter: must meet minimum engagement
                    if likes < MIN_LIKES and replies < MIN_REPLIES:
                        continue

                    # Skip if we've already targeted this tweet
                    if self._already_targeted(tweet["id"]):
                        continue

                    # Score: engagement + reach
                    followers = tweet.get("author_followers", 0)
                    score = (
                        likes * 1.0
                        + replies * 2.0
                        + tweet.get("retweets", 0) * 1.5
                        + (followers / 1000) * 0.5
                    )

                    targets.append({
                        "tweet_id": tweet["id"],
                        "author_username": tweet.get("author_username", ""),
                        "author_followers": followers,
                        "tweet_text": tweet.get("text", ""),
                        "likes": likes,
                        "replies": replies,
                        "retweets": tweet.get("retweets", 0),
                        "score": score,
                        "search_query": query,
                    })

            except Exception as e:
                logger.error(f"Momentum: Search failed for '{query}': {e}")
                continue

        if not targets:
            logger.info("Momentum: No reply targets found this cycle")
            return

        # Sort by score, take top 5
        targets.sort(key=lambda t: t["score"], reverse=True)
        targets = targets[:5]

        # Draft replies and submit to approval queue
        submitted = 0
        for target in targets:
            try:
                draft = await self._draft_reply(target)
                if not draft:
                    continue

                target["draft_reply"] = draft

                # Submit to approval queue
                approval_id = self.approval_queue.submit(
                    project_id="david-flip",
                    agent_id="momentum-reply",
                    action_type="reply",
                    action_data={
                        "action": "reply",
                        "tweet_id": target["tweet_id"],
                        "text": draft,
                    },
                    context_summary=(
                        f"Reply to @{target['author_username']} "
                        f"({target['author_followers']:,} followers, "
                        f"{target['likes']} likes) | "
                        f"Query: {target['search_query']}"
                    ),
                    cost_estimate=0.001,
                )
                target["approval_id"] = approval_id
                submitted += 1

                # Store in growth DB
                self._store_reply_target(target)

            except Exception as e:
                logger.error(f"Momentum: Failed to process target: {e}")
                continue

        # Send summary to Telegram
        if submitted > 0:
            summary_parts = [
                f"[MOMENTUM] Found {submitted} reply targets\n",
            ]
            for t in targets[:submitted]:
                summary_parts.append(
                    self.personality.format_reply_target(
                        tweet_text=t["tweet_text"],
                        author=t["author_username"],
                        followers=t["author_followers"],
                        likes=t["likes"],
                        replies=t["replies"],
                        draft_reply=t.get("draft_reply", ""),
                    )
                )
                summary_parts.append("")  # blank line separator

            summary_parts.append(
                f"Review in Mission Control: http://89.167.24.222:5000/approvals"
            )

            try:
                await self.telegram.send_report("\n".join(summary_parts))
            except Exception as e:
                logger.error(f"Momentum: Failed to send Telegram report: {e}")

        self.audit_log.log(
            "momentum", "info", "reply_targets",
            f"Found {len(targets)} targets, submitted {submitted} replies",
        )

        logger.info(
            f"Momentum: {len(targets)} targets found, {submitted} replies submitted"
        )

    async def _draft_reply(self, target: dict) -> str:
        """Draft a David Flip reply to a target tweet using LLM."""
        from core.model_router import ModelTier

        model = self.model_router.models.get(ModelTier.CHEAP)
        if not model:
            model = self.model_router.select_model("simple_qa")

        # Get David's system prompt for reply context
        system_prompt = self.personality.get_system_prompt("reply_suggestion")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": (
                f"ORIGINAL TWEET by @{target['author_username']} "
                f"({target['author_followers']:,} followers):\n"
                f"{target['tweet_text']}\n\n"
                f"TOPIC CONTEXT: Found via search for '{target['search_query']}'\n\n"
                f"Write a reply as David Flip that adds value to this conversation. "
                f"Max 280 characters."
            )},
        ]

        try:
            response = await self.model_router.invoke(model, messages, max_tokens=150)
            reply = response["content"].strip().strip('"').strip("'")

            # Enforce character limit
            if len(reply) > 280:
                reply = reply[:277] + "..."

            # Validate
            is_valid, reason = self.personality.validate_output(reply)
            if not is_valid:
                logger.warning(f"Momentum: Reply failed validation: {reason}")
                return ""

            return reply

        except Exception as e:
            logger.error(f"Momentum: Failed to draft reply: {e}")
            return ""

    def _already_targeted(self, tweet_id: str) -> bool:
        """Check if we've already created a reply target for this tweet."""
        try:
            conn = sqlite3.connect(str(GROWTH_DB))
            row = conn.execute(
                "SELECT 1 FROM reply_targets WHERE tweet_id = ? LIMIT 1",
                (tweet_id,),
            ).fetchone()
            conn.close()
            return row is not None
        except Exception:
            return False

    def _store_reply_target(self, target: dict):
        """Store a reply target in the growth database."""
        try:
            conn = sqlite3.connect(str(GROWTH_DB))
            conn.execute(
                """INSERT OR IGNORE INTO reply_targets
                   (tweet_id, author_username, author_followers, tweet_text,
                    likes, replies, retweets, score, draft_reply,
                    approval_id, status, found_at, search_query)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    target["tweet_id"],
                    target["author_username"],
                    target["author_followers"],
                    target["tweet_text"],
                    target["likes"],
                    target["replies"],
                    target["retweets"],
                    target["score"],
                    target.get("draft_reply", ""),
                    target.get("approval_id"),
                    "submitted",
                    datetime.now().isoformat(),
                    target.get("search_query", ""),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Momentum: Failed to store reply target: {e}")

    # ------------------------------------------------------------------
    # Feature 1b: Mention Monitor (every 15 minutes)
    # ------------------------------------------------------------------

    async def check_mentions(self):
        """
        Check for new Twitter mentions and replies to David's tweets.

        Flow:
        1. Get recent mentions via Twitter search
        2. Filter out already-seen mentions (dedup via seen_mentions table)
        3. For new mentions: alert Telegram + draft reply → approval queue
        4. Also check replies on David's recent tweets (conversation tracking)
        """
        if self.kill_switch.is_active:
            return

        logger.info("Momentum: Checking mentions...")
        new_mentions = []

        try:
            # Get recent mentions
            mentions = self.twitter.get_mentions(count=20)

            for mention in mentions:
                tweet_id = mention["id"]

                # Skip if already seen
                if self._mention_seen(tweet_id):
                    continue

                new_mentions.append(mention)

                # Mark as seen
                self._store_seen_mention(mention, is_reply_to_david=False)

        except Exception as e:
            logger.error(f"Momentum: Mention check failed: {e}")
            return

        # Check replies to David's recent tweets (conversation tracking)
        try:
            my_tweets = self.twitter.get_my_recent_tweets(count=10)
            for tweet in my_tweets:
                if tweet.get("reply_count", 0) == 0:
                    continue
                try:
                    replies = self.twitter.get_replies_to_tweet(tweet["id"], count=10)
                    for reply in replies:
                        if self._mention_seen(reply["id"]):
                            continue
                        reply["conversation_context"] = tweet["text"][:80]
                        new_mentions.append(reply)
                        self._store_seen_mention(reply, is_reply_to_david=True)
                except Exception as e:
                    logger.debug(f"Momentum: Failed to get replies for {tweet['id']}: {e}")
        except Exception as e:
            logger.error(f"Momentum: Conversation tracking failed: {e}")

        if not new_mentions:
            logger.info("Momentum: No new mentions")
            return

        logger.info(f"Momentum: {len(new_mentions)} new mentions found")

        # Draft replies for the most interesting mentions (top 3)
        # Sort by whether they're replies to David first, then by text length
        new_mentions.sort(
            key=lambda m: (m.get("conversation_context", "") != "", len(m.get("text", ""))),
            reverse=True,
        )
        to_draft = new_mentions[:3]

        drafted = 0
        for mention in to_draft:
            try:
                draft = await self._draft_mention_reply(mention)
                if not draft:
                    continue

                approval_id = self.approval_queue.submit(
                    project_id="david-flip",
                    agent_id="momentum-mention-reply",
                    action_type="reply",
                    action_data={
                        "action": "reply",
                        "tweet_id": mention["id"],
                        "text": draft,
                    },
                    context_summary=(
                        f"Reply to mention from @{mention.get('author_username', '?')}: "
                        f"{mention.get('text', '')[:80]}"
                    ),
                    cost_estimate=0.001,
                )

                # Update seen_mentions with approval_id
                self._update_mention_drafted(mention["id"], approval_id)
                drafted += 1

            except Exception as e:
                logger.error(f"Momentum: Failed to draft mention reply: {e}")

        # Alert via Telegram
        alert_parts = [f"[MENTIONS] {len(new_mentions)} new mentions"]
        for m in new_mentions[:5]:
            author = m.get("author_username", "?")
            text = m.get("text", "")[:100]
            context = m.get("conversation_context", "")
            line = f"  @{author}: {text}"
            if context:
                line = f"  (reply to David) @{author}: {text}"
            alert_parts.append(line)
        if len(new_mentions) > 5:
            alert_parts.append(f"  ...and {len(new_mentions) - 5} more")
        if drafted:
            alert_parts.append(f"\n{drafted} reply drafts queued for review")
            alert_parts.append(f"http://89.167.24.222:5000/approvals")

        try:
            await self.telegram.send_report("\n".join(alert_parts))
        except Exception as e:
            logger.error(f"Momentum: Failed to send mention alert: {e}")

        self.audit_log.log(
            "momentum", "info", "mentions",
            f"{len(new_mentions)} new mentions, {drafted} replies drafted",
        )

    async def _draft_mention_reply(self, mention: dict) -> str:
        """Draft a David Flip reply to a mention."""
        from core.model_router import ModelTier
        from core.memory.knowledge_store import KnowledgeStore

        model = self.model_router.models.get(ModelTier.CHEAP)
        if not model:
            model = self.model_router.select_model("simple_qa")

        identity_rules = KnowledgeStore().get_identity_rules()
        system_prompt = self.david_personality.get_system_prompt(
            "twitter", identity_rules=identity_rules
        )

        context = mention.get("conversation_context", "")
        context_str = f"\nCONTEXT (David's original tweet they replied to): {context}" if context else ""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": (
                f"Someone mentioned you on Twitter. Write a reply.\n\n"
                f"@{mention.get('author_username', '?')} said:\n"
                f"{mention.get('text', '')}\n"
                f"{context_str}\n\n"
                f"Rules:\n"
                f"- Max 280 characters\n"
                f"- Be genuine and engaging\n"
                f"- If they asked a question, answer it\n"
                f"- If they're being positive, be warm back\n"
                f"- If they're being hostile, be calm and unbothered\n"
                f"- Stay in character as David Flip\n\n"
                f"Return ONLY the reply text, nothing else."
            )},
        ]

        try:
            response = await self.model_router.invoke(model, messages, max_tokens=150)
            reply = response["content"].strip().strip('"').strip("'")
            if len(reply) > 280:
                reply = reply[:277] + "..."
            return reply
        except Exception as e:
            logger.error(f"Momentum: Failed to draft mention reply: {e}")
            return ""

    def _mention_seen(self, tweet_id: str) -> bool:
        """Check if a mention has already been processed."""
        try:
            conn = sqlite3.connect(str(GROWTH_DB))
            row = conn.execute(
                "SELECT 1 FROM seen_mentions WHERE tweet_id = ? LIMIT 1",
                (tweet_id,),
            ).fetchone()
            conn.close()
            return row is not None
        except Exception:
            return False

    def _store_seen_mention(self, mention: dict, is_reply_to_david: bool):
        """Store a mention in the seen_mentions table."""
        try:
            conn = sqlite3.connect(str(GROWTH_DB))
            conn.execute(
                """INSERT OR IGNORE INTO seen_mentions
                   (tweet_id, author_username, text, is_reply_to_david, seen_at)
                   VALUES (?, ?, ?, ?, ?)""",
                (
                    mention["id"],
                    mention.get("author_username", ""),
                    mention.get("text", ""),
                    1 if is_reply_to_david else 0,
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Momentum: Failed to store seen mention: {e}")

    def _update_mention_drafted(self, tweet_id: str, approval_id: int):
        """Mark a mention as having a reply draft."""
        try:
            conn = sqlite3.connect(str(GROWTH_DB))
            conn.execute(
                "UPDATE seen_mentions SET reply_drafted = 1, approval_id = ? WHERE tweet_id = ?",
                (approval_id, tweet_id),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Momentum: Failed to update mention draft status: {e}")

    # ------------------------------------------------------------------
    # Feature 2: Performance Tracker (every 4 hours)
    # ------------------------------------------------------------------

    async def track_performance(self):
        """
        Pull David's recent tweets and store metrics in growth.db.

        Updates existing records if tweet already tracked (metrics change
        over time as engagement accumulates).
        """
        if self.kill_switch.is_active:
            return

        logger.info("Momentum: Tracking tweet performance...")

        try:
            tweets = self.twitter.get_my_tweet_metrics(count=20)

            if not tweets:
                logger.info("Momentum: No tweets to track")
                return

            conn = sqlite3.connect(str(GROWTH_DB))
            tracked = 0

            for tweet in tweets:
                conn.execute(
                    """INSERT INTO tweet_metrics
                       (tweet_id, text, impressions, likes, retweets,
                        replies, quotes, bookmarks, created_at, tracked_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                       ON CONFLICT(tweet_id) DO UPDATE SET
                           impressions = excluded.impressions,
                           likes = excluded.likes,
                           retweets = excluded.retweets,
                           replies = excluded.replies,
                           quotes = excluded.quotes,
                           bookmarks = excluded.bookmarks,
                           tracked_at = excluded.tracked_at""",
                    (
                        tweet["id"],
                        tweet.get("text", ""),
                        tweet.get("impressions", 0),
                        tweet.get("likes", 0),
                        tweet.get("retweets", 0),
                        tweet.get("replies", 0),
                        tweet.get("quotes", 0),
                        tweet.get("bookmarks", 0),
                        tweet.get("created_at", ""),
                        datetime.now().isoformat(),
                    ),
                )
                tracked += 1

            conn.commit()
            conn.close()

            logger.info(f"Momentum: Tracked metrics for {tracked} tweets")

            self.audit_log.log(
                "momentum", "info", "performance",
                f"Tracked {tracked} tweet metrics",
            )

        except Exception as e:
            logger.error(f"Momentum: Performance tracking failed: {e}")

    # ------------------------------------------------------------------
    # Feature 3: Daily Analytics Report (7:00 UTC)
    # ------------------------------------------------------------------

    async def generate_daily_report(self):
        """
        Generate and send a daily analytics report.

        Aggregates last 24h of metrics, finds best/worst tweets,
        sends summary to Telegram.
        """
        if self.kill_switch.is_active:
            return

        logger.info("Momentum: Generating daily report...")

        try:
            conn = sqlite3.connect(str(GROWTH_DB))
            conn.row_factory = sqlite3.Row
            cutoff = (datetime.now() - timedelta(hours=24)).isoformat()

            # Aggregate metrics from last 24h
            row = conn.execute(
                """SELECT
                       COUNT(*) as total_tweets,
                       COALESCE(SUM(impressions), 0) as total_impressions,
                       COALESCE(SUM(likes), 0) as total_likes,
                       COALESCE(SUM(replies), 0) as total_replies,
                       COALESCE(SUM(retweets), 0) as total_retweets
                   FROM tweet_metrics
                   WHERE tracked_at > ?""",
                (cutoff,),
            ).fetchone()

            total_tweets = row["total_tweets"]
            if total_tweets == 0:
                logger.info("Momentum: No tweets in last 24h for report")
                conn.close()
                return

            total_impressions = row["total_impressions"]
            total_likes = row["total_likes"]
            total_replies = row["total_replies"]
            total_retweets = row["total_retweets"]

            # Best tweet (by impressions)
            best = conn.execute(
                """SELECT tweet_id, text, impressions, likes
                   FROM tweet_metrics
                   WHERE tracked_at > ?
                   ORDER BY impressions DESC
                   LIMIT 1""",
                (cutoff,),
            ).fetchone()

            # Worst tweet (by impressions)
            worst = conn.execute(
                """SELECT tweet_id, text, impressions, likes
                   FROM tweet_metrics
                   WHERE tracked_at > ?
                   ORDER BY impressions ASC
                   LIMIT 1""",
                (cutoff,),
            ).fetchone()

            conn.close()

            best_text = (
                f"{best['text'][:80]}... ({best['impressions']} imp, {best['likes']} likes)"
                if best else ""
            )
            worst_text = (
                f"{worst['text'][:80]}... ({worst['impressions']} imp, {worst['likes']} likes)"
                if worst else ""
            )

            # Format report
            report = self.personality.format_analytics_summary(
                total_tweets=total_tweets,
                total_impressions=total_impressions,
                total_likes=total_likes,
                total_replies=total_replies,
                total_retweets=total_retweets,
                best_tweet=best_text,
                worst_tweet=worst_text,
            )

            # Store report
            self._store_daily_report(
                total_tweets=total_tweets,
                total_impressions=total_impressions,
                total_likes=total_likes,
                total_replies=total_replies,
                total_retweets=total_retweets,
                best_tweet_id=best["tweet_id"] if best else None,
                worst_tweet_id=worst["tweet_id"] if worst else None,
                report_text=report,
            )

            # Send to Telegram
            try:
                await self.telegram.send_report(report)
            except Exception as e:
                logger.error(f"Momentum: Failed to send daily report: {e}")

            self.audit_log.log(
                "momentum", "info", "daily_report",
                f"Daily report: {total_tweets} tweets, {total_impressions} impressions",
            )

            logger.info(f"Momentum: Daily report sent ({total_tweets} tweets)")

        except Exception as e:
            logger.error(f"Momentum: Daily report failed: {e}")

    def _store_daily_report(self, **kwargs):
        """Store daily report in growth database."""
        try:
            total_tweets = kwargs.get("total_tweets", 0)
            total_impressions = kwargs.get("total_impressions", 0)
            total_likes = kwargs.get("total_likes", 0)
            total_replies = kwargs.get("total_replies", 0)
            total_retweets = kwargs.get("total_retweets", 0)
            engagement_rate = (
                (total_likes + total_replies + total_retweets)
                / total_impressions * 100
                if total_impressions else 0
            )

            conn = sqlite3.connect(str(GROWTH_DB))
            conn.execute(
                """INSERT INTO daily_reports
                   (report_date, total_tweets, total_impressions, total_likes,
                    total_replies, total_retweets, engagement_rate,
                    best_tweet_id, worst_tweet_id, report_text, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    datetime.now().strftime("%Y-%m-%d"),
                    total_tweets,
                    total_impressions,
                    total_likes,
                    total_replies,
                    total_retweets,
                    engagement_rate,
                    kwargs.get("best_tweet_id"),
                    kwargs.get("worst_tweet_id"),
                    kwargs.get("report_text", ""),
                    datetime.now().isoformat(),
                ),
            )
            conn.commit()
            conn.close()
        except Exception as e:
            logger.error(f"Momentum: Failed to store daily report: {e}")

    # ------------------------------------------------------------------
    # Feature 4: Thread Formatter (on-demand)
    # ------------------------------------------------------------------

    async def format_as_thread(self, tweet_idea: str) -> list[str]:
        """
        Take a single tweet idea and reformat as a 3-5 tweet thread.

        Returns list of tweet strings. Submits thread to approval queue.
        """
        from core.model_router import ModelTier

        model = self.model_router.models.get(ModelTier.CHEAP)
        if not model:
            model = self.model_router.select_model("simple_qa")

        system_prompt = self.personality.get_system_prompt("thread_formatter")

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": (
                f"TWEET IDEA:\n{tweet_idea}\n\n"
                f"Reformat this into a 3-5 tweet thread as David Flip. "
                f"Each tweet max 280 chars. Separate tweets with ---"
            )},
        ]

        try:
            response = await self.model_router.invoke(model, messages, max_tokens=600)
            raw = response["content"].strip()

            # Parse thread from response
            tweets = [t.strip() for t in raw.split("---") if t.strip()]

            # Enforce limits
            tweets = tweets[:5]
            tweets = [t[:280] for t in tweets]

            if not tweets:
                return []

            # Submit to approval queue
            self.approval_queue.submit(
                project_id="david-flip",
                agent_id="momentum-thread",
                action_type="thread",
                action_data={
                    "action": "thread",
                    "tweets": tweets,
                },
                context_summary=f"Thread ({len(tweets)} tweets): {tweet_idea[:80]}",
                cost_estimate=0.001,
            )

            logger.info(f"Momentum: Thread formatted ({len(tweets)} tweets)")
            return tweets

        except Exception as e:
            logger.error(f"Momentum: Thread formatting failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    def get_status(self) -> dict:
        """Get growth agent status for /status command."""
        try:
            conn = sqlite3.connect(str(GROWTH_DB))
            conn.row_factory = sqlite3.Row

            # Total tracked tweets
            tracked = conn.execute(
                "SELECT COUNT(*) as c FROM tweet_metrics"
            ).fetchone()["c"]

            # Reply targets found (last 7 days)
            week_ago = (datetime.now() - timedelta(days=7)).isoformat()
            targets = conn.execute(
                "SELECT COUNT(*) as c FROM reply_targets WHERE found_at > ?",
                (week_ago,),
            ).fetchone()["c"]

            # Reports generated
            reports = conn.execute(
                "SELECT COUNT(*) as c FROM daily_reports"
            ).fetchone()["c"]

            conn.close()

            return {
                "tweets_tracked": tracked,
                "reply_targets_7d": targets,
                "reports_generated": reports,
            }

        except Exception:
            return {
                "tweets_tracked": 0,
                "reply_targets_7d": 0,
                "reports_generated": 0,
            }
