@echo off
title Claude Y - Jet's Dev Session
color 0A

echo.
echo   =============================================
echo      CLAUDE Y  (Young3ULL)
echo      Jet's Game Dev Partner
echo   =============================================
echo.

REM === CHANGE THIS to Jet's project folder ===
set PROJECT_DIR=C:\Users\Jet\UnityProject
REM ============================================

cd /d "%PROJECT_DIR%"
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Could not find project folder: %PROJECT_DIR%
    echo.
    echo Right-click this file, click Edit, and fix the PROJECT_DIR path.
    pause
    exit /b 1
)

echo   Project: %CD%
echo.

REM Check if claude_memory folder exists
if not exist "claude_memory\__init__.py" (
    echo   WARNING: claude_memory folder not found!
    echo   Copy claude_memory_lite into this project and rename to claude_memory
    echo   See SETUP_FOR_JET.md for instructions.
    echo.
)

REM Check if CLAUDE.md exists
if not exist "CLAUDE.md" (
    echo   WARNING: CLAUDE.md not found!
    echo   Copy CLAUDE_TEMPLATE.md to this folder as CLAUDE.md
    echo   and fill in your project details.
    echo.
)

REM Generate fresh session brief
echo   Loading memories...
python -m claude_memory brief >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    REM Count memories
    for /f "tokens=2 delims=:" %%a in ('python -m claude_memory status 2^>nul ^| findstr "Total"') do (
        echo   Memories loaded:%%a
    )
) else (
    echo   No memories yet. Run first_run.py to seed initial memories.
    echo   python claude_memory\first_run.py
)

echo.
echo   Starting Claude Code...
echo   Type /help for commands
echo   =============================================
echo.

claude

echo.
echo   =============================================
echo   Session ended.
echo.
echo   Did you save your memories?
echo   Run: python -m claude_memory brief
echo   =============================================
echo.
pause
