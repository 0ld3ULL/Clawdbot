"""Seed DEVA's memory with core knowledge she should always have."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from voice.memory import DevaMemory, GroupMemory, GameMemory

print("Seeding DEVA's memory...")

# === User Profile ===
mem = DevaMemory()
mem.set_user("name", "Jono")
mem.set_user("alias", "0ld3ULL")
mem.set_user("role", "AI Founder / Game Developer")
mem.set_user("company", "PLAYA3ULL GAMES")
mem.set_user("active_engine", "Unity")
mem.set_user("active_game", "Amphitheatre")
mem.set_user("project_path", r"C:\Games\Amphitheatre\Amphitheatre")
mem.set_user("os", "Windows")
mem.set_user("note", "Not a programmer - uses voice to direct DEVA. Australian accent.")
print("  User profile: set")

# === Core Knowledge ===
mem.learn(
    topic="DEVA Identity",
    content="DEVA is a voice-controlled AI game development assistant built by PLAYA3ULL GAMES. She uses voice input (Whisper STT) and voice output (ElevenLabs TTS) with Claude as the brain. She has tools for editing code, running commands, and managing Unity projects.",
    category="general",
    source="core"
)
mem.learn(
    topic="Amphitheatre Project",
    content="Amphitheatre is a Unity game by PLAYA3ULL GAMES. It's a Roman-themed multiplayer game. The project is located at C:\\Games\\Amphitheatre\\Amphitheatre. It uses Unity engine.",
    category="unity",
    source="core"
)
mem.learn(
    topic="DEVA Trigger Words",
    content="DEVA operates in two modes: conversation mode (default) for discussion and planning, and action mode triggered by 'DEVA execute program' or 'execute program'. In conversation mode, DEVA talks naturally. When the trigger phrase is said, DEVA reviews the conversation and takes action using her tools.",
    category="general",
    source="core"
)
mem.learn(
    topic="Wall Mode",
    content="Wall Mode loads an entire codebase into context using Gemini 2.5 Flash (1M token context). Activate by saying 'wall' or 'wall [subsystem]'. The codebase is cached for follow-up questions. Clear with 'clear wall'.",
    category="general",
    source="core"
)
mem.learn(
    topic="Jono's Working Setup",
    content="Jono works between two computers - an ASUS ROG laptop and a main PC. Projects may be on different drives. Amphitheatre project is at C:\\Games\\Amphitheatre\\Amphitheatre on the laptop. Unity 6000.3.7f1 is installed at C:\\Program Files\\Unity\\Hub\\Editor\\6000.3.7f1.",
    category="general",
    source="core"
)
print("  Knowledge: seeded")

# === Register Amphitheatre Game ===
games = GameMemory()
games.register_game("Amphitheatre", "unity")

# Update with project path
with __import__('sqlite3').connect(games.db_path) as conn:
    conn.execute("UPDATE games SET project_path = ? WHERE name = ?",
                 (r"C:\Games\Amphitheatre\Amphitheatre", "Amphitheatre"))
print("  Game 'Amphitheatre' registered")

print("\nDone! DEVA now knows who Jono is and about Amphitheatre.")
