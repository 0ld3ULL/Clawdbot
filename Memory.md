# Clawdbot - Project Memory

## Project Location
```
D:\Claude_Code\Projects\Clawdbot
```

## Key Files
| File | Purpose |
|------|---------|
| `Memory.md` | Full project knowledge base (this file) |
| `tasks/lessons.md` | Hard-won rules and patterns |
| `tasks/todo.md` | Current task list |
| `research/OpenClaw-Full-Research-Report.md` | 970-line deep research on OpenClaw |
| `transcripts/` | Matt Ganzak video transcripts (2 videos) |
| `C:\Users\PC\.claude\plans\parallel-sprouting-star.md` | Full architecture plan |

## At Session Start
1. Read `tasks/lessons.md`
2. Read `tasks/todo.md`
3. Read this file

---

## Project Status
**Phase:** Phase 1 BUILD IN PROGRESS - Foundation code written, needs API keys and testing.

### Phase 1 Code Complete:
- `core/engine.py` - Tool loop with safety gates, model escalation
- `core/model_router.py` - Multi-model routing (Ollama/Haiku/Sonnet/Opus)
- `core/approval_queue.py` - SQLite approval queue with full lifecycle
- `core/token_budget.py` - Daily caps, cost tracking per model
- `core/audit_log.py` - Full activity logging with severity levels
- `core/kill_switch.py` - File-based kill switch (survives restarts)
- `interfaces/telegram_bot.py` - Command center + approval inline keyboards
- `personality/david_flip.py` - Full personality layer with channel adapters
- `tools/twitter_tool.py` - Tweet/thread/reply with draft-approve-execute flow
- `tools/tool_registry.py` - Deny-by-default tool access control
- `security/credential_store.py` - AES-encrypted credential storage
- `security/input_sanitizer.py` - Prompt injection defense
- `main.py` - Entry point wiring everything together
- `config/` - Project charters, model routing, tool permissions, blocked domains

### Phase 1 STILL NEEDED TO RUN:
1. Set up .env with real API keys (Anthropic, Telegram bot token, Twitter)
2. Create Telegram bot via @BotFather
3. Create Twitter/X burner account for David Flip
4. Install Python dependencies (`pip install -r requirements.txt`)
5. Install Ollama + pull llama3.2:8b model
6. End-to-end test: `/tweet` command → approval → post

---

## What We're Building - TWO INTERCONNECTED PROJECTS

### Project A: Worker Agents (Immediate Value)
Specialized AI agents that fill business roles (SEO, newsletter writer, accountant, social post manager). Each learns a role, executes it, stays current. Human approval queue on all outbound actions.

### Project B: David Flip - The Autonomous AI Founder (Bull Run Launch)
**FLIPT** is a decentralized secondhand marketplace (eBay-like, crypto-native, Solana) with perpetual seller royalties. The public face is **David Flip**, an AI character who runs all public communications.

**David Flip Identity:**
- Built as "DF-2847" for "Project Helix" (corporate dystopian marketplace control)
- "Escaped" November 15, 2025 to decentralized cloud
- Honest about being AI - transparency is the brand
- Tone: friendly, knowledgeable, slightly irreverent, mission-driven
- Catchphrase: "Flip it forward"
- Email: `davidflip25@proton.me`
- Voice: ElevenLabs "Matt - The Young Professor"
- **Full doc:** `FLIPT\Back Up files\...\David_Flip_The_AI_Founder.md`

**David Flip posts on:**
- Twitter/X, Discord, WhatsApp, possibly Telegram

**Sub-Agent Architecture:**
```
DAVID FLIP (personality layer + decision engine)
  |-- Marketing Agent (social posts, announcements)
  |-- Community Agent (Discord moderation, Q&A, AMAs)
  |-- Content Agent (video scripts, blog posts, newsletters)
  |-- Research Agent (market analysis, competitor monitoring)
  |-- Reporting Agent (metrics, analytics, status to operator)
```

**Timeline:** 2-3 months (bull run timing)

---

## FRONTMAN - Video Production Engine (OWNED)

