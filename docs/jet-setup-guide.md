# Jet's Setup Guide — Claude Y, The Wall & GitHub

Hey Jet! Follow these steps IN ORDER. Don't skip ahead.
Copy and paste the commands EXACTLY as shown (the grey boxes).

If something goes wrong, screenshot the error and send it to Dad.

---

## PART 1: Install the Tools

You need 4 things installed. If you already have any of them, skip that step.

### Step 1 — Install Git

Git is what lets you upload/download code to GitHub.

1. Go to https://git-scm.com/download/win
2. Click the big download button
3. Run the installer
4. Just keep clicking **Next** on every screen (don't change anything)
5. Click **Install**
6. Click **Finish**

### Step 2 — Install Python

Python is the programming language The Wall runs on.

1. Go to https://www.python.org/downloads/
2. Click the big yellow **Download Python** button
3. Run the installer
4. **IMPORTANT: Tick the box that says "Add Python to PATH"** (bottom of the first screen)
5. Click **Install Now**
6. When it finishes, click **Close**

### Step 3 — Install Node.js

Node.js is what Claude Code runs on.

1. Go to https://nodejs.org
2. Click the **LTS** download button (the one that says "Recommended")
3. Run the installer
4. Keep clicking **Next** on every screen
5. Click **Install**
6. Click **Finish**

### Step 4 — Install GitHub CLI

This lets you log into GitHub from the terminal.

1. Go to https://cli.github.com
2. Click **Download for Windows**
3. Run the installer
4. Keep clicking **Next**, then **Install**, then **Finish**

---

## PART 2: Open a Terminal

Every command from here on is typed into a terminal.

1. Press the **Windows key** on your keyboard
2. Type **cmd**
3. Click **Command Prompt** (the black icon)

A black window will open. This is your terminal. Leave it open for all the steps below.

---

## PART 3: Install Claude Code

Paste this into the terminal and press **Enter**:

```
npm install -g @anthropic-ai/claude-code
```

Wait for it to finish (might take a minute). You'll see a bunch of text scroll by. When it stops and you get a new blank line with `C:\`, it's done.

---

## PART 4: Log Into GitHub

Paste this and press **Enter**:

```
gh auth login
```

It will ask you questions. Pick these answers:

1. **What account do you want to log into?** → Pick `GitHub.com` (press Enter)
2. **What is your preferred protocol?** → Pick `HTTPS` (press Enter)
3. **Authenticate Git with your GitHub credentials?** → Pick `Yes` (press Enter)
4. **How would you like to authenticate?** → Pick `Login with a web browser`

It will show you a code (like `ABCD-1234`). Then it opens your browser.

5. In the browser, log in with your **jetpackzack1** GitHub account
6. Paste in the code it showed you
7. Click **Authorize**
8. Go back to the terminal — it should say "Logged in as jetpackzack1"

---

## PART 5: Set Your Git Identity

This puts your name on your commits so people know who made the changes.

Paste these TWO commands one at a time (press Enter after each):

```
git config --global user.name "jetpackzack1"
```

```
git config --global user.email "REPLACE_WITH_YOUR_GITHUB_EMAIL"
```

**IMPORTANT:** Replace `REPLACE_WITH_YOUR_GITHUB_EMAIL` with the actual email address you used to sign up for GitHub. Keep the quotes.

---

## PART 6: Clone the Projects

"Cloning" means downloading the code from GitHub onto your computer.

### Clone The David Project (Dad's stuff)

Paste these commands one at a time:

```
mkdir C:\Projects
```

(If it says "already exists" that's fine, keep going)

```
cd C:\Projects
```

```
git clone https://github.com/0ld3ULL/the-david-project.git Clawdbot
```

Wait for it to finish. You should see "done" at the end.

### Clone Starvin Martian (your Unity project)

```
git clone https://github.com/playa3ull/starvin-martian.git StarvinMartian
```

Wait for it to finish.

Now you have two project folders:
- `C:\Projects\Clawdbot` — Dad's project (TDP)
- `C:\Projects\StarvinMartian` — Your Unity project

---

## PART 7: Set Up The Wall

The Wall lets Claude Y send the entire codebase to Google's Gemini AI for analysis. It can see ALL the code at once and find bugs, explain how things connect, etc.

### Step 1 — Create a Python virtual environment

Paste these one at a time:

```
cd C:\Projects\Clawdbot
```

```
python -m venv venv
```

(Wait for it — takes about 30 seconds, no output means it worked)

```
venv\Scripts\activate
```

Your terminal should now show `(venv)` at the start of the line. That means you're inside the virtual environment.

```
pip install httpx python-dotenv
```

Wait for it to install. You'll see "Successfully installed" when done.

### Step 2 — Add the Google API Key

The Wall uses Google's Gemini to analyze code. You need an API key.

**Option A — Get your own key (free):**

1. Go to https://aistudio.google.com/apikey
2. Sign in with a Google account
3. Click **Create API Key**
4. Copy the key (it looks like a long string of random letters and numbers)

**Option B — Ask Dad for his key**

Once you have the key, create the config file:

1. Open **Notepad**
2. Type this (replace the placeholder with your actual key):
   ```
   GOOGLE_API_KEY=paste_your_key_here
   ```
3. Click **File > Save As**
4. Navigate to `C:\Projects\Clawdbot`
5. In the **File name** box, type exactly: `.env`
6. In the **Save as type** dropdown, change it to **All Files (*.*)**
7. Click **Save**

**Why "All Files"?** If you don't change it, Notepad will save it as `.env.txt` which won't work.

### Step 3 — Test The Wall

Paste this:

```
cd C:\Projects\Clawdbot
```

```
venv\Scripts\python.exe voice/wall_python.py "What does main.py do?"
```

If The Wall is working, you'll see:
- `[Wall] Loaded context: XXX estimated tokens`
- `[Wall] Sending to Gemini...`
- Then a bunch of analysis text about what main.py does

If you get an error about the API key, double-check your `.env` file.

---

## PART 8: Launch Claude Y

### For Dad's project (TDP):

```
cd C:\Projects\Clawdbot
claude
```

### For Starvin Martian:

```
cd C:\Projects\StarvinMartian
claude
```

The first time you run `claude`, it will ask you to log in with an Anthropic account. Follow the prompts — it opens a browser.

Claude Y will automatically know which GitHub to push to based on which folder you launched it in:
- Launched in `Clawdbot` → pushes to **0ld3ULL** (Dad's GitHub)
- Launched in `StarvinMartian` → pushes to **playa3ull** (PLAYA3ULL GitHub)

---

## PART 9: Test That GitHub Push Works

Let's make sure you can push to both repos.

### Test 1 — The David Project

```
cd C:\Projects\Clawdbot
git status
```

This should show something like `On branch main` and `nothing to commit`. That means it's connected.

### Test 2 — Starvin Martian

```
cd C:\Projects\StarvinMartian
git status
```

Same thing — should show the branch name and no errors.

If either one gives you a permission error, your GitHub login from Part 4 might not have worked. Run `gh auth login` again.

---

## Quick Reference Card

Once everything is set up, this is all you need to remember:

| What | Command |
|------|---------|
| Open TDP project | `cd C:\Projects\Clawdbot && claude` |
| Open Starvin Martian | `cd C:\Projects\StarvinMartian && claude` |
| Use The Wall (from inside Claude) | Tell Claude: "take it to The Wall" |
| Generate memory brief | `python -m claude_memory brief` |
| Check git connection | `git status` |
| See what you changed | `git diff` |
| Update your local code | `git pull` |

---

## Something Went Wrong?

| Problem | Fix |
|---------|-----|
| `'git' is not recognized` | Restart your terminal. If still broken, reinstall Git (Step 1) |
| `'python' is not recognized` | Reinstall Python and make sure you tick "Add to PATH" |
| `'npm' is not recognized` | Restart your terminal. If still broken, reinstall Node.js |
| `'claude' is not recognized` | Run `npm install -g @anthropic-ai/claude-code` again |
| `'gh' is not recognized` | Restart your terminal. If still broken, reinstall GitHub CLI |
| Permission denied on git push | Run `gh auth login` again |
| Wall says "No API key found" | Check your `.env` file exists in `C:\Projects\Clawdbot` and has the key |
| Wall says "Rate limit" | Wait 60 seconds and try again (free tier has limits) |

---

*Last updated: 2026-02-11*
*Generated by Claude D for Jet (Claude Y)*
