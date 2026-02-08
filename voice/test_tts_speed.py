"""Test TTS speed with pygame instead of sounddevice."""
import time
import wave
import tempfile
import os
import pygame

# Initialize pygame mixer ONCE at start
pygame.mixer.init()

from piper import PiperVoice

print('Loading voice...')
voice = PiperVoice.load('data/voices/jenny.onnx')

text = 'What game dev challenge can I help you tackle today?'
print(f'Speaking: {text}')
print()

t1 = time.time()
temp_path = tempfile.mktemp(suffix='.wav')
print(f'1. Temp file: {time.time()-t1:.2f}s')

t2 = time.time()
with wave.open(temp_path, 'wb') as wav_file:
    voice.synthesize_wav(text, wav_file)
print(f'2. Synthesize: {time.time()-t2:.2f}s')

t3 = time.time()
pygame.mixer.music.load(temp_path)
print(f'3. Load file: {time.time()-t3:.2f}s')

t4 = time.time()
pygame.mixer.music.play()
print(f'4. Play start: {time.time()-t4:.2f}s')

# Wait for playback to finish
while pygame.mixer.music.get_busy():
    time.sleep(0.1)
print(f'5. Play done: {time.time()-t4:.2f}s')

os.unlink(temp_path)
pygame.mixer.quit()
