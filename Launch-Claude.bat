@echo off
title The David Project - Claude Code
cd /d C:\Projects\TheDavidProject 2>nul || cd /d C:\Projects\Clawdbot

echo ============================================
echo   The David Project - Starting Claude Code
echo ============================================
echo.

:: Generate fresh memory brief
echo Generating memory brief...
call venv\Scripts\activate.bat
python -m claude_memory brief
echo.

:: Launch Claude Code
echo Launching Claude Code...
echo Claude will automatically read CLAUDE.md + your memory brief.
echo.
claude

pause
