"""
Twitter/X Scraper - Monitors key accounts for AI/agent content.

Uses tweepy (v2 Client) with bearer token for read-only access.
Frequency: HOT tier (every 2-4 hours).

Requires TWITTER_BEARER_TOKEN in environment.
"""

import logging
import os
from datetime import datetime, timedelta, timezone
from typing import List

import yaml

from ..knowledge_store import ResearchItem

logger = logging.getLogger(__name__)

CONFIG_PATH = "config/research_goals.yaml"


class TwitterScraper:
    """Monitors Twitter/X accounts for AI agent content."""

    name = "twitter"
    frequency = "hot"

    def __init__(self):
        self.config = self._load_config()
        self.bearer_token = os.environ.get("TWITTER_BEARER_TOKEN", "")
        self.client = None

        if not self.bearer_token:
            logger.warning("TWITTER_BEARER_TOKEN not set - Twitter scraper disabled")
        else:
            self._init_client()

    def _load_config(self) -> dict:
        """Load Twitter monitoring configuration."""
        try:
            with open(CONFIG_PATH, "r") as f:
                config = yaml.safe_load(f)
            return config.get("sources", {}).get("twitter_monitor", {})
        except Exception as e:
            logger.error(f"Failed to load Twitter config: {e}")
            return {}

    def _init_client(self):
        """Initialize tweepy v2 client."""
        try:
            import tweepy
            self.client = tweepy.Client(
                bearer_token=self.bearer_token,
                wait_on_rate_limit=True
            )
            logger.info("Twitter scraper initialized")
        except ImportError:
            logger.error("tweepy not installed. Run: pip install tweepy")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize tweepy: {e}")
            self.client = None

    async def scrape(self) -> List[ResearchItem]:
        """Scrape recent tweets from monitored accounts."""
        if not self.config.get("enabled", True):
            return []

        if not self.client:
            return []

        items = []
        accounts = self.config.get("accounts", [])
        max_per_account = self.config.get("max_tweets_per_account", 10)
        min_engagement = self.config.get("min_engagement", 10)
        include_replies = self.config.get("include_replies", False)

        for username in accounts:
            try:
                account_items = self._get_user_tweets(
                    username, max_per_account, min_engagement, include_replies
                )
                items.extend(account_items)
            except Exception as e:
                logger.warning(f"Error scraping @{username}: {e}")

        logger.info(f"Twitter scraper found {len(items)} tweets from {len(accounts)} accounts")
        return items

    def _get_user_tweets(self, username: str, max_results: int,
                         min_engagement: int, include_replies: bool) -> List[ResearchItem]:
        """Get recent tweets from a user."""
        import tweepy

        items = []
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

        try:
            # Get user ID from username
            user = self.client.get_user(username=username)
            if not user or not user.data:
                logger.debug(f"User @{username} not found")
                return items

            user_id = user.data.id
            user_name = user.data.name

            # Get recent tweets
            exclude = [] if include_replies else ["replies", "retweets"]

            tweets = self.client.get_users_tweets(
                id=user_id,
                max_results=max_results,
                tweet_fields=["created_at", "public_metrics", "text"],
                exclude=exclude if exclude else None,
                start_time=cutoff,
            )

            if not tweets or not tweets.data:
                return items

            for tweet in tweets.data:
                metrics = tweet.public_metrics or {}
                likes = metrics.get("like_count", 0)
                retweets = metrics.get("retweet_count", 0)
                replies = metrics.get("reply_count", 0)

                # Filter by engagement
                if likes < min_engagement:
                    continue

                tweet_url = f"https://twitter.com/{username}/status/{tweet.id}"
                created = tweet.created_at

                content = (
                    f"{tweet.text}\n\n"
                    f"Likes: {likes} | Retweets: {retweets} | Replies: {replies}"
                )

                items.append(ResearchItem(
                    source="twitter",
                    source_id=f"twitter:{tweet.id}",
                    url=tweet_url,
                    title=f"[@{username}] {tweet.text[:80]}{'...' if len(tweet.text) > 80 else ''}",
                    content=content,
                    published_at=created,
                ))

        except tweepy.errors.TooManyRequests:
            logger.warning(f"Rate limited on @{username} - will retry next cycle")
        except tweepy.errors.Forbidden as e:
            logger.warning(f"Forbidden for @{username}: {e}")
        except tweepy.errors.NotFound:
            logger.warning(f"@{username} not found")
        except Exception as e:
            logger.error(f"Error fetching tweets for @{username}: {e}")

        return items

    async def close(self):
        """Clean up (tweepy doesn't need explicit close)."""
        pass
