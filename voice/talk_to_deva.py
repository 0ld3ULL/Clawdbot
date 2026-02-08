"""
Simple DEVA conversation - type to talk, she speaks back.

No push-to-talk, just type your message and press Enter.

Run: python voice/talk_to_deva.py
"""

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import anthropic
from tools.elevenlabs_tool import ElevenLabsTool
from voice.audio_playback import AudioPlayback
from personality.deva import get_deva_prompt, DEVA_VOICE


async def main():
    print("=" * 50)
    print("  DEVA - Developer Expert Virtual Assistant")
    print("  (pronounced 'Diva')")
    print("=" * 50)
    print()
    print("Type your message and press Enter.")
    print("Type 'quit' to exit.")
    print()

    # Initialize
    client = anthropic.Anthropic()
    elevenlabs = ElevenLabsTool()
    playback = AudioPlayback()

    system_prompt = get_deva_prompt(mode="voice")
    messages = []

    # Get voice ID
    voice_id = DEVA_VOICE.get("voice_id") or os.environ.get("ELEVENLABS_VOICE_ID")
    print(f"Using voice: {DEVA_VOICE.get('voice_name', 'default')}")
    print()

    while True:
        try:
            # Get user input
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nDEVA: Fine, leave. See if I care. ...I care a little.")
                break

            # Add to conversation
            messages.append({"role": "user", "content": user_input})

            # Get DEVA's response (using Haiku for speed)
            response = client.messages.create(
                model="claude-3-5-haiku-20241022",  # Fast model
                max_tokens=60,  # Very short
                system=system_prompt + "\n\nCRITICAL: MAX 1 sentence. Be brief.",
                messages=messages,
            )

            deva_response = response.content[0].text
            messages.append({"role": "assistant", "content": deva_response})

            # Print response
            print(f"DEVA: {deva_response}")

            # Speak response using streaming
            print("(speaking...)")
            import httpx
            import tempfile

            url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}/stream"
            headers = {
                "Accept": "audio/mpeg",
                "Content-Type": "application/json",
                "xi-api-key": os.environ.get("ELEVENLABS_API_KEY"),
            }
            data = {
                "text": deva_response,
                "model_id": DEVA_VOICE.get("model", "eleven_flash_v2_5"),
                "voice_settings": {
                    "stability": DEVA_VOICE.get("stability", 0.5),
                    "similarity_boost": DEVA_VOICE.get("similarity_boost", 0.75),
                }
            }

            with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
                temp_path = f.name
                async with httpx.AsyncClient(timeout=30) as http:
                    async with http.stream("POST", url, headers=headers, json=data) as resp:
                        async for chunk in resp.aiter_bytes():
                            f.write(chunk)

            playback.play_file(temp_path)
            os.unlink(temp_path)
            print()

        except KeyboardInterrupt:
            print("\n\nDEVA: Interrupted? Rude. But fine. Bye.")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
