"""
Audio Playback - Speaker output handling.

Plays audio from:
- WAV bytes (from recordings)
- MP3 bytes (from ElevenLabs)
- File paths
"""

import io
import logging
import tempfile
import threading
from typing import Optional

logger = logging.getLogger(__name__)


class AudioPlayback:
    """Play audio through speakers."""

    def __init__(self):
        self._playing = False
        self._lock = threading.Lock()

    def _get_sounddevice(self):
        """Lazy import sounddevice."""
        try:
            import sounddevice as sd
            return sd
        except ImportError:
            raise RuntimeError(
                "sounddevice not installed. Run:\n"
                "pip install sounddevice"
            )

    def _get_soundfile(self):
        """Lazy import soundfile."""
        try:
            import soundfile as sf
            return sf
        except ImportError:
            raise RuntimeError(
                "soundfile not installed. Run:\n"
                "pip install soundfile"
            )

    def list_devices(self) -> list[dict]:
        """List available audio output devices."""
        sd = self._get_sounddevice()
        devices = sd.query_devices()
        output_devices = []

        for i, device in enumerate(devices):
            if device['max_output_channels'] > 0:
                output_devices.append({
                    "id": i,
                    "name": device['name'],
                    "channels": device['max_output_channels'],
                    "sample_rate": device['default_samplerate'],
                    "is_default": i == sd.default.device[1],
                })

        return output_devices

    def play_file(self, file_path: str, blocking: bool = True, device_id: Optional[int] = None):
        """
        Play audio from a file.

        Args:
            file_path: Path to audio file (WAV, MP3, etc.)
            blocking: Wait for playback to complete
            device_id: Specific output device (uses default if None)
        """
        sd = self._get_sounddevice()
        sf = self._get_soundfile()

        logger.info(f"Playing audio: {file_path}")

        # Read audio file
        data, sample_rate = sf.read(file_path)

        with self._lock:
            self._playing = True

        try:
            sd.play(data, sample_rate, device=device_id)
            if blocking:
                sd.wait()
        finally:
            with self._lock:
                self._playing = False

        logger.debug("Playback complete")

    def play_bytes(self, audio_data: bytes, format: str = "mp3", blocking: bool = True, device_id: Optional[int] = None):
        """
        Play audio from bytes.

        Args:
            audio_data: Raw audio bytes
            format: Audio format ("mp3", "wav")
            blocking: Wait for playback to complete
            device_id: Specific output device
        """
        sf = self._get_soundfile()

        # soundfile can read from BytesIO
        buffer = io.BytesIO(audio_data)

        try:
            data, sample_rate = sf.read(buffer)
        except Exception as e:
            # Some formats need to be written to temp file first
            logger.debug(f"Direct read failed, using temp file: {e}")
            suffix = f".{format}"
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
                f.write(audio_data)
                temp_path = f.name

            try:
                self.play_file(temp_path, blocking, device_id)
                return
            finally:
                import os
                try:
                    os.unlink(temp_path)
                except:
                    pass

        sd = self._get_sounddevice()

        logger.info(f"Playing {len(audio_data)} bytes of audio")

        with self._lock:
            self._playing = True

        try:
            sd.play(data, sample_rate, device=device_id)
            if blocking:
                sd.wait()
        finally:
            with self._lock:
                self._playing = False

        logger.debug("Playback complete")

    def play_mp3(self, mp3_data: bytes, blocking: bool = True, device_id: Optional[int] = None):
        """
        Play MP3 audio (convenience method for ElevenLabs output).

        Args:
            mp3_data: MP3 audio bytes
            blocking: Wait for playback to complete
            device_id: Specific output device
        """
        self.play_bytes(mp3_data, format="mp3", blocking=blocking, device_id=device_id)

    def stop(self):
        """Stop current playback."""
        sd = self._get_sounddevice()
        sd.stop()
        with self._lock:
            self._playing = False
        logger.info("Playback stopped")

    def is_playing(self) -> bool:
        """Check if audio is currently playing."""
        with self._lock:
            return self._playing


class TextToSpeechPlayer:
    """Combines ElevenLabs TTS with audio playback."""

    def __init__(self, voice_id: Optional[str] = None):
        """
        Initialize TTS player.

        Args:
            voice_id: ElevenLabs voice ID (uses DEVA's default if None)
        """
        self.playback = AudioPlayback()
        self.voice_id = voice_id
        self._elevenlabs = None

    def _get_elevenlabs(self):
        """Lazy load ElevenLabs tool."""
        if self._elevenlabs is None:
            from tools.elevenlabs_tool import ElevenLabsTool
            self._elevenlabs = ElevenLabsTool()
        return self._elevenlabs

    async def speak(self, text: str, blocking: bool = True):
        """
        Convert text to speech and play it.

        Args:
            text: Text for DEVA to speak
            blocking: Wait for playback to complete
        """
        elevenlabs = self._get_elevenlabs()

        logger.info(f"DEVA speaking: {text[:50]}...")

        # Generate speech
        audio_data = await elevenlabs.text_to_speech(
            text=text,
            voice_id=self.voice_id,
        )

        # Play it
        self.playback.play_mp3(audio_data, blocking=blocking)

    def speak_sync(self, text: str, blocking: bool = True):
        """Synchronous version of speak()."""
        import asyncio
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Already in async context, create task
            asyncio.create_task(self.speak(text, blocking))
        else:
            loop.run_until_complete(self.speak(text, blocking))

    def stop(self):
        """Stop current playback."""
        self.playback.stop()


# Convenience functions
def play_audio(audio_data: bytes, format: str = "mp3"):
    """Quick playback for testing."""
    player = AudioPlayback()
    player.play_bytes(audio_data, format=format)


def play_file(file_path: str):
    """Quick file playback for testing."""
    player = AudioPlayback()
    player.play_file(file_path)
