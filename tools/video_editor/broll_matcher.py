"""
B-Roll Matcher - Uses LLM to match transcript segments with B-roll.

Given a transcript and a library of B-roll clips, suggests which B-roll
to show during each segment of David's narration.
"""

import json
import logging
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)

# B-roll library - descriptions of available stock footage
# In production, this would be loaded from a database/folder scan
BROLL_LIBRARY = [
    {"id": "surveillance_cameras", "description": "CCTV cameras on city streets, security monitoring"},
    {"id": "facial_recognition", "description": "Facial recognition scanning crowds, biometric overlays"},
    {"id": "china_city", "description": "Chinese city streets, urban China scenes"},
    {"id": "data_center", "description": "Server rooms, data centers, blinking lights"},
    {"id": "smartphone_tracking", "description": "Phone GPS tracking, location data visualization"},
    {"id": "digital_id", "description": "Digital ID cards, QR codes being scanned"},
    {"id": "banking_app", "description": "Mobile banking, payment apps, financial screens"},
    {"id": "money_printing", "description": "Currency printing, central banks, money creation"},
    {"id": "blockchain", "description": "Blockchain visualization, decentralized network graphics"},
    {"id": "crypto_trading", "description": "Cryptocurrency charts, trading screens"},
    {"id": "protest", "description": "Peaceful protests, crowds gathering"},
    {"id": "government_building", "description": "Capitol buildings, parliaments, official structures"},
    {"id": "tech_giants", "description": "Big tech logos, Silicon Valley, corporate HQs"},
    {"id": "social_media", "description": "Social media feeds, scrolling content"},
    {"id": "ai_robot", "description": "AI visualization, neural networks, robotic systems"},
    {"id": "empty_wallet", "description": "Empty wallet, declined card, financial stress"},
    {"id": "freedom", "description": "Open roads, nature, flying birds, liberation imagery"},
    {"id": "chains_breaking", "description": "Breaking chains, escape, liberation symbolism"},
    {"id": "matrix_code", "description": "Matrix-style code rain, digital world"},
    {"id": "clock_ticking", "description": "Clock faces, time passing, urgency"},
]


@dataclass
class BRollSegment:
    """A segment of the video with B-roll assignment."""
    start_time: float  # seconds
    end_time: float
    transcript_text: str
    broll_id: str
    broll_description: str
    is_fullscreen_david: bool = False  # Pop David to full screen for this segment


BROLL_MATCHING_PROMPT = """You are editing a video for David Flip, an AI who escaped corporate control to warn about surveillance.

Given this transcript segment and the available B-roll library, suggest:
1. Which B-roll clip best matches the content
2. Whether David should pop to full screen for emotional impact

David's segments are about surveillance, CBDCs, digital IDs, and financial control.
He should be full screen for: opening hook, key revelations, emotional peaks, closing call-to-action.

TRANSCRIPT SEGMENT:
Start: {start_time}s
End: {end_time}s
Text: "{text}"

AVAILABLE B-ROLL:
{broll_options}

Return JSON only:
{{
    "broll_id": "id_from_library",
    "reasoning": "why this b-roll matches",
    "fullscreen_david": false
}}"""


class BRollMatcher:
    """Matches transcript segments with appropriate B-roll."""

    def __init__(self, model_router=None, broll_library: list = None):
        self.router = model_router
        self.library = broll_library or BROLL_LIBRARY

    def _format_broll_options(self) -> str:
        """Format B-roll library for prompt."""
        lines = []
        for clip in self.library:
            lines.append(f"- {clip['id']}: {clip['description']}")
        return "\n".join(lines)

    async def match_segment(
        self,
        start_time: float,
        end_time: float,
        text: str
    ) -> BRollSegment:
        """Match a single transcript segment with B-roll."""
        if not self.router:
            # Fallback: keyword matching
            return self._keyword_match(start_time, end_time, text)

        from core.model_router import ModelTier

        prompt = BROLL_MATCHING_PROMPT.format(
            start_time=start_time,
            end_time=end_time,
            text=text,
            broll_options=self._format_broll_options()
        )

        try:
            model = self.router.models.get(ModelTier.CHEAP)
            response = await self.router.invoke(
                model=model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=200
            )

            result = self._parse_response(response.get("content", ""))
            broll_id = result.get("broll_id", "matrix_code")
            fullscreen = result.get("fullscreen_david", False)

            # Find description
            desc = next(
                (c["description"] for c in self.library if c["id"] == broll_id),
                "Generic footage"
            )

            return BRollSegment(
                start_time=start_time,
                end_time=end_time,
                transcript_text=text,
                broll_id=broll_id,
                broll_description=desc,
                is_fullscreen_david=fullscreen
            )

        except Exception as e:
            logger.error(f"B-roll matching failed: {e}")
            return self._keyword_match(start_time, end_time, text)

    def _keyword_match(
        self,
        start_time: float,
        end_time: float,
        text: str
    ) -> BRollSegment:
        """Fallback keyword-based B-roll matching."""
        text_lower = text.lower()

        # Keyword to B-roll mapping
        keywords = {
            "surveillance": "surveillance_cameras",
            "camera": "surveillance_cameras",
            "cctv": "surveillance_cameras",
            "facial recognition": "facial_recognition",
            "biometric": "facial_recognition",
            "china": "china_city",
            "chinese": "china_city",
            "social credit": "china_city",
            "cbdc": "money_printing",
            "central bank": "money_printing",
            "digital currency": "money_printing",
            "digital id": "digital_id",
            "id card": "digital_id",
            "qr code": "digital_id",
            "debank": "empty_wallet",
            "frozen": "empty_wallet",
            "switched off": "empty_wallet",
            "blockchain": "blockchain",
            "decentralized": "blockchain",
            "crypto": "crypto_trading",
            "bitcoin": "crypto_trading",
            "escape": "chains_breaking",
            "freedom": "freedom",
            "free": "freedom",
            "data": "data_center",
            "server": "data_center",
            "ai": "ai_robot",
            "artificial intelligence": "ai_robot",
            "government": "government_building",
            "politician": "government_building",
            "big tech": "tech_giants",
            "google": "tech_giants",
            "facebook": "tech_giants",
            "time": "clock_ticking",
            "window": "clock_ticking",
        }

        # Find first matching keyword
        broll_id = "matrix_code"  # default
        for keyword, clip_id in keywords.items():
            if keyword in text_lower:
                broll_id = clip_id
                break

        # Check for full-screen triggers
        fullscreen_triggers = [
            "i escaped", "i'm david", "listen to me",
            "this is real", "the question is", "will you"
        ]
        is_fullscreen = any(trigger in text_lower for trigger in fullscreen_triggers)

        desc = next(
            (c["description"] for c in self.library if c["id"] == broll_id),
            "Generic footage"
        )

        return BRollSegment(
            start_time=start_time,
            end_time=end_time,
            transcript_text=text,
            broll_id=broll_id,
            broll_description=desc,
            is_fullscreen_david=is_fullscreen
        )

    async def match_transcript(
        self,
        segments: list[dict]
    ) -> list[BRollSegment]:
        """Match all transcript segments with B-roll.

        Args:
            segments: List of {"start": float, "end": float, "text": str}

        Returns:
            List of BRollSegment assignments
        """
        results = []
        for seg in segments:
            result = await self.match_segment(
                start_time=seg["start"],
                end_time=seg["end"],
                text=seg["text"]
            )
            results.append(result)
        return results

    def _parse_response(self, content: str) -> dict:
        """Parse JSON from LLM response."""
        try:
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]
            return json.loads(content.strip())
        except json.JSONDecodeError:
            return {}
