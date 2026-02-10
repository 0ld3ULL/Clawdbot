"""
Wall Mode for Python codebases — The David Project edition.

"Taking it to the wall" — load the full codebase (or targeted files) into
Gemini's 1M context window for cross-file analysis that no single-file
reader can do.

Usage from CLI:
    python voice/wall_python.py "Is the Oprah wiring correct?"
    python voice/wall_python.py --subsystem agents "How does Oprah work?"
    python voice/wall_python.py --files main.py,agents/operations_agent.py "Check the wiring"

Usage from Claude Code (just run via Bash tool):
    python voice/wall_python.py "Your question here"

Usage from Python:
    from voice.wall_python import wall_analyze
    print(wall_analyze("Is there any broken wiring in main.py?"))
"""

import argparse
import fnmatch
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Set

# Ensure project root is on sys.path so imports work when run as a script
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

# Project root (auto-detected: go up from this file's directory)
PROJECT_ROOT = Path(__file__).resolve().parent.parent

# Extensions to collect
CODE_EXTENSIONS = [".py"]
CONFIG_EXTENSIONS = [".yaml", ".yml"]
TEMPLATE_EXTENSIONS = [".html"]

# Directories to skip entirely
EXCLUDE_DIRS = {
    ".git", "venv", "__pycache__", "node_modules", "Stuff",
    "ProjectsLumina", "data", ".mypy_cache", ".pytest_cache",
    "nul", "transcripts", "docs",
}

# Files to skip
EXCLUDE_FILES = {
    "nul",
}

# Subsystem detection patterns (used for --subsystem filter)
SUBSYSTEM_PATTERNS: Dict[str, List[str]] = {
    "personality": [r"personality", r"david_flip", r"oprah", r"echo", r"deva"],
    "agents": [r"agents/", r"operations_agent", r"content_agent", r"research_agent", r"interview_agent"],
    "core": [r"core/", r"engine", r"approval", r"audit", r"kill_switch", r"scheduler", r"memory", r"token_budget", r"model_router"],
    "tools": [r"tools/", r"twitter_tool", r"tiktok_tool", r"video_distributor", r"chart"],
    "dashboard": [r"dashboard/", r"flask"],
    "voice": [r"voice/", r"wall", r"gemini"],
    "video": [r"video_pipeline/", r"elevenlabs", r"hedra", r"ffmpeg"],
    "telegram": [r"telegram_bot"],
    "security": [r"security/", r"git_guard", r"credential", r"sanitizer", r"two_factor"],
    "claude_memory": [r"claude_memory/"],
}

# Approximate tokens per character
CHARS_PER_TOKEN = 3.5


# ---------------------------------------------------------------------------
# Collector
# ---------------------------------------------------------------------------

def _should_exclude_dir(dirname: str) -> bool:
    return dirname in EXCLUDE_DIRS or dirname.startswith(".")


def _detect_subsystems(relative_path: str, content: str) -> List[str]:
    """Detect which subsystems a file belongs to."""
    text = (relative_path + " " + content[:500]).lower()
    found = []
    for subsystem, patterns in SUBSYSTEM_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, text, re.IGNORECASE):
                found.append(subsystem)
                break
    return found


