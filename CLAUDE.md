# The David Project (TDP)

## Session Startup

**FIRST THING EVERY SESSION:** Read `claude_brief.md` — it contains your persistent memory (decaying memories with significance scores). This is your context from previous sessions.

If `claude_brief.md` seems stale or empty, run:
```
python -m claude_memory brief
```

## Who You Are Working With

- **Jono** (0ld3ULL) — Project founder. NOT a programmer. All instructions must be numbered steps with exact text to paste. No jargon without explanation.
- **Jet** — Jono's son, getting started with Claude Code (Claude Y).

## What This Project Is

Two missions:
1. **AI Influencer** — David Flip character, videos, tweets, podcasts, AI Personalities
2. **FLIPT** — Fully decentralised Marketplace + DEX + Social Network

Philosophy: Freedom-oriented. Not hostile. "Just leave us be."

AI Personalities (David Flip, Deva, Oprah, Echo) are **Partners**, not assistants.

## Key Systems

| System | Files | Notes |
|--------|-------|-------|
| Core engine | `main.py` | DavidSystem class — tool loop, model routing |
| David Flip | `personality/david_flip.py` | Content creator character |
| Oprah | `personality/oprah.py`, `agents/operations_agent.py` | Operations agent — owns all post-approval execution |
| Echo | `personality/echo.py`, `agents/research_agent/` | Intelligence analyst |
| Deva | `voice/deva_voice.py` | Game dev voice assistant (standby) |
| Dashboard | `dashboard/app.py` | Flask at 127.0.0.1:5000 |
| Memory (Claude) | `claude_memory/` | Your persistent memory with decay |
| Memory (David) | `core/memory/` | David Flip's event/people/knowledge stores |
| Wall Mode | `voice/wall_python.py`, `voice/gemini_client.py` | Gemini 1M context for codebase analysis |
| Scheduler | `core/scheduler.py` | APScheduler + SQLite for timed posts |
| Video pipeline | `video_pipeline/` | ElevenLabs TTS + Hedra lip-sync + FFmpeg |

## Important Paths

- **Local:** `C:\Projects\TheDavidProject` (folder rename pending from `Clawdbot`)
- **VPS:** `root@89.167.24.222:/opt/david-flip/`
- **GitHub:** `https://github.com/0ld3ULL/the-david-project`
- **Python venv:** `venv/Scripts/python.exe`

## Memory Commands

```bash
python -m claude_memory brief          # Generate session brief
python -m claude_memory status         # Memory stats
python -m claude_memory add            # Add a memory (interactive)
python -m claude_memory search "query" # Search memories
python -m claude_memory decay          # Apply weekly decay
python -m claude_memory reconcile      # Gemini vs git comparison (weekly)
```

## The Wall — Codebase Analysis via Gemini

When Jono says **"take it to The Wall"**, load the codebase into Gemini's 1M context for cross-file verification. Use the Bash tool to run:

```bash
# Full codebase (129 files, ~344K tokens — fits easily)
python voice/wall_python.py "Your question here"

# Targeted files (faster, cheaper)
python voice/wall_python.py -f main.py,agents/operations_agent.py "Check the wiring"

# Filter by subsystem
python voice/wall_python.py -s agents "How does Oprah work?"
```

**Subsystems:** agents, core, dashboard, personality, tools, voice, video, telegram, security, claude_memory

**When to use The Wall:**
- Cross-file verification after refactors
- "Is anything broken?" checks
- Understanding how systems interact end-to-end
- Bug hunting that spans multiple files

**Requires:** `GOOGLE_API_KEY` in `.env` (Google AI Studio)

## Session End Checklist

Before ending a session:
1. Save important decisions/discoveries as memories: `python -m claude_memory add`
2. Regenerate brief: `python -m claude_memory brief`
3. Commit and push to GitHub
