"""
David PIP Video Editor

Creates videos with:
- David in picture-in-picture corner (default)
- B-roll as main content
- Occasional full-screen David cuts

Pipeline:
1. Transcribe David's video with Whisper (get timestamps)
2. Match transcript segments with B-roll using LLM
3. Compose final video with FFmpeg
"""

import asyncio
import json
import logging
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .broll_matcher import BRollMatcher, BRollSegment

logger = logging.getLogger(__name__)


@dataclass
class EditorConfig:
    """Configuration for video editor."""
    # PIP settings
    pip_position: str = "bottom_right"  # bottom_right, bottom_left, top_right, top_left
    pip_size: float = 0.25  # 25% of screen width
    pip_margin: int = 20  # pixels from edge

    # Output settings
    output_width: int = 1920
    output_height: int = 1080
    output_fps: int = 30

    # B-roll folder
    broll_folder: Optional[Path] = None


class DavidPIPEditor:
    """
    Video editor that creates David PIP videos.

    Usage:
        editor = DavidPIPEditor()
        output = await editor.create_video(
            david_video="path/to/david_talking.mp4",
            broll_folder="path/to/broll/",
            output_path="path/to/output.mp4"
        )
    """

    def __init__(
        self,
        config: EditorConfig = None,
        model_router=None
    ):
        self.config = config or EditorConfig()
        self.broll_matcher = BRollMatcher(model_router=model_router)

    async def create_video(
        self,
        david_video: Path | str,
        output_path: Path | str,
        broll_folder: Path | str = None
    ) -> Path:
        """
        Create a PIP video from David's talking head.

        Args:
            david_video: Path to David's video (talking head)
            output_path: Path for output video
            broll_folder: Folder containing B-roll clips (named by ID)

        Returns:
            Path to output video
        """
        david_video = Path(david_video)
        output_path = Path(output_path)
        broll_folder = Path(broll_folder) if broll_folder else self.config.broll_folder

        logger.info(f"Creating PIP video from {david_video}")

        # Step 1: Transcribe with Whisper
        logger.info("Step 1: Transcribing with Whisper...")
        transcript = await self._transcribe(david_video)

        # Step 2: Match B-roll
        logger.info(f"Step 2: Matching {len(transcript)} segments with B-roll...")
        segments = await self.broll_matcher.match_transcript(transcript)

        # Step 3: Build FFmpeg filter
        logger.info("Step 3: Building FFmpeg filter...")
        filter_complex = self._build_filter(segments, broll_folder)

        # Step 4: Render with FFmpeg
        logger.info("Step 4: Rendering final video...")
        await self._render(david_video, segments, broll_folder, output_path, filter_complex)

        logger.info(f"Video complete: {output_path}")
        return output_path

    async def _transcribe(self, video_path: Path) -> list[dict]:
        """Transcribe video using Whisper."""
        try:
            # Use whisper CLI (faster-whisper recommended)
            result = subprocess.run(
                [
                    "whisper",
                    str(video_path),
                    "--model", "base",  # or "small" for better accuracy
                    "--output_format", "json",
                    "--output_dir", str(video_path.parent),
                ],
                capture_output=True,
                text=True,
                timeout=300  # 5 minutes
            )

            if result.returncode != 0:
                logger.error(f"Whisper failed: {result.stderr}")
                raise RuntimeError(f"Whisper transcription failed: {result.stderr}")

            # Load JSON output
            json_path = video_path.with_suffix(".json")
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # Convert to our format
            segments = []
            for seg in data.get("segments", []):
                segments.append({
                    "start": seg["start"],
                    "end": seg["end"],
                    "text": seg["text"].strip()
                })

            return segments

        except FileNotFoundError:
            logger.warning("Whisper not found, using mock transcription")
            # Mock transcription for testing
            duration = self._get_video_duration(video_path)
            segment_length = 10  # 10-second segments
            segments = []
            for i in range(0, int(duration), segment_length):
                segments.append({
                    "start": float(i),
                    "end": min(float(i + segment_length), duration),
                    "text": f"[Segment {i // segment_length + 1}]"
                })
            return segments

    def _get_video_duration(self, video_path: Path) -> float:
        """Get video duration using FFprobe."""
        try:
            result = subprocess.run(
                [
                    "ffprobe",
                    "-v", "error",
                    "-show_entries", "format=duration",
                    "-of", "json",
                    str(video_path)
                ],
                capture_output=True,
                text=True
            )
            data = json.loads(result.stdout)
            return float(data["format"]["duration"])
        except Exception as e:
            logger.error(f"Could not get video duration: {e}")
            return 60.0  # Default 1 minute

    def _build_filter(
        self,
        segments: list[BRollSegment],
        broll_folder: Path
    ) -> str:
        """Build FFmpeg filter_complex for PIP composition."""
        # This is a simplified version - full implementation would
        # dynamically switch between PIP and fullscreen based on segments

        cfg = self.config

        # PIP position calculations
        pip_w = int(cfg.output_width * cfg.pip_size)
        pip_h = int(cfg.output_height * cfg.pip_size)

        positions = {
            "bottom_right": (cfg.output_width - pip_w - cfg.pip_margin,
                           cfg.output_height - pip_h - cfg.pip_margin),
            "bottom_left": (cfg.pip_margin,
                          cfg.output_height - pip_h - cfg.pip_margin),
            "top_right": (cfg.output_width - pip_w - cfg.pip_margin,
                        cfg.pip_margin),
            "top_left": (cfg.pip_margin, cfg.pip_margin),
        }

        pip_x, pip_y = positions.get(cfg.pip_position, positions["bottom_right"])

        # Basic PIP filter (David overlaid on B-roll)
        filter_str = (
            f"[1:v]scale={pip_w}:{pip_h}[pip];"
            f"[0:v][pip]overlay={pip_x}:{pip_y}[out]"
        )

        return filter_str

    async def _render(
        self,
        david_video: Path,
        segments: list[BRollSegment],
        broll_folder: Path,
        output_path: Path,
        filter_complex: str
    ):
        """Render final video with FFmpeg."""
        # Find B-roll clips for each segment
        # For now, use first B-roll as continuous background

        # Find a B-roll file
        broll_file = None
        if broll_folder and broll_folder.exists():
            for ext in ["*.mp4", "*.mov", "*.webm"]:
                files = list(broll_folder.glob(ext))
                if files:
                    broll_file = files[0]
                    break

        if not broll_file:
            # Create black background if no B-roll
            logger.warning("No B-roll found, using black background")
            broll_file = await self._create_black_video(
                self._get_video_duration(david_video)
            )

        # FFmpeg command
        cmd = [
            "ffmpeg",
            "-y",  # Overwrite output
            "-i", str(broll_file),  # Background (B-roll)
            "-i", str(david_video),  # Foreground (David PIP)
            "-filter_complex", filter_complex,
            "-map", "[out]",
            "-map", "1:a",  # Audio from David
            "-c:v", "libx264",
            "-preset", "medium",
            "-crf", "23",
            "-c:a", "aac",
            "-b:a", "192k",
            str(output_path)
        ]

        logger.info(f"Running: {' '.join(cmd)}")

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            logger.error(f"FFmpeg failed: {stderr.decode()}")
            raise RuntimeError(f"FFmpeg render failed: {stderr.decode()}")

    async def _create_black_video(self, duration: float) -> Path:
        """Create a black video for background."""
        cfg = self.config
        temp_path = Path(tempfile.gettempdir()) / "black_bg.mp4"

        cmd = [
            "ffmpeg",
            "-y",
            "-f", "lavfi",
            "-i", f"color=c=black:s={cfg.output_width}x{cfg.output_height}:d={duration}",
            "-c:v", "libx264",
            "-preset", "ultrafast",
            str(temp_path)
        ]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        await process.communicate()
        return temp_path


# CLI interface
async def main():
    """Command-line interface for video editor."""
    import sys

    if len(sys.argv) < 3:
        print("Usage: python -m tools.video_editor.editor <david_video> <output> [broll_folder]")
        sys.exit(1)

    david_video = sys.argv[1]
    output = sys.argv[2]
    broll = sys.argv[3] if len(sys.argv) > 3 else None

    editor = DavidPIPEditor()
    await editor.create_video(david_video, output, broll)
    print(f"Output: {output}")


if __name__ == "__main__":
    asyncio.run(main())