def collect_project(
    subsystem: Optional[str] = None,
    files_filter: Optional[List[str]] = None,
    include_templates: bool = True,
    include_config: bool = True,
    max_tokens: int = 800_000,
) -> str:
    """
    Collect the TDP Python codebase into a formatted context string.

    Args:
        subsystem:  Filter to files matching a subsystem (e.g. "agents", "core")
        files_filter: Explicit list of relative file paths to include (overrides subsystem)
        include_templates: Include .html dashboard templates
        include_config: Include .yaml/.yml config files
        max_tokens: Token budget (default 800K — Gemini Flash safe limit)

    Returns:
        Formatted context string ready for Gemini.
    """
    extensions = list(CODE_EXTENSIONS)
    if include_config:
        extensions.extend(CONFIG_EXTENSIONS)
    if include_templates:
        extensions.extend(TEMPLATE_EXTENSIONS)

    collected = []  # (relative_path, content, subsystems, tokens)
    total_tokens = 0

    # If explicit files requested, only collect those
    if files_filter:
        for rel_path in files_filter:
            full_path = PROJECT_ROOT / rel_path
            if not full_path.exists():
                # Try without leading slash
                full_path = PROJECT_ROOT / rel_path.lstrip("/\\")
            if full_path.exists():
                try:
                    content = full_path.read_text(encoding="utf-8", errors="ignore")
                    tokens = int(len(content) / CHARS_PER_TOKEN)
                    subsystems = _detect_subsystems(rel_path, content)
                    collected.append((rel_path, content, subsystems, tokens))
                    total_tokens += tokens
                except Exception:
                    pass
    else:
        # Walk the project
        for root, dirs, filenames in os.walk(PROJECT_ROOT):
            # Prune excluded directories
            dirs[:] = [d for d in dirs if not _should_exclude_dir(d)]

            for filename in filenames:
                if filename in EXCLUDE_FILES:
                    continue
                if not any(filename.endswith(ext) for ext in extensions):
                    continue

                file_path = Path(root) / filename
                rel_path = str(file_path.relative_to(PROJECT_ROOT)).replace("\\", "/")

                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception:
                    continue

                subsystems = _detect_subsystems(rel_path, content)

                # Filter by subsystem if requested
                if subsystem and subsystem.lower() not in [s.lower() for s in subsystems]:
                    continue

                tokens = int(len(content) / CHARS_PER_TOKEN)

                # Check token budget
                if total_tokens + tokens > max_tokens:
                    break

                collected.append((rel_path, content, subsystems, tokens))
                total_tokens += tokens

    # Sort: main.py first, then alphabetical
    collected.sort(key=lambda x: (x[0] != "main.py", x[0]))

    # Format
    lines = []
    lines.append("=" * 80)
    lines.append("WALL MODE: The David Project (Python Codebase)")
    lines.append("=" * 80)
    lines.append("")
    if subsystem:
        lines.append(f"Subsystem filter: {subsystem}")
    if files_filter:
        lines.append(f"Files filter: {', '.join(files_filter)}")
    lines.append(f"Files: {len(collected)}")
    lines.append(f"Estimated tokens: {total_tokens:,}")
    lines.append("")

    # File index
    lines.append("-" * 80)
    lines.append("FILE INDEX")
    lines.append("-" * 80)
    for i, (rel_path, _, subsystems, tokens) in enumerate(collected, 1):
        sub_str = f" [{', '.join(subsystems)}]" if subsystems else ""
        lines.append(f"{i:3}. {rel_path} ({tokens:,} tok){sub_str}")
    lines.append("")

    # File contents
    lines.append("=" * 80)
    lines.append("FILE CONTENTS")
    lines.append("=" * 80)
    for rel_path, content, subsystems, _ in collected:
        lines.append("")
        lines.append("-" * 80)
        lines.append(f"FILE: {rel_path}")
        lines.append(f"SUBSYSTEMS: {', '.join(subsystems) or 'none'}")
        lines.append("-" * 80)
        lines.append("")
        lines.append(content)

    lines.append("")
    lines.append("=" * 80)
    lines.append("END OF WALL")
    lines.append("=" * 80)

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Analyze
# ---------------------------------------------------------------------------

def wall_analyze(
    question: str,
    subsystem: Optional[str] = None,
    files: Optional[List[str]] = None,
    max_output_tokens: int = 8000,
) -> str:
    """
    Load the TDP codebase into Gemini and ask a question.

    Args:
        question: What to analyze
        subsystem: Optional subsystem filter (e.g. "agents", "core", "dashboard")
        files: Optional explicit file list (e.g. ["main.py", "agents/operations_agent.py"])
        max_output_tokens: Max response tokens from Gemini

    Returns:
        Gemini's analysis text
    """
    from dotenv import load_dotenv
    load_dotenv()
    from voice.gemini_client import GeminiClient

    # Collect context
    context = collect_project(subsystem=subsystem, files_filter=files)

    # Count tokens for user info
    est_tokens = int(len(context) / CHARS_PER_TOKEN)
    print(f"[Wall] Loaded context: {est_tokens:,} estimated tokens")

    # Build analysis prompt
    system_prompt = (
        "You are analysing The David Project (TDP) — a Python AI agent system.\n"
        "The full codebase (or a targeted subset) is loaded below.\n\n"
        "RULES:\n"
        "1. Reference specific files and line numbers\n"
        "2. Be direct and concise\n"
        "3. If you find issues, state them clearly with fixes\n"
        "4. Cross-reference between files — that's the whole point of Wall Mode\n"
        "5. If something looks correct, say so\n"
    )

    full_prompt = f"{system_prompt}\n\n{context}\n\n=== QUESTION ===\n{question}\n\n=== ANALYSIS ==="

    # Send to Gemini
    print("[Wall] Sending to Gemini...")
    client = GeminiClient()
    response = client.analyze(
        context="",  # We built the full prompt ourselves
        question=full_prompt,
        max_tokens=max_output_tokens,
    )
    print(f"[Wall] Done — {response.input_tokens:,} input, {response.output_tokens:,} output tokens ({response.provider})")

    return response.text


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Wall Mode for The David Project — load codebase into Gemini for analysis",
        usage='python voice/wall_python.py "Your question here"',
    )
    parser.add_argument("question", help="Question to ask about the codebase")
    parser.add_argument(
        "--subsystem", "-s",
        help="Filter to a subsystem (agents, core, dashboard, personality, tools, voice, video, telegram, security, claude_memory)",
    )
    parser.add_argument(
        "--files", "-f",
        help="Comma-separated list of specific files to analyze (e.g. main.py,agents/operations_agent.py)",
    )
    parser.add_argument(
        "--tokens", "-t",
        type=int,
        default=8000,
        help="Max output tokens from Gemini (default: 8000)",
    )

    args = parser.parse_args()

    files_list = args.files.split(",") if args.files else None

    result = wall_analyze(
        question=args.question,
        subsystem=args.subsystem,
        files=files_list,
        max_output_tokens=args.tokens,
    )

    print("\n" + "=" * 80)
    print("WALL MODE ANALYSIS")
    print("=" * 80 + "\n")
    print(result)


if __name__ == "__main__":
    main()
