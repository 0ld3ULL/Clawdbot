"""
YouTube Scraper - Monitors channels for new videos.

Uses YouTube Data API v3. Requires YOUTUBE_API_KEY environment variable.
"""

import logging
import os
from datetime import datetime, timedelta
from typing import List

import httpx
import yaml

from ..knowledge_store import ResearchItem

logger = logging.getLogger(__name__)

CONFIG_PATH = "config/research_goals.yaml"


class YouTubeScraper:
    """Scrapes YouTube channels for new videos."""

    name = "youtube"

    def __init__(self):
        self.config = self._load_config()
        self.api_key = os.environ.get("YOUTUBE_API_KEY", "")
        self.client = httpx.AsyncClient(timeout=30.0)

        if not self.api_key:
            logger.warning("YOUTUBE_API_KEY not set - YouTube scraper disabled")

    def _load_config(self) -> dict:
        """Load YouTube configuration."""
        try:
            with open(CONFIG_PATH, "r") as f:
                config = yaml.safe_load(f)
            return config.get("sources", {}).get("youtube", {})
        except Exception as e:
            logger.error(f"Failed to load YouTube config: {e}")
            return {}

    async def scrape(self) -> List[ResearchItem]:
        """Scrape all configured YouTube channels."""
        if not self.api_key:
            return []

        items = []
        channels = self.config.get("channels", [])

        for channel_handle in channels:
            try:
                # Remove @ prefix if present
                handle = channel_handle.lstrip("@")
                videos = await self._get_recent_videos(handle)
                items.extend(videos)
            except Exception as e:
                logger.error(f"Error scraping YouTube channel {channel_handle}: {e}")

        logger.info(f"YouTube scraper found {len(items)} items from {len(channels)} channels")
        return items

    async def _get_channel_id(self, handle: str) -> str:
        """Get channel ID from handle."""
        url = "https://www.googleapis.com/youtube/v3/channels"
        params = {
            "key": self.api_key,
            "forHandle": handle,
            "part": "id"
        }

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            items = data.get("items", [])
            if items:
                return items[0].get("id", "")
        except Exception as e:
            logger.warning(f"Failed to get channel ID for @{handle}: {e}")

        return ""

    async def _get_recent_videos(self, handle: str, max_results: int = 5) -> List[ResearchItem]:
        """Get recent videos from a channel."""
        items = []

        # First get channel ID from handle
        channel_id = await self._get_channel_id(handle)
        if not channel_id:
            logger.warning(f"Could not find channel ID for @{handle}")
            return items

        # Get uploads playlist (it's UC + channel_id with UU prefix)
        uploads_playlist = "UU" + channel_id[2:] if channel_id.startswith("UC") else None

        if not uploads_playlist:
            # Fallback to search
            return await self._search_channel_videos(channel_id, handle, max_results)

        # Get playlist items
        url = "https://www.googleapis.com/youtube/v3/playlistItems"
        params = {
            "key": self.api_key,
            "playlistId": uploads_playlist,
            "part": "snippet",
            "maxResults": max_results
        }

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            # Only get videos from last 7 days
            cutoff = datetime.utcnow() - timedelta(days=7)

            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                video_id = snippet.get("resourceId", {}).get("videoId", "")
                title = snippet.get("title", "")
                description = snippet.get("description", "")
                published = snippet.get("publishedAt", "")
                channel_title = snippet.get("channelTitle", handle)

                # Parse date
                pub_date = self._parse_date(published)
                if pub_date and pub_date < cutoff:
                    continue  # Skip older videos

                if video_id and title:
                    items.append(ResearchItem(
                        source="youtube",
                        source_id=f"youtube:{video_id}",
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        title=f"[{channel_title}] {title}",
                        content=description[:2000] if description else f"New video from {channel_title}",
                        published_at=pub_date
                    ))

        except httpx.HTTPError as e:
            logger.warning(f"HTTP error getting videos for @{handle}: {e}")
        except Exception as e:
            logger.error(f"Error getting videos for @{handle}: {e}")

        return items

    async def _search_channel_videos(self, channel_id: str, handle: str, max_results: int = 5) -> List[ResearchItem]:
        """Fallback: Search for recent videos from a channel."""
        items = []
        url = "https://www.googleapis.com/youtube/v3/search"

        # Only search for videos from last 7 days
        published_after = (datetime.utcnow() - timedelta(days=7)).isoformat() + "Z"

        params = {
            "key": self.api_key,
            "channelId": channel_id,
            "part": "snippet",
            "type": "video",
            "order": "date",
            "maxResults": max_results,
            "publishedAfter": published_after
        }

        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()

            for item in data.get("items", []):
                video_id = item.get("id", {}).get("videoId", "")
                snippet = item.get("snippet", {})
                title = snippet.get("title", "")
                description = snippet.get("description", "")
                published = snippet.get("publishedAt", "")
                channel_title = snippet.get("channelTitle", handle)

                if video_id and title:
                    items.append(ResearchItem(
                        source="youtube",
                        source_id=f"youtube:{video_id}",
                        url=f"https://www.youtube.com/watch?v={video_id}",
                        title=f"[{channel_title}] {title}",
                        content=description[:2000] if description else f"New video from {channel_title}",
                        published_at=self._parse_date(published)
                    ))

        except httpx.HTTPError as e:
            logger.warning(f"HTTP error searching videos for @{handle}: {e}")
        except Exception as e:
            logger.error(f"Error searching videos for @{handle}: {e}")

        return items

    def _parse_date(self, date_str: str) -> datetime:
        """Parse YouTube date format (ISO 8601)."""
        if not date_str:
            return None
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except Exception:
            return None

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
