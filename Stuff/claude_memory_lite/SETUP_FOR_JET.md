# Setting Up Claude Y (Young3ULL)

Claude Y is Claude Code with persistent memory. It remembers your decisions,
your bugs, your ideas, and your architecture across sessions. After a few days
of use, it knows your project like a teammate.

---

## Step 1: Install Claude Code (one time only)

1. Download and install **Node.js** from https://nodejs.org
   - Click the big green button, install with all defaults

2. Open **Command Prompt** (press Win+R, type `cmd`, press Enter)

3. Paste this and press Enter:
   ```
   npm install -g @anthropic-ai/claude-code
   ```

4. You need one of these for Claude to work:
   - **Claude Pro subscription** ($20/month) — easiest
   - **Claude Max subscription** ($100/month) — unlimited
   - **Anthropic API key** (pay-per-use) — from console.anthropic.com

5. You also need **Python** installed (for the memory system)
   - Download from https://python.org if you don't have it
   - Make sure "Add to PATH" is ticked during install

---

## Step 2: Copy Files Into Your Project

Your game project folder probably looks something like:
```
C:\Games\MyGame\
├── Assets\
├── Packages\
├── ProjectSettings\
└── ...
```

Copy these into it:

1. Copy the **entire `claude_memory_lite` folder** into your project root
2. **Rename it** from `claude_memory_lite` to `claude_memory`
3. Copy **`CLAUDE_TEMPLATE.md`** into your project root, rename to **`CLAUDE.md`**

Your project should now look like:
```
C:\Games\MyGame\
├── Assets\
├── Packages\
├── ProjectSettings\
├── claude_memory\          <-- renamed from claude_memory_lite
│   ├── __init__.py
│   ├── __main__.py
│   ├── store.py
│   ├── brief.py
│   └── first_run.py
├── CLAUDE.md               <-- renamed from CLAUDE_TEMPLATE.md
└── ...
```

---

## Step 3: Edit CLAUDE.md

Open `CLAUDE.md` in your project root and fill in:

1. Replace `[PROJECT NAME]` with your game's name
2. Replace the `[DESCRIBE THE GAME HERE...]` section with details about your game:
   - What kind of game is it?
   - What Unity version?
   - What platform(s)?
   - How far along is it?

Everything else in the file is already set up — Claude will read it automatically.

---

## Step 4: Run First-Time Setup

Open Command Prompt, navigate to your project, and run:

```
cd C:\Games\MyGame
python claude_memory\first_run.py
```

This pre-loads Claude with essential memories (who you are, that this is a production codebase, etc.). You can edit `first_run.py` before running it to add your own — there are commented-out examples inside for architecture, networking, UI, etc.

---

## Step 5: Update .gitignore

Open your `.gitignore` file and add these lines at the bottom:

```
# Claude Y memory (personal, not source code)
data/claude_memory.db
data/claude_memory.db-wal
data/claude_memory.db-shm
claude_brief.md
claude_memory/__pycache__/
```

This keeps the memory database and session brief out of Git.

---

## Step 6: Set Up Desktop Launcher

1. Copy **`Launch Claude Y.bat`** to your **Desktop**
2. Right-click it, click **Edit**
3. Find this line near the top:
   ```
   set PROJECT_DIR=C:\Users\Jet\UnityProject
   ```
4. Change it to your actual project path, for example:
   ```
   set PROJECT_DIR=C:\Games\MyGame
   ```
5. Save and close

---

## Step 7: First Session

1. **Double-click `Launch Claude Y.bat`** on your Desktop
2. Claude Y starts and loads your memories
3. For your first session, tell Claude:

   > "Read through the project structure and save key architecture decisions as memories.
   > Look at the main systems — player controller, UI, networking, whatever the big ones are —
   > and save what you learn."

4. This is the brain dump session. Let Claude explore and build up its memory.
   After this session, it will know your codebase.

---

## Daily Use

**Starting:** Double-click `Launch Claude Y.bat` — it auto-loads memories.

**During work:** Just work normally. Claude will proactively save memories when you make
decisions or it discovers architecture. You can also say:
- "Remember that" — Claude saves the current context
- "Save that as a decision" — Claude saves with decision category

**Ending:** Before you close, Claude should:
1. Save a session summary
2. Regenerate the brief
3. Remind you of next steps

If Claude forgets, just say: "End of session — save memories and generate brief"

---

## Quick Reference

| Command | What it does |
|---------|-------------|
| `python -m claude_memory brief` | Generate session brief |
| `python -m claude_memory status` | See memory stats |
| `python -m claude_memory add decision 8 "title" "content"` | Save a memory |
| `python -m claude_memory search "networking"` | Search memories |
| `python -m claude_memory delete 5` | Delete memory #5 |

| Category | Use for |
|----------|---------|
| decision | "We chose X over Y because..." |
| architecture | "The inventory system uses ScriptableObjects" |
| bug | "Physics breaks below 30fps" |
| idea | "Maybe add a crafting system" |
| context | "The UI should feel like Zelda BOTW" |
| person | Who's working on the project |
| task | What's being worked on |
| session | End-of-session summaries |

| Significance | Meaning | Stays in brief |
|---|---|---|
| 8-10 | Critical | Forever |
| 5-7 | Important | 30 days |
| 1-4 | Minor | 7 days |