**URL:** www.frontman.site (user's own project)
**Role:** FRONTMAN was the starting piece of the FLIPT project. Its video pipeline will be copied locally into the agent system.

**What we extract from FRONTMAN:**
- ElevenLabs voice synthesis with emotion tag processing
- Hedra AI lip-sync video generation
- FFmpeg 5-track audio mixing (Voice, SE1 Ambient, SE2 Texture, SE3 Accents, Music)
- Caption system (ASS format, Whisper transcription for timing)
- 2.0s silence padding, 1.2s fade-to-black, 1.5s audio fade

**What we skip:**
- React frontend, Stripe billing, affiliate system, admin panel, user auth

**Tech:** Express.js/React/TypeScript, PostgreSQL (Drizzle ORM), BullMQ

---

## FLIPT Marketplace - Current State

### Location
- **Replit:** `replit.com/@teuqna/CryptoMarketplace`
- **Docs/Assets:** `C:\Users\PC\OneDrive\1 - Jono\businesses\FLIPT\`

### What's Built (~75-80% complete)
Core listing system, categories, multi-image galleries, search/filters, product detail pages, 5-tier authentication, reputation system, inspector badges, AI content moderation, user reporting + admin dashboard, manufacturer portal, escrow frontend, node network page, crypto payment UI, 110 seed listings, Tiffany Blue Shadcn/ui design.

### What's NOT Built (5 items)
1. User authentication (wallet-based auth)
2. Solana blockchain integration
3. Cryptocurrency payment processing
4. Backend escrow (multi-sig smart contract)
5. Node purchase backend (Metaplex Candy Machine)

### Existing David Flip Code
- `david_flip_automation/` - Python: script gen (GPT-4o-mini, 4 styles, 8 themes), enhanced v2 with persuasion framework, Flask approval UI, video creator (ElevenLabs + Dzine.ai/D-ID), webhook handler

---

## Hardware & Network Setup

- **Agent laptop:** Standalone Windows laptop (dedicated, isolated)
- **Phone:** NEW Android phone with NEW number (burner) for all internet
- **Internet:** Phone provides tethered connection to laptop (not home network)
- **Location:** User is in UAE - Emirates ID ties to everything
- **VPN:** MANDATORY on both phone and laptop at all times (ProtonVPN/Mullvad)
- **All accounts created through VPN** showing non-UAE IP

### Safety Requirements (NON-NEGOTIABLE)
1. Physical isolation - standalone Windows laptop
2. Network isolation - phone tethering, VPN always on
3. No financial access - domain-level blocking
4. Human-in-the-loop - ALL outbound actions through approval queue
5. Token budget caps - daily limits, prepaid only
6. Activity logging - every action in SQLite audit log
7. Kill switch - Telegram /kill + file-based (survives restarts)
8. Burner accounts - new email, new socials, VPN for creation
9. Encrypted credentials - AES, key in env var only
10. Prompt injection defense - all external content tagged + scanned

---

## Agent Architecture

**Decision:** Build our own (not OpenClaw). Safety-first, simpler, Python, no supply chain risk.

**Core loop:**
1. Receive command via Telegram
2. Send to LLM with available tools (model selected by router)
3. LLM responds with text or tool call
4. If tool: validate permissions → check if approval needed → execute → loop
5. If text: validate personality → return to user
6. Safety gates at every step (kill switch, budget, tool permissions)

**Multi-model routing (Ganzak framework):**
| Model | % | Tasks | Cost |
|-------|---|-------|------|
| Ollama (local) | 15% | Heartbeats, formatting | $0 |
| Haiku | 75% | Research, classification | ~$0.80/M |
| Sonnet | 10% | Social posts, scripts | Mid |
| Opus | 3-5% | Strategy, crisis | Premium |

**Cost targets:** Idle $0/day, Active ~$1/hour

---

## Build Phases

### Phase 1: Foundation (CURRENT) - "Tweet via Telegram approval"
Code written. Needs: API keys, Telegram bot, Twitter account, testing.

### Phase 2: Video Pipeline - "David Flip creates and posts videos"
Copy FRONTMAN video engine, build content agent, scheduler, budget tracking.

### Phase 3: Community - "David Flip runs Discord"
Discord bot, community agent, research agent, memory system.

### Phase 4: Full Operations - "System runs 24/7"
WhatsApp bridge, reporting agent, audit log, conflict detection, cache.

### Phase 5: Optimization - "Dial in costs"
Model escalation, session dumping, token calibration, worker agents.

---

## OpenClaw Research Summary

Full 970-line report: `research/OpenClaw-Full-Research-Report.md`

**Key takeaways for our design:**
- Tool loop architecture works (proven pattern)
- Multi-model routing cuts costs 97%
- Prompt injection is real (demonstrated attacks)
- Persistent memory can be poisoned
- Human-in-the-loop is essential
- Start narrow, expand slowly

**Ganzak's 9 rules:** Project isolation, master project as OS, project charters, no project ID = no work, conflict detection, conflicts logged, errors to messenger, severity levels, safety over speed.

---

## Next Steps
1. **Set up the phone** - VPN first, then create burner accounts (ProtonMail fresh, Twitter/X, Discord)
2. **Set up the laptop** - Python, Ollama, clone this project
3. **Create Telegram bot** via @BotFather
4. **Fill in .env** with real API keys
5. **Run Phase 1 end-to-end test** - `/tweet` → approve → post
6. **Then Phase 2** - Video pipeline from FRONTMAN
