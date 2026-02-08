# DEVA Setup Guide - David's Laptop

Follow these steps exactly to set up DEVA on the new Windows 11 laptop.

---

## Step 1: Install Claude Code

1. Open **Microsoft Edge** (or Chrome)
2. Go to: https://claude.ai/download
3. Click **Download for Windows**
4. Run the installer when it downloads
5. Follow the prompts to complete installation
6. When done, you'll see Claude Code in your Start menu

---

## Step 2: Open PowerShell

1. Click the **Start** button
2. Type: `powershell`
3. Click **Windows PowerShell** (NOT the (x86) version)
4. A blue window will open - this is PowerShell

---

## Step 3: Install Git

1. In PowerShell, paste this command and press Enter:
```powershell
winget install Git.Git
```

2. Wait for it to finish (about 1 minute)
3. **Close PowerShell** and **open a new PowerShell window** (so Git works)

---

## Step 4: Create Projects Folder

1. In PowerShell, paste this and press Enter:
```powershell
mkdir C:\Projects
cd C:\Projects
```

---

## Step 5: Clone the Clawdbot Repository

1. In PowerShell, paste this and press Enter:
```powershell
git clone https://github.com/0ld3ULL/Clawdbot.git
cd Clawdbot
```

2. Wait for download to complete

---

## Step 6: Install Python

1. In PowerShell, paste this and press Enter:
```powershell
winget install Python.Python.3.12
```

2. Wait for installation (about 2 minutes)
3. **Close PowerShell** and **open a new PowerShell window**

---

## Step 7: Create Python Virtual Environment

1. In PowerShell, paste these commands one at a time:
```powershell
cd C:\Projects\Clawdbot
python -m venv venv
.\venv\Scripts\Activate.ps1
```

2. You should see `(venv)` at the start of your prompt

**If you get an error about "running scripts is disabled":**
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
.\venv\Scripts\Activate.ps1
```

---

## Step 8: Install Python Dependencies

1. With `(venv)` active, paste this:
```powershell
pip install -r requirements.txt
```

2. Wait for all packages to install (3-5 minutes)

---

## Step 9: Install DEVA Voice Dependencies

1. Still in PowerShell with `(venv)` active:
```powershell
pip install RealtimeSTT torch torchaudio
```

2. This takes a while (5-10 minutes) - it's downloading AI models

---

## Step 10: Create the .env File

1. In PowerShell, type:
```powershell
notepad .env
```

2. Notepad will open and ask "Create new file?" - click **Yes**

3. Paste this content into Notepad:
```
# DEVA Configuration

# Anthropic API (for Claude)
ANTHROPIC_API_KEY=your_anthropic_key_here

# Google AI (for Wall Mode - Gemini)
GOOGLE_API_KEY=your_google_key_here

# ElevenLabs (for voice)
ELEVENLABS_API_KEY=your_elevenlabs_key_here
```

4. Replace the placeholder values with your actual API keys
5. Save the file (Ctrl+S) and close Notepad

---

## Step 11: Test DEVA

1. In PowerShell with `(venv)` active:
```powershell
cd C:\Projects\Clawdbot
python voice/deva_voice.py
```

2. You should see:
```
Initializing DEVA...
  Loading speech recognition...
  Gemini: google API ready
  Voice: Veronica
Ready!
```

3. Speak into your microphone to test
4. Say "quit" to exit

---

## Step 12: Set Up Claude Code Access

1. Open **Claude Code** from the Start menu
2. It will ask you to log in - use your Anthropic account
3. Once logged in, type:
```
cd C:\Projects\Clawdbot
```

4. Then type:
```
Read Memory.md
```

5. Claude now has full context about the project!

---

## Quick Reference

**Start DEVA (voice assistant):**
```powershell
cd C:\Projects\Clawdbot
.\venv\Scripts\Activate.ps1
python voice/deva_voice.py
```

**Start Claude Code with project context:**
```powershell
cd C:\Projects\Clawdbot
claude
```
Then: `Read Memory.md`

**Update from GitHub:**
```powershell
cd C:\Projects\Clawdbot
git pull
```

---

## Troubleshooting

**"python is not recognized"**
- Close PowerShell, open new one, try again
- Or run: `winget install Python.Python.3.12`

**"git is not recognized"**
- Close PowerShell, open new one, try again
- Or run: `winget install Git.Git`

**Microphone not working**
- Check Windows Settings > Privacy > Microphone
- Make sure apps can access microphone

**ElevenLabs voice not working**
- Check your API key in .env file
- Make sure you have credits in your ElevenLabs account

---

## Discord Link to Send Yourself

Copy this message to send via Discord:

```
DEVA Setup Link:
https://github.com/0ld3ULL/Clawdbot

Open DEVA-SETUP.md and follow the steps.
```
