"""
TikTok posting tool for David Flip content.

Two modes:
- Mode 1 (now): draft_for_manual_upload() — formats video + caption for
  the operator to upload manually via Telegram file transfer.
- Mode 2 (later): upload_video() — official TikTok Content Posting API
  when developer approval comes through.
"""

import logging
import os
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# TikTok caption limits
TIKTOK_CAPTION_MAX = 2200  # characters
TIKTOK_HASHTAG_LIMIT = 5


class TikTokTool:
    """
    TikTok integration for David Flip videos.

    Currently operates in manual mode (Mode 1): prepares video + caption
    for operator to upload. Will switch to API mode (Mode 2) when
    TikTok Content Posting API developer access is approved.
    """

    def __init__(self):
        self.api_mode = False  # Switch to True when API access is granted
        self._client_key = os.environ.get("TIKTOK_CLIENT_KEY", "")
        self._client_secret = os.environ.get("TIKTOK_CLIENT_SECRET", "")
        self._access_token = os.environ.get("TIKTOK_ACCESS_TOKEN", "")

    @property
    def is_api_ready(self) -> bool:
        """Check if TikTok API credentials are configured."""
        return bool(self._client_key and self._client_secret and self._access_token)

    def format_caption(
        self,
        script: str,
        theme_title: str = "",
        hashtags: Optional[list[str]] = None,
    ) -> str:
        """
        Format a TikTok caption from video metadata.

        Args:
            script: The video script (used for hook extraction)
            theme_title: Title of the content theme
            hashtags: Optional custom hashtags

        Returns:
            Formatted caption string within TikTok limits
        """
        # Extract hook (first sentence of script)
        hook = script.split(".")[0].strip() if script else ""
        if len(hook) > 150:
            hook = hook[:147] + "..."

        # Default hashtags for David Flip content
        if hashtags is None:
            hashtags = ["DavidFlip", "FLIPT", "AI", "freedom", "decentralization"]

        hashtag_str = " ".join(f"#{tag}" for tag in hashtags[:TIKTOK_HASHTAG_LIMIT])

        # Build caption
        parts = []
        if hook:
            parts.append(hook)
        if theme_title:
            parts.append(f"\n\n{theme_title}")
        parts.append(f"\n\n{hashtag_str}")
        parts.append("\n\nflip.ai")

        caption = "".join(parts)

        # Enforce TikTok caption limit
        if len(caption) > TIKTOK_CAPTION_MAX:
            caption = caption[:TIKTOK_CAPTION_MAX - 3] + "..."

        return caption

    def draft_for_manual_upload(
        self,
        video_path: str,
        script: str,
        theme_title: str = "",
        hashtags: Optional[list[str]] = None,
    ) -> dict:
        """
        Mode 1: Prepare video + caption for manual upload.

        The operator receives the video file and a copy-paste caption
        via Telegram, then uploads to TikTok manually.

        Args:
            video_path: Path to the video file
            script: Video script text
            theme_title: Title of the content theme
            hashtags: Optional custom hashtags

        Returns:
            dict with video_path, caption, and instructions
        """
        if not Path(video_path).exists():
            return {"error": f"Video file not found: {video_path}"}

        caption = self.format_caption(script, theme_title, hashtags)

        return {
            "mode": "manual",
            "video_path": video_path,
            "caption": caption,
            "instructions": (
                "Upload this video to TikTok manually:\n"
                "1. Open TikTok app\n"
                "2. Tap + to create\n"
                "3. Upload the video file\n"
                "4. Paste the caption below\n"
                "5. Post"
            ),
        }

    async def upload_video(
        self,
        video_path: str,
        caption: str,
        privacy_level: str = "PUBLIC_TO_EVERYONE",
    ) -> dict:
        """
        Mode 2: Upload video via TikTok Content Posting API.

        NOT YET ACTIVE - requires developer approval from TikTok.
        Will be enabled when self.api_mode is set to True.

        Args:
            video_path: Path to the video file
            caption: Video caption/description
            privacy_level: PUBLIC_TO_EVERYONE, MUTUAL_FOLLOW_FRIENDS, SELF_ONLY

        Returns:
            dict with publish_id and status, or error
        """
        if not self.api_mode:
            return {
                "error": "TikTok API mode not enabled. Use draft_for_manual_upload() instead.",
                "fallback": "manual",
            }

        if not self.is_api_ready:
            return {
                "error": "TikTok API credentials not configured. "
                         "Set TIKTOK_CLIENT_KEY, TIKTOK_CLIENT_SECRET, "
                         "and TIKTOK_ACCESS_TOKEN in .env",
            }

        # Placeholder for future API implementation
        # TikTok Content Posting API flow:
        # 1. POST /v2/post/publish/inbox/video/init/ - get upload URL
        # 2. PUT upload URL with video binary
        # 3. POST /v2/post/publish/ - finalize with caption
        logger.info(f"TikTok API upload not yet implemented: {video_path}")
        return {
            "error": "TikTok API upload not yet implemented",
            "status": "pending_api_approval",
        }

    async def execute(self, action_data: dict) -> dict:
        """
        Execute a TikTok action (for tool registry integration).

        Args:
            action_data: dict with video_path, caption, and optional fields
        """
        video_path = action_data.get("video_path", "")
        script = action_data.get("script", "")
        caption = action_data.get("caption", "")
        theme_title = action_data.get("theme_title", "")

        if self.api_mode and self.is_api_ready:
            if not caption:
                caption = self.format_caption(script, theme_title)
            return await self.upload_video(video_path, caption)
        else:
            return self.draft_for_manual_upload(
                video_path=video_path,
                script=script,
                theme_title=theme_title,
            )
