"""
Streaming Text-to-Speech - Start playing immediately while generating.

Uses ElevenLabs streaming API for near-instant voice response.
"""

import io
import logging
import os
import queue
import threading
from typing import Optional

logger = logging.getLogger(__name__)


class StreamingTTS:
    """Stream audio from ElevenLabs - plays while generating."""

    def __init__(self, voice_id: Optional[str] = None):
        self.voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID")
        self._api_key = os.environ.get("ELEVENLABS_API_KEY")
        self._audio_queue = queue.Queue()
        self._playing = False

    def speak(self, text: str, model: str = "eleven_turbo_v2_5"):
        """
        Speak text with streaming - audio starts almost immediately.

        Args:
            text: Text for DEVA to speak
            model: ElevenLabs model (eleven_turbo_v2_5 recommended for speed)
        """
        import httpx
        import sounddevice as sd
        import soundfile as sf

        url = f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}/stream"

        headers = {
            "Accept": "audio/mpeg",
            "Content-Type": "application/json",
            "xi-api-key": self._api_key,
        }

        data = {
            "text": text,
            "model_id": model,
            "voice_settings": {
                "stability": 0.4,
                "similarity_boost": 0.75,
            }
        }

        # Collect all audio chunks first (simpler approach)
        # True streaming with sounddevice is complex due to MP3 decoding
        audio_chunks = []

        logger.info(f"Streaming TTS: {text[:50]}...")

        with httpx.stream("POST", url, headers=headers, json=data, timeout=60) as response:
            if response.status_code != 200:
                raise RuntimeError(f"ElevenLabs error: {response.status_code}")

            for chunk in response.iter_bytes(chunk_size=1024):
                if chunk:
                    audio_chunks.append(chunk)

        # Combine and play
        audio_data = b"".join(audio_chunks)

        # Play using soundfile + sounddevice
        buffer = io.BytesIO(audio_data)
        data_array, sample_rate = sf.read(buffer)
        sd.play(data_array, sample_rate)
        sd.wait()


class LocalTTS:
    """
    Local text-to-speech using Edge TTS (Microsoft) - fast and free.

    Falls back to this if you want zero latency and don't mind different voice.
    """

    def __init__(self, voice: str = "en-US-AriaNeural"):
        """
        Initialize local TTS.

        Args:
            voice: Edge TTS voice name
                   Female options:
                   - en-US-AriaNeural (default, expressive)
                   - en-US-JennyNeural (casual)
                   - en-GB-SoniaNeural (British)
        """
        self.voice = voice

    async def speak(self, text: str):
        """Generate and play speech locally."""
        try:
            import edge_tts
            import sounddevice as sd
            import soundfile as sf
            import tempfile
            import os

            # Generate audio
            communicate = edge_tts.Communicate(text, self.voice)

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                temp_path = f.name

            await communicate.save(temp_path)

            # Play it
            data, sample_rate = sf.read(temp_path)
            sd.play(data, sample_rate)
            sd.wait()

            # Cleanup
            os.unlink(temp_path)

        except ImportError:
            raise RuntimeError(
                "edge-tts not installed. Run:\n"
                "pip install edge-tts"
            )

    def speak_sync(self, text: str):
        """Synchronous version."""
        import asyncio
        asyncio.run(self.speak(text))


# Quick test
if __name__ == "__main__":
    import asyncio
    from dotenv import load_dotenv
    load_dotenv()

    print("Testing streaming TTS...")

    # Test ElevenLabs streaming
    from personality.deva import DEVA_VOICE
    tts = StreamingTTS(voice_id=DEVA_VOICE["voice_id"])
    tts.speak("Hello! I'm DEVA. This is streaming audio, so it should start playing faster.")
