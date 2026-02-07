"""
Speech-to-Text using local Whisper (GPU accelerated).

Uses faster-whisper for efficient transcription on NVIDIA GPUs.
"""

import logging
import os
import tempfile
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

# Model sizes: tiny, base, small, medium, large-v2, large-v3
# Larger = more accurate but slower
DEFAULT_MODEL = "base"  # Good balance of speed/accuracy for real-time


class SpeechToText:
    """Local Whisper-based speech-to-text."""

    def __init__(self, model_size: str = DEFAULT_MODEL, device: str = "cuda"):
        """
        Initialize Whisper model.

        Args:
            model_size: Whisper model size (tiny, base, small, medium, large-v2, large-v3)
            device: "cuda" for GPU, "cpu" for CPU
        """
        self.model_size = model_size
        self.device = device
        self._model = None

    def _load_model(self):
        """Lazy-load the Whisper model."""
        if self._model is not None:
            return self._model

        try:
            from faster_whisper import WhisperModel

            logger.info(f"Loading Whisper model '{self.model_size}' on {self.device}...")

            # Use float16 on GPU for speed, int8 on CPU for memory
            compute_type = "float16" if self.device == "cuda" else "int8"

            self._model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type=compute_type,
            )

            logger.info(f"Whisper model loaded successfully")
            return self._model

        except ImportError:
            raise RuntimeError(
                "faster-whisper not installed. Run:\n"
                "pip install faster-whisper\n"
                "For CUDA support also install: pip install nvidia-cublas-cu12 nvidia-cudnn-cu12"
            )
        except Exception as e:
            logger.error(f"Failed to load Whisper model: {e}")
            raise

    def transcribe(self, audio_path: str, language: str = "en") -> str:
        """
        Transcribe audio file to text.

        Args:
            audio_path: Path to audio file (WAV, MP3, etc.)
            language: Language code (e.g., "en" for English)

        Returns:
            Transcribed text
        """
        model = self._load_model()

        logger.debug(f"Transcribing: {audio_path}")

        segments, info = model.transcribe(
            audio_path,
            language=language,
            beam_size=5,
            vad_filter=True,  # Filter out silence
        )

        # Combine all segments into single text
        text = " ".join([segment.text.strip() for segment in segments])

        logger.debug(f"Transcribed: {text[:100]}...")
        return text.strip()

    def transcribe_bytes(self, audio_data: bytes, language: str = "en") -> str:
        """
        Transcribe audio bytes to text.

        Args:
            audio_data: Raw audio data (WAV format)
            language: Language code

        Returns:
            Transcribed text
        """
        # Write to temp file (faster-whisper needs a file path)
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(audio_data)
            temp_path = f.name

        try:
            return self.transcribe(temp_path, language)
        finally:
            # Cleanup temp file
            try:
                os.unlink(temp_path)
            except:
                pass

    def get_model_info(self) -> dict:
        """Get information about the loaded model."""
        return {
            "model_size": self.model_size,
            "device": self.device,
            "loaded": self._model is not None,
        }


# Convenience function for quick transcription
_default_stt: Optional[SpeechToText] = None

def transcribe(audio_path: str, language: str = "en") -> str:
    """Quick transcription using default model."""
    global _default_stt
    if _default_stt is None:
        _default_stt = SpeechToText()
    return _default_stt.transcribe(audio_path, language)
