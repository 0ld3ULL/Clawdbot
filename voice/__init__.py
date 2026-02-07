"""
DEVA's Voice System

Components:
- speech_to_text: Local Whisper for transcription (GPU accelerated)
- audio_capture: Microphone input handling
- audio_playback: Speaker output with ElevenLabs TTS
- voice_assistant: Main interaction loop (push-to-talk)

Usage:
    python -m voice.voice_assistant

Or in code:
    from voice import VoiceAssistant
    assistant = VoiceAssistant()
    assistant.start()
"""

from .voice_assistant import VoiceAssistant
from .speech_to_text import SpeechToText
from .audio_capture import AudioCapture, PushToTalk
from .audio_playback import AudioPlayback, TextToSpeechPlayer

__all__ = [
    "VoiceAssistant",
    "SpeechToText",
    "AudioCapture",
    "PushToTalk",
    "AudioPlayback",
    "TextToSpeechPlayer",
]
