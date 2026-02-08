"""
Test DEVA voice system components.

Run: python voice/test_deva.py
"""

import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()


async def test_tts():
    """Test text-to-speech (DEVA speaking)."""
    print("\n=== Testing Text-to-Speech ===")

    from tools.elevenlabs_tool import ElevenLabsTool
    from voice.audio_playback import AudioPlayback
    from personality.deva import DEVA_VOICE

    elevenlabs = ElevenLabsTool()
    playback = AudioPlayback()

    text = "Hello! I'm DEVA, your developer expert virtual assistant. Yes, I know I'm brilliant. You're welcome."

    print(f"Generating speech: {text}")
    # Try DEVA voice first, fall back to default
    voice_id = DEVA_VOICE.get("voice_id") or os.environ.get("ELEVENLABS_VOICE_ID")
    print(f"Using voice ID: {voice_id}")

    audio = await elevenlabs.text_to_speech(
        text=text,
        voice_id=voice_id,
    )
    print(f"Audio generated: {len(audio)} bytes")

    print("Playing audio...")
    playback.play_mp3(audio)
    print("Done!")


def test_stt():
    """Test speech-to-text (recording + Whisper)."""
    print("\n=== Testing Speech-to-Text ===")

    from voice.audio_capture import AudioCapture
    from voice.speech_to_text import SpeechToText

    capture = AudioCapture()
    stt = SpeechToText(model_size="base", device="cuda")

    print("Recording 5 seconds of audio...")
    print("Speak now!")
    audio = capture.record_seconds(5.0)
    print(f"Recorded: {len(audio)} bytes")

    print("Transcribing...")
    text = stt.transcribe_bytes(audio)
    print(f"You said: {text}")


async def test_full_conversation():
    """Test full conversation flow (text only, no voice)."""
    print("\n=== Testing DEVA Conversation ===")

    import anthropic
    from personality.deva import get_deva_prompt

    client = anthropic.Anthropic()
    system_prompt = get_deva_prompt(mode="voice")

    questions = [
        "Hey DEVA, can you help me with Unity?",
        "My player keeps falling through the floor after sitting.",
    ]

    messages = []

    for q in questions:
        print(f"\nYou: {q}")
        messages.append({"role": "user", "content": q})

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=300,
            system=system_prompt,
            messages=messages,
        )

        answer = response.content[0].text
        print(f"DEVA: {answer}")
        messages.append({"role": "assistant", "content": answer})


def test_devices():
    """List available audio devices."""
    print("\n=== Audio Devices ===")

    from voice.audio_capture import AudioCapture
    from voice.audio_playback import AudioPlayback

    capture = AudioCapture()
    playback = AudioPlayback()

    print("\nInput devices (microphones):")
    for d in capture.list_devices():
        default = " (DEFAULT)" if d['is_default'] else ""
        print(f"  [{d['id']}] {d['name']}{default}")

    print("\nOutput devices (speakers):")
    for d in playback.list_devices():
        default = " (DEFAULT)" if d['is_default'] else ""
        print(f"  [{d['id']}] {d['name']}{default}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Test DEVA components")
    parser.add_argument("--tts", action="store_true", help="Test text-to-speech")
    parser.add_argument("--stt", action="store_true", help="Test speech-to-text")
    parser.add_argument("--chat", action="store_true", help="Test conversation")
    parser.add_argument("--devices", action="store_true", help="List audio devices")
    parser.add_argument("--all", action="store_true", help="Run all tests")

    args = parser.parse_args()

    if args.devices or args.all:
        test_devices()

    if args.tts or args.all:
        asyncio.run(test_tts())

    if args.stt or args.all:
        test_stt()

    if args.chat or args.all:
        asyncio.run(test_full_conversation())

    if not any([args.tts, args.stt, args.chat, args.devices, args.all]):
        print("DEVA Test Suite")
        print("===============")
        print("Usage:")
        print("  python voice/test_deva.py --devices  # List audio devices")
        print("  python voice/test_deva.py --tts      # Test DEVA speaking")
        print("  python voice/test_deva.py --stt      # Test speech recognition")
        print("  python voice/test_deva.py --chat     # Test conversation (text)")
        print("  python voice/test_deva.py --all      # Run all tests")
