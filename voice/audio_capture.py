"""
Audio Capture - Microphone input handling.

Supports:
- Push-to-talk (hold key to record)
- Voice activity detection (auto-detect speech)
- Continuous recording
"""

import io
import logging
import threading
import wave
from typing import Callable, Optional

logger = logging.getLogger(__name__)

# Audio settings
SAMPLE_RATE = 16000  # Whisper expects 16kHz
CHANNELS = 1  # Mono
CHUNK_SIZE = 1024
FORMAT_BITS = 16


class AudioCapture:
    """Capture audio from microphone."""

    def __init__(self, sample_rate: int = SAMPLE_RATE, channels: int = CHANNELS):
        """
        Initialize audio capture.

        Args:
            sample_rate: Audio sample rate (default 16000 for Whisper)
            channels: Number of audio channels (default 1 for mono)
        """
        self.sample_rate = sample_rate
        self.channels = channels
        self._stream = None
        self._recording = False
        self._frames = []
        self._lock = threading.Lock()

    def _get_sounddevice(self):
        """Lazy import sounddevice."""
        try:
            import sounddevice as sd
            return sd
        except ImportError:
            raise RuntimeError(
                "sounddevice not installed. Run:\n"
                "pip install sounddevice\n"
                "On Windows, you may also need: pip install soundfile"
            )

    def list_devices(self) -> list[dict]:
        """List available audio input devices."""
        sd = self._get_sounddevice()
        devices = sd.query_devices()
        input_devices = []

        for i, device in enumerate(devices):
            if device['max_input_channels'] > 0:
                input_devices.append({
                    "id": i,
                    "name": device['name'],
                    "channels": device['max_input_channels'],
                    "sample_rate": device['default_samplerate'],
                    "is_default": i == sd.default.device[0],
                })

        return input_devices

    def get_default_device(self) -> Optional[dict]:
        """Get the default input device."""
        devices = self.list_devices()
        for device in devices:
            if device['is_default']:
                return device
        return devices[0] if devices else None

    def record_seconds(self, duration: float, device_id: Optional[int] = None) -> bytes:
        """
        Record audio for a fixed duration.

        Args:
            duration: Recording duration in seconds
            device_id: Specific device ID (uses default if None)

        Returns:
            WAV audio data as bytes
        """
        sd = self._get_sounddevice()

        logger.info(f"Recording {duration}s of audio...")

        # Record audio
        audio_data = sd.rec(
            int(duration * self.sample_rate),
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='int16',
            device=device_id,
        )
        sd.wait()  # Wait for recording to complete

        logger.info(f"Recording complete: {len(audio_data)} samples")

        # Convert to WAV bytes
        return self._to_wav_bytes(audio_data)

    def start_recording(self, device_id: Optional[int] = None):
        """
        Start continuous recording (for push-to-talk).

        Call stop_recording() to get the audio data.
        """
        sd = self._get_sounddevice()

        with self._lock:
            if self._recording:
                logger.warning("Already recording")
                return

            self._frames = []
            self._recording = True

        def callback(indata, frames, time, status):
            if status:
                logger.warning(f"Audio callback status: {status}")
            if self._recording:
                with self._lock:
                    self._frames.append(indata.copy())

        self._stream = sd.InputStream(
            samplerate=self.sample_rate,
            channels=self.channels,
            dtype='int16',
            device=device_id,
            callback=callback,
            blocksize=CHUNK_SIZE,
        )
        self._stream.start()
        logger.info("Recording started (push-to-talk)")

    def stop_recording(self) -> bytes:
        """
        Stop recording and return the audio data.

        Returns:
            WAV audio data as bytes
        """
        with self._lock:
            self._recording = False

        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None

        # Combine all frames
        with self._lock:
            if not self._frames:
                logger.warning("No audio frames captured")
                return b""

            import numpy as np
            audio_data = np.concatenate(self._frames)
            self._frames = []

        logger.info(f"Recording stopped: {len(audio_data)} samples")
        return self._to_wav_bytes(audio_data)

    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recording

    def _to_wav_bytes(self, audio_data) -> bytes:
        """Convert numpy audio array to WAV bytes."""
        buffer = io.BytesIO()

        with wave.open(buffer, 'wb') as wav_file:
            wav_file.setnchannels(self.channels)
            wav_file.setsampwidth(2)  # 16-bit = 2 bytes
            wav_file.setframerate(self.sample_rate)
            wav_file.writeframes(audio_data.tobytes())

        return buffer.getvalue()


class PushToTalk:
    """Push-to-talk recording with keyboard control."""

    def __init__(self, capture: AudioCapture = None, key: str = "space"):
        """
        Initialize push-to-talk.

        Args:
            capture: AudioCapture instance (creates one if None)
            key: Key to hold for recording (default: space)
        """
        self.capture = capture or AudioCapture()
        self.key = key
        self._on_audio: Optional[Callable[[bytes], None]] = None

    def _get_keyboard(self):
        """Lazy import keyboard library."""
        try:
            import keyboard
            return keyboard
        except ImportError:
            raise RuntimeError(
                "keyboard not installed. Run:\n"
                "pip install keyboard\n"
                "Note: On Linux, may need to run as root"
            )

    def start(self, on_audio: Callable[[bytes], None]):
        """
        Start listening for push-to-talk.

        Args:
            on_audio: Callback function that receives WAV audio bytes
        """
        keyboard = self._get_keyboard()
        self._on_audio = on_audio

        def on_press(event):
            if event.name == self.key and not self.capture.is_recording():
                logger.info(f"[{self.key}] pressed - start recording")
                self.capture.start_recording()

        def on_release(event):
            if event.name == self.key and self.capture.is_recording():
                logger.info(f"[{self.key}] released - stop recording")
                audio = self.capture.stop_recording()
                if audio and self._on_audio:
                    self._on_audio(audio)

        keyboard.on_press(on_press)
        keyboard.on_release(on_release)

        logger.info(f"Push-to-talk active. Hold [{self.key}] to speak.")

    def stop(self):
        """Stop listening for push-to-talk."""
        keyboard = self._get_keyboard()
        keyboard.unhook_all()
        logger.info("Push-to-talk stopped")


# Convenience function
def record_audio(duration: float = 5.0) -> bytes:
    """Quick recording for testing."""
    capture = AudioCapture()
    return capture.record_seconds(duration)
