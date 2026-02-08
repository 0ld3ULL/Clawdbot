"""
Fast DEVA conversation using Edge TTS (Microsoft) - near instant voice.

Edge TTS is free and MUCH faster than ElevenLabs for real-time conversation.
Trade-off: Different voice (not Veronica), but response is instant.

Run: python voice/talk_to_deva_fast.py
"""

import asyncio
import os
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

import anthropic
import edge_tts
import sounddevice as sd
import soundfile as sf
from personality.deva import get_deva_prompt

# Fast female voices for DEVA
EDGE_VOICES = {
    "aria": "en-US-AriaNeural",      # Expressive, good for DEVA's drama
    "jenny": "en-US-JennyNeural",    # Casual, friendly
    "sonia": "en-GB-SoniaNeural",    # British, sophisticated
    "emma": "en-US-EmmaNeural",      # Clear, professional
}

DEVA_EDGE_VOICE = EDGE_VOICES["aria"]  # Aria is expressive - good for diva


async def speak_fast(text: str, voice: str = DEVA_EDGE_VOICE):
    """Generate and play speech using Edge TTS - very fast."""
    communicate = edge_tts.Communicate(text, voice)

    # Save to temp file
    with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
        temp_path = f.name

    await communicate.save(temp_path)

    # Play it
    data, sample_rate = sf.read(temp_path)
    sd.play(data, sample_rate)
    sd.wait()

    # Cleanup
    os.unlink(temp_path)


async def main():
    print("=" * 50)
    print("  DEVA - Developer Expert Virtual Assistant")
    print("  (Fast Mode - Edge TTS)")
    print("=" * 50)
    print()
    print("Type your message and press Enter.")
    print("Type 'quit' to exit.")
    print()
    print(f"Using voice: Microsoft Aria (fast)")
    print()

    # Initialize
    client = anthropic.Anthropic()
    system_prompt = get_deva_prompt(mode="voice")
    messages = []

    while True:
        try:
            user_input = input("You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nDEVA: Fine, leave. I have better things to do anyway.")
                await speak_fast("Fine, leave. I have better things to do anyway.")
                break

            messages.append({"role": "user", "content": user_input})

            print("DEVA is thinking...")
            response = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=200,  # Shorter for faster TTS
                system=system_prompt,
                messages=messages,
            )

            deva_response = response.content[0].text
            messages.append({"role": "assistant", "content": deva_response})

            print(f"DEVA: {deva_response}")
            print("(speaking...)")
            await speak_fast(deva_response)
            print()

        except KeyboardInterrupt:
            print("\n\nDEVA: Interrupted. Typical.")
            break
        except Exception as e:
            print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
