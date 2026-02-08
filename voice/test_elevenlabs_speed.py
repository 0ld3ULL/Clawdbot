"""Test ElevenLabs speed with pygame playback."""
import time
import os
import tempfile
import httpx
import pygame

from dotenv import load_dotenv
load_dotenv()

pygame.mixer.init()

VOICE_ID = "ejl43bbp2vjkAFGSmAMa"  # Veronica
API_KEY = os.environ.get("ELEVENLABS_API_KEY")

text = "What game dev challenge can I help you tackle today?"
print(f"Speaking: {text}")
print()

url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}/stream"
headers = {
    "Accept": "audio/mpeg",
    "Content-Type": "application/json",
    "xi-api-key": API_KEY,
}
data = {
    "text": text,
    "model_id": "eleven_flash_v2_5",  # Fastest model
    "voice_settings": {
        "stability": 0.5,
        "similarity_boost": 0.75,
    }
}

# Time the API call
t1 = time.time()
temp_path = tempfile.mktemp(suffix='.mp3')

with httpx.Client(timeout=30) as client:
    with client.stream("POST", url, headers=headers, json=data) as response:
        with open(temp_path, 'wb') as f:
            for chunk in response.iter_bytes():
                f.write(chunk)

print(f"1. API + download: {time.time()-t1:.2f}s")

# Time playback
t2 = time.time()
pygame.mixer.music.load(temp_path)
print(f"2. Load: {time.time()-t2:.2f}s")

t3 = time.time()
pygame.mixer.music.play()
print(f"3. Play start: {time.time()-t3:.2f}s")

while pygame.mixer.music.get_busy():
    time.sleep(0.05)
print(f"4. Play done: {time.time()-t3:.2f}s")

pygame.mixer.music.unload()
os.unlink(temp_path)
pygame.mixer.quit()
