"""
Hacker News Scraper - Monitors HN front page for AI/agent content.

Uses the free Firebase HN API (no auth needed).
Frequency: HOT tier (every 2-4 hours).
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

import httpx
import yaml

from ..knowledge_store import ResearchItem

logger = logging.getLogger(__name__)

CONFIG_PATH = "config/research_goals.yaml"
HN_API_BASE = "https://hacker-news.firebaseio.com/v0"


class HackerNewsScraper:
    """Scrapes Hacker News for trending AI/agent stories."""

    name = "hackernews"
    frequency = "hot"

    def __init__(self):
        self.config = self._load_config()
        self.client = httpx.AsyncClient(timeout=30.0)
        self.max_stories = self.config.get("max_stories", 30)
        self.min_score = self.config.get("min_score", 20)
        self.keywords = [k.lower() for k in self.config.get("keywords", [])]

    def _load_config(self) -> dict:
        """Load HN configuration."""
        try:
            with open(CONFIG_PATH, "r") as f:
                config = yaml.safe_load(f)
            return config.get("sources", {}).get("hackernews", {})
        except Exception as e:
            logger.error(f"Failed to load HN config: {e}")
            return {}

    async def scrape(self) -> List[ResearchItem]:
        """Scrape top HN stories, filtered by relevance."""
        if not self.config.get("enabled", True):
            return []

        items = []

        try:
            # Get top story IDs
            response = await self.client.get(f"{HN_API_BASE}/topstories.json")
            response.raise_for_status()
            story_ids = response.json()[:self.max_stories]

            # Fetch each story (in batches to be polite)
            cutoff = datetime.utcnow() - timedelta(hours=24)

            tasks = [self._fetch_story(sid) for sid in story_ids]
            results = await asyncio.gather(*tasks, return_exceptions=True)

            for result in results:
                if isinstance(result, Exception):
                    continue
                if result is None:
                    continue

                story = result

                # Filter: must be a story (not job/poll)
                if story.get("type") != "story":
                    continue

                # Filter: must have minimum score
                score = story.get("score", 0)
                if score < self.min_score:
                    continue

                # Filter: must be recent (last 24 hours)
                story_time = datetime.utcfromtimestamp(story.get("time", 0))
                if story_time < cutoff:
                    continue

                title = story.get("title", "")
                story_url = story.get("url", "")
                hn_url = f"https://news.ycombinator.com/item?id={story['id']}"
                num_comments = story.get("descendants", 0)

                # Keyword pre-filter on title
                if self.keywords:
                    title_lower = title.lower()
                    if not any(kw in title_lower for kw in self.keywords):
                        continue

                # Build content
                content = (
                    f"{title}\n\n"
                    f"External URL: {story_url}\n"
                    f"HN Discussion: {hn_url}\n"
                    f"Score: {score} | Comments: {num_comments}\n"
                    f"Posted by: {story.get('by', 'unknown')}"
                )

                items.append(ResearchItem(
                    source="hackernews",
                    source_id=f"hn:{story['id']}",
                    url=story_url or hn_url,
                    title=f"[HN {score}pt] {title}",
                    content=content,
                    published_at=story_time,
                ))

        except httpx.HTTPError as e:
            logger.warning(f"HN API error: {e}")
        except Exception as e:
            logger.error(f"HN scraper error: {e}")

        logger.info(f"HN scraper found {len(items)} relevant stories")
        return items

    async def _fetch_story(self, story_id: int) -> dict:
        """Fetch a single story from the HN API."""
        try:
            response = await self.client.get(
                f"{HN_API_BASE}/item/{story_id}.json"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.debug(f"Failed to fetch HN story {story_id}: {e}")
            return None

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
