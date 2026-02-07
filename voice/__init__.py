"""
David's Voice System

Components:
- speech_to_text: Local Whisper for transcription (GPU accelerated)
- text_to_speech: ElevenLabs wrapper for David's voice
- audio_capture: Microphone input handling
- audio_playback: Speaker output handling
- voice_assistant: Main interaction loop
"""

from .voice_assistant import VoiceAssistant

__all__ = ["VoiceAssistant"]
