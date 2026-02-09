"""
Multi-platform video distributor for David Flip content.

Takes a video + metadata and distributes to selected platforms:
- Twitter (via TwitterTool.post_video)
- YouTube (via YouTubeTool.upload_short)
- TikTok (via TikTokTool - manual mode or API)

All posts go through the approval queue first.
Replaces ad-hoc _post_video_both() in telegram_bot.py.
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class VideoDistributor:
    """
    Distributes approved videos to multiple platforms.

    All distribution is operator-triggered and goes through approval queue.
    No autonomous posting.
    """

    def __init__(self, twitter_tool=None, youtube_tool=None, tiktok_tool=None,
                 telegram_bot=None):
        self._twitter = twitter_tool
        self._youtube = youtube_tool
        self._tiktok = tiktok_tool
        self._telegram = telegram_bot  # For TikTok manual mode (send file to operator)

    def _get_twitter(self):
        """Lazy-load Twitter tool."""
        if self._twitter is None:
            try:
                from tools.twitter_tool import TwitterTool
                self._twitter = TwitterTool()
            except Exception as e:
                logger.error(f"Failed to load TwitterTool: {e}")
        return self._twitter

    def _get_youtube(self):
        """Lazy-load YouTube tool."""
        if self._youtube is None:
            try:
                from tools.youtube_tool import YouTubeTool
                self._youtube = YouTubeTool()
            except Exception as e:
                logger.error(f"Failed to load YouTubeTool: {e}")
        return self._youtube

    def _get_tiktok(self):
        """Lazy-load TikTok tool."""
        if self._tiktok is None:
            try:
                from tools.tiktok_tool import TikTokTool
                self._tiktok = TikTokTool()
            except Exception as e:
                logger.error(f"Failed to load TikTokTool: {e}")
        return self._tiktok

    async def distribute(
        self,
        video_path: str,
        script: str,
        platforms: list[str],
        title: str = "",
        description: str = "",
        theme_title: str = "",
        tags: Optional[list[str]] = None,
    ) -> dict:
        """
        Distribute a video to selected platforms.

        Args:
            video_path: Path to the video file
            script: Video script text
            platforms: List of platforms: "twitter", "youtube", "tiktok"
            title: Video title (used for YouTube)
            description: Video description
            theme_title: Theme title for TikTok caption
            tags: Tags/hashtags for platforms that support them

        Returns:
            dict with results per platform and overall status
        """
        if not Path(video_path).exists():
            return {"error": f"Video file not found: {video_path}"}

        if tags is None:
            tags = ["DavidFlip", "FLIPT", "decentralization", "freedom", "AI"]

        results = {}
        errors = {}

        for platform in platforms:
            try:
                if platform == "twitter":
                    result = await self._post_twitter(
                        video_path, script, title, description
                    )
                elif platform == "youtube":
                    result = await self._post_youtube(
                        video_path, title or "David Flip", description, tags
                    )
                elif platform == "tiktok":
                    result = await self._post_tiktok(
                        video_path, script, theme_title
                    )
                else:
                    result = {"error": f"Unknown platform: {platform}"}

                if "error" in result:
                    errors[platform] = result["error"]
                else:
                    results[platform] = result

            except Exception as e:
                logger.error(f"Distribution to {platform} failed: {e}")
                errors[platform] = str(e)

        return {
            "distributed": list(results.keys()),
            "failed": list(errors.keys()),
            "results": results,
            "errors": errors,
            "all_success": len(errors) == 0,
        }

    async def _post_twitter(
        self, video_path: str, script: str, title: str, description: str
    ) -> dict:
        """Post video to Twitter/X."""
        twitter = self._get_twitter()
        if not twitter:
            return {"error": "Twitter tool not available"}

        # Build tweet text from title + description, within 280 chars
        tweet_text = title
        if description:
            tweet_text += f"\n\n{description}"
        tweet_text = tweet_text[:280]

        if not tweet_text.strip():
            # Extract hook from script as tweet text
            hook = script.split(".")[0].strip() if script else "David Flip"
            tweet_text = hook[:280]

        result = await twitter.post_video(text=tweet_text, video_path=video_path)
        if "error" in result:
            return result

        logger.info(f"Posted to Twitter: {result.get('url', 'OK')}")
        return {
            "platform": "twitter",
            "url": result.get("url", ""),
            "tweet_id": result.get("tweet_id", ""),
        }

    async def _post_youtube(
        self, video_path: str, title: str, description: str, tags: list[str]
    ) -> dict:
        """Post video to YouTube as a Short."""
        youtube = self._get_youtube()
        if not youtube:
            return {"error": "YouTube tool not available"}

        result = await youtube.upload_short(
            video_path=video_path,
            title=title or "David Flip",
            description=description or "flipt.ai",
            tags=tags,
        )

        if "error" in result:
            return result

        url = result.get("shorts_url") or result.get("url", "")
        logger.info(f"Posted to YouTube: {url}")
        return {
            "platform": "youtube",
            "url": url,
            "video_id": result.get("id", ""),
        }

    async def _post_tiktok(
        self, video_path: str, script: str, theme_title: str
    ) -> dict:
        """
        Post video to TikTok.

        In manual mode (current): returns draft info for operator.
        In API mode (future): uploads directly.
        """
        tiktok = self._get_tiktok()
        if not tiktok:
            return {"error": "TikTok tool not available"}

        result = tiktok.draft_for_manual_upload(
            video_path=video_path,
            script=script,
            theme_title=theme_title,
        )

        if "error" in result:
            return result

        # If we have a Telegram bot reference, send the file to operator
        if self._telegram and result.get("mode") == "manual":
            try:
                await self._send_tiktok_to_operator(
                    video_path, result.get("caption", "")
                )
                result["sent_to_operator"] = True
            except Exception as e:
                logger.error(f"Failed to send TikTok file to operator: {e}")
                result["sent_to_operator"] = False

        logger.info(f"TikTok draft prepared: {video_path}")
        return {
            "platform": "tiktok",
            "mode": result.get("mode", "manual"),
            "caption": result.get("caption", ""),
            "sent_to_operator": result.get("sent_to_operator", False),
        }

    async def _send_tiktok_to_operator(self, video_path: str, caption: str):
        """Send TikTok video + caption to operator via Telegram."""
        if not self._telegram or not self._telegram.app:
            return

        operator_id = self._telegram.operator_id
        if not operator_id:
            return

        # Send video file
        with open(video_path, "rb") as video_file:
            await self._telegram.app.bot.send_video(
                chat_id=operator_id,
                video=video_file,
                caption=(
                    "TIKTOK UPLOAD\n\n"
                    "Upload this video to TikTok manually.\n"
                    "Caption to copy-paste below:"
                ),
            )

        # Send caption as separate message (easy to copy)
        await self._telegram.app.bot.send_message(
            chat_id=operator_id,
            text=caption,
        )
