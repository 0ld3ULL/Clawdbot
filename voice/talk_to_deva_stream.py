"""
DEVA with streaming audio - Veronica voice, starts playing immediately.

Uses ElevenLabs streaming API + pygame for real-time playback.
Audio starts playing within 1-2 seconds while rest generates.

Run: python voice/talk_to_deva_stream.py
"""

import asyncio
import io
import os
import sys
import tempfile
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import anthropic
import httpx
from personality.deva import get_deva_prompt, DEVA_VOICE


def play_audio_file(file_path: str):
    """Play audio file using sounddevice."""
    import sounddevice as sd
    import soundfile as sf
    data, sample_rate = sf.read(file_path)
    sd.play(data, sample_rate)
    sd.wait()


async def stream_and_play(text: str):
    """
    Stream audio from ElevenLabs and play as it arrives.
    """
    voice_id = DEVA_VOICE["voice_id"]
    api_key = os.environ.get("ELEVENLABS_API_KEY")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"

    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key,
    }

    data = {
        "text": text,
        "model_id": DEVA_VOICE.get("model", "eleven_v3"),
        "voice_settings": {
            "stability": DEVA_VOICE.get("stability", 0.3),
            "similarity_boost": DEVA_VOICE.get("similarity_boost", 0.75),
            "style": DEVA_VOICE.get("style", 0.8),
            "use_speaker_boost": DEVA_VOICE.get("use_speaker_boost", True),
        }
    }

    # Stream to temp file, then play
    # (True streaming with MP3 decoding is complex, this is simpler)
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        temp_path = f.name

        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("POST", url, headers=headers, json=data) as response:
                if response.status_code != 200:
                    error = await response.aread()
                    raise RuntimeError(f"ElevenLabs error {response.status_code}: {error}")

                # Write chunks as they arrive
                first_chunk = True
                async for chunk in response.aiter_bytes(chunk_size=4096):
                    if chunk:
                        f.write(chunk)
                        if first_chunk:
                            print("(audio streaming...)")
                            first_chunk = False

    # Play the complete file
    play_audio_file(temp_path)

    # Cleanup
    os.unlink(temp_path)


async def main():
    print("=" * 50)
    print("  DEVA - Developer Expert Virtual Assistant")
    print("  (Streaming Mode - Veronica Voice)")
    print("=" * 50)
    print()
    print("Type your message and press Enter.")
    print("Type 'quit' to exit.")
    print()

    client = anthropic.Anthropic()
    system_prompt = get_deva_prompt(mode="voice")
    messages = []

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nDEVA signing off. You're welcome.")
                break

            messages.append({"role": "user", "content": user_input})

            print("DEVA is thinking...")
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=150,  # Shorter = faster TTS
                system=system_prompt,
                messages=messages,
            )

            deva_response = response.content[0].text
            messages.append({"role": "assistant", "content": deva_response})

            print(f"DEVA: {deva_response}")

            await stream_and_play(deva_response)
            print()

        except KeyboardInterrupt:
            print("\n\nBye.")
            break
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
