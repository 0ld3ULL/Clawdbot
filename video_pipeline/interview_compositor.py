"""
Interview Compositor - Assembles interview videos from Q&A clips.

Format: Alternating full-screen clips
  David's question → Expert's answer → David's question → ...

Designed for 9:16 vertical video (Shorts/TikTok/Reels).
Normalizes all clips to consistent resolution/fps/codec before joining.
"""

import asyncio
import logging
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Default output specs for vertical video
DEFAULT_WIDTH = 1080
DEFAULT_HEIGHT = 1920
DEFAULT_FPS = 30
DEFAULT_CODEC = "libx264"
DEFAULT_AUDIO_CODEC = "aac"
DEFAULT_AUDIO_BITRATE = "192k"
DEFAULT_CRF = 23

# Title card settings
TITLE_CARD_DURATION = 2.0  # seconds
TITLE_FONT_SIZE = 48
TITLE_BG_COLOR = "black"
TITLE_TEXT_COLOR = "white"

# Transition settings
CROSSFADE_DURATION = 0.3  # seconds


class InterviewCompositor:
    """
    Composites interview videos from David's questions and expert answers.

    Takes a directory of question clips and answer clips, normalizes them,
    and joins them in alternating Q&A order with optional title cards.
    """

    def __init__(self):
        self._ffmpeg = self._find_ffmpeg()

    def _find_ffmpeg(self) -> str:
        """Find FFmpeg executable on the system."""
        # Try common locations
        candidates = ["ffmpeg"]

        if os.name == "nt":
            # Windows paths
            candidates.extend([
                r"C:\Program Files\ffmpeg\bin\ffmpeg.exe",
                r"C:\ffmpeg\bin\ffmpeg.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-7.1.1-full_build\bin\ffmpeg.exe"),
            ])
        else:
            candidates.extend(["/usr/bin/ffmpeg", "/usr/local/bin/ffmpeg"])

        for path in candidates:
            expanded = os.path.expandvars(path)
            if os.path.isfile(expanded):
                return expanded

        # Fallback: hope it's on PATH
        return "ffmpeg"

    async def _get_video_info(self, video_path: str) -> dict:
        """Get video metadata (resolution, fps, duration, codec)."""
        cmd = [
            self._ffmpeg.replace("ffmpeg", "ffprobe"),
            "-v", "quiet",
            "-print_format", "json",
            "-show_format", "-show_streams",
            video_path,
        ]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _ = await proc.communicate()

            import json
            data = json.loads(stdout.decode())

            video_stream = next(
                (s for s in data.get("streams", []) if s["codec_type"] == "video"),
                {},
            )

            return {
                "width": int(video_stream.get("width", 0)),
                "height": int(video_stream.get("height", 0)),
                "fps": eval(video_stream.get("r_frame_rate", "30/1")),
                "duration": float(data.get("format", {}).get("duration", 0)),
                "codec": video_stream.get("codec_name", "unknown"),
            }
        except Exception as e:
            logger.error(f"Failed to get video info for {video_path}: {e}")
            return {"width": 0, "height": 0, "fps": 30, "duration": 0, "codec": "unknown"}

    async def normalize_clip(
        self,
        input_path: str,
        output_path: str,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        fps: int = DEFAULT_FPS,
    ) -> str:
        """
        Normalize a video clip to target resolution, fps, and codec.

        Handles phone videos with varying specs by scaling + padding
        to maintain aspect ratio within the target frame.
        """
        # Scale to fit within target dimensions, pad to fill
        filter_complex = (
            f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,"
            f"fps={fps},format=yuv420p"
        )

        cmd = [
            self._ffmpeg,
            "-i", input_path,
            "-vf", filter_complex,
            "-c:v", DEFAULT_CODEC,
            "-preset", "fast",
            "-crf", str(DEFAULT_CRF),
            "-c:a", DEFAULT_AUDIO_CODEC,
            "-b:a", DEFAULT_AUDIO_BITRATE,
            "-ar", "44100",
            "-ac", "2",
            "-y",
            output_path,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(
                f"FFmpeg normalize failed for {input_path}: {stderr.decode()[-500:]}"
            )

        logger.info(f"Normalized clip: {input_path} -> {output_path}")
        return output_path

    async def create_title_card(
        self,
        text: str,
        output_path: str,
        duration: float = TITLE_CARD_DURATION,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
    ) -> str:
        """Create a title card video with text on black background."""
        # Escape special characters for FFmpeg drawtext
        safe_text = text.replace("'", "\\'").replace(":", "\\:")

        cmd = [
            self._ffmpeg,
            "-f", "lavfi",
            "-i", f"color=c={TITLE_BG_COLOR}:s={width}x{height}:d={duration}:r={DEFAULT_FPS}",
            "-f", "lavfi",
            "-i", f"anullsrc=r=44100:cl=stereo",
            "-t", str(duration),
            "-vf", (
                f"drawtext=text='{safe_text}':"
                f"fontsize={TITLE_FONT_SIZE}:"
                f"fontcolor={TITLE_TEXT_COLOR}:"
                f"x=(w-text_w)/2:y=(h-text_h)/2"
            ),
            "-c:v", DEFAULT_CODEC,
            "-preset", "fast",
            "-crf", str(DEFAULT_CRF),
            "-c:a", DEFAULT_AUDIO_CODEC,
            "-b:a", DEFAULT_AUDIO_BITRATE,
            "-shortest",
            "-y",
            output_path,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Title card creation failed: {stderr.decode()[-500:]}")

        logger.info(f"Created title card: {output_path}")
        return output_path

    async def compose_interview(
        self,
        questions_dir: str,
        answers_dir: str,
        output_path: str,
        title: str = "",
        expert_name: str = "",
        include_title_cards: bool = True,
        music_path: Optional[str] = None,
        music_volume: float = 0.08,
    ) -> dict:
        """
        Compose a full interview video from Q&A clip pairs.

        Args:
            questions_dir: Directory containing David's question clips (q1.mp4, q2.mp4, ...)
            answers_dir: Directory containing expert answer clips (a1.mp4, a2.mp4, ...)
            output_path: Where to save the final composed video
            title: Interview title for intro card
            expert_name: Expert's name for title cards
            include_title_cards: Whether to add title cards between Q&A pairs
            music_path: Optional background music track
            music_volume: Background music volume (very low for interviews)

        Returns:
            dict with output_path, duration, clip_count, etc.
        """
        questions_path = Path(questions_dir)
        answers_path = Path(answers_dir)

        # Find matching Q&A pairs
        q_files = sorted(questions_path.glob("q*.mp4"))
        a_files = sorted(answers_path.glob("a*.mp4"))

        if not q_files:
            return {"error": "No question clips found"}
        if not a_files:
            return {"error": "No answer clips found"}

        pairs = min(len(q_files), len(a_files))
        logger.info(f"Composing interview: {pairs} Q&A pairs")

        # Create temp directory for normalized clips
        temp_dir = tempfile.mkdtemp(prefix="interview_")
        normalized_clips = []

        try:
            # Optional intro title card
            if include_title_cards and title:
                intro_text = title
                if expert_name:
                    intro_text += f"\\nwith {expert_name}"
                intro_path = os.path.join(temp_dir, "intro_card.mp4")
                await self.create_title_card(
                    intro_text, intro_path, duration=3.0
                )
                normalized_clips.append(intro_path)

            # Process each Q&A pair
            for i in range(pairs):
                q_file = q_files[i]
                a_file = a_files[i]

                # Optional Q&A label title card
                if include_title_cards:
                    label_path = os.path.join(temp_dir, f"label_{i+1}.mp4")
                    await self.create_title_card(
                        f"Question {i+1}", label_path, duration=1.5
                    )
                    normalized_clips.append(label_path)

                # Normalize question clip
                norm_q = os.path.join(temp_dir, f"norm_q{i+1}.mp4")
                await self.normalize_clip(str(q_file), norm_q)
                normalized_clips.append(norm_q)

                # Normalize answer clip
                norm_a = os.path.join(temp_dir, f"norm_a{i+1}.mp4")
                await self.normalize_clip(str(a_file), norm_a)
                normalized_clips.append(norm_a)

            # Create concat list file
            concat_list = os.path.join(temp_dir, "concat_list.txt")
            with open(concat_list, "w") as f:
                for clip in normalized_clips:
                    # Escape path for FFmpeg concat demuxer
                    escaped = clip.replace("\\", "/").replace("'", "'\\''")
                    f.write(f"file '{escaped}'\n")

            # Ensure output directory exists
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)

            # Concat all clips
            if music_path and Path(music_path).exists():
                # With background music
                await self._concat_with_music(
                    concat_list, output_path, music_path, music_volume
                )
            else:
                # Without background music
                await self._concat_clips(concat_list, output_path)

            # Get final video info
            info = await self._get_video_info(output_path)

            return {
                "output_path": output_path,
                "duration": info.get("duration", 0),
                "clip_count": len(normalized_clips),
                "qa_pairs": pairs,
                "resolution": f"{DEFAULT_WIDTH}x{DEFAULT_HEIGHT}",
            }

        finally:
            # Clean up temp files
            import shutil
            try:
                shutil.rmtree(temp_dir, ignore_errors=True)
            except Exception:
                pass

    async def _concat_clips(self, concat_list: str, output_path: str):
        """Concatenate clips using FFmpeg concat demuxer."""
        cmd = [
            self._ffmpeg,
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list,
            "-c:v", DEFAULT_CODEC,
            "-preset", "fast",
            "-crf", str(DEFAULT_CRF),
            "-c:a", DEFAULT_AUDIO_CODEC,
            "-b:a", DEFAULT_AUDIO_BITRATE,
            "-y",
            output_path,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Concat failed: {stderr.decode()[-500:]}")

        logger.info(f"Concatenated {output_path}")

    async def _concat_with_music(
        self,
        concat_list: str,
        output_path: str,
        music_path: str,
        music_volume: float,
    ):
        """Concatenate clips with background music mixed in."""
        cmd = [
            self._ffmpeg,
            "-f", "concat",
            "-safe", "0",
            "-i", concat_list,
            "-stream_loop", "-1",
            "-i", music_path,
            "-filter_complex", (
                f"[0:a]volume=1.0[voice];"
                f"[1:a]volume={music_volume}[music];"
                f"[voice][music]amix=inputs=2:duration=first[aout]"
            ),
            "-map", "0:v",
            "-map", "[aout]",
            "-c:v", DEFAULT_CODEC,
            "-preset", "fast",
            "-crf", str(DEFAULT_CRF),
            "-c:a", DEFAULT_AUDIO_CODEC,
            "-b:a", DEFAULT_AUDIO_BITRATE,
            "-shortest",
            "-y",
            output_path,
        ]

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            raise RuntimeError(f"Concat with music failed: {stderr.decode()[-500:]}")

        logger.info(f"Concatenated with music: {output_path}")

    def check_clip_pairs(
        self, questions_dir: str, answers_dir: str
    ) -> dict:
        """
        Check which Q&A pairs are complete (both question and answer exist).

        Returns status of each pair and overall readiness.
        """
        questions_path = Path(questions_dir)
        answers_path = Path(answers_dir)

        q_files = sorted(questions_path.glob("q*.mp4"))
        a_files = {f.stem: f for f in answers_path.glob("a*.mp4")}

        pairs = []
        for q_file in q_files:
            q_num = q_file.stem.replace("q", "")
            a_key = f"a{q_num}"
            has_answer = a_key in a_files

            pairs.append({
                "question_num": int(q_num) if q_num.isdigit() else q_num,
                "question_file": str(q_file),
                "has_answer": has_answer,
                "answer_file": str(a_files[a_key]) if has_answer else None,
            })

        complete = sum(1 for p in pairs if p["has_answer"])

        return {
            "total_questions": len(q_files),
            "total_answers": len(a_files),
            "complete_pairs": complete,
            "ready_to_compose": complete > 0,
            "all_complete": complete == len(q_files),
            "pairs": pairs,
        }
