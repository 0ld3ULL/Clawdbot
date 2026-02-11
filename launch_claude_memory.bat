@echo off
title Claude Memory Boot
cd /d "C:\Projects\Clawdbot"

echo ============================================
echo   Claude Memory System - Session Boot
echo ============================================
echo.

echo [1/2] Generating memory brief...
"venv\Scripts\python.exe" -m claude_memory brief
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo WARNING: Brief generation failed. Launching Claude Code anyway...
    echo You may need to run: python -m claude_memory brief
    echo.
    pause
)

echo.
echo [2/2] Launching Claude Code with memory loaded...
echo.

"%APPDATA%\npm\claude.cmd"
