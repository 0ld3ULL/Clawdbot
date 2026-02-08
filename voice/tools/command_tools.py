"""
Command Tools for DEVA - Run shell commands, git operations, builds.

Safety features:
- Command allowlist
- Timeout protection
- Output capture
"""

import os
import subprocess
import shlex
from typing import Optional, List
from dataclasses import dataclass
from datetime import datetime


@dataclass
class CommandResult:
    """Result from a command execution."""
    success: bool
    stdout: str
    stderr: str
    return_code: int
    error: Optional[str] = None


class CommandTools:
    """
    Command execution for DEVA.

    Safety features:
    - Allowlist of safe commands
    - Timeout protection
    - Working directory restrictions
    """

    # Commands that are always safe
    SAFE_COMMANDS = {
        # Git (read-only)
        "git status", "git log", "git diff", "git branch", "git show",
        "git ls-files", "git blame",
        # Git (write - careful)
        "git add", "git commit", "git checkout", "git pull", "git push",
        # File operations (read-only)
        "ls", "dir", "cat", "head", "tail", "find", "grep", "wc",
        # Build tools
        "dotnet build", "dotnet test", "msbuild",
        # Unity (command line)
        "Unity", "unity",
        # Windows start command (launch apps)
        "start",
        # Python
        "python", "pip",
        # Node
        "npm", "node",
    }

    # Commands that are NEVER allowed
    BLOCKED_COMMANDS = {
        "rm -rf", "del /f", "format", "mkfs",
        "shutdown", "reboot", "halt",
        "curl", "wget",  # No downloading
        "chmod", "chown",  # No permission changes
        "sudo", "su",  # No privilege escalation
        "eval", "exec",  # No code execution
    }

    def __init__(self, allowed_directories: List[str] = None, timeout: int = 60):
        """
        Initialize command tools.

        Args:
            allowed_directories: Directories where commands can run
            timeout: Default command timeout in seconds
        """
        self.allowed_directories = allowed_directories or []
        self.timeout = timeout
        self.command_log = []

    def _validate_command(self, command: str) -> tuple[bool, str]:
        """Check if command is allowed."""
        command_lower = command.lower()

        # Check blocked commands
        for blocked in self.BLOCKED_COMMANDS:
            if blocked in command_lower:
                return False, f"Command contains blocked operation: {blocked}"

        # Check if it starts with a safe command
        is_safe = False
        for safe in self.SAFE_COMMANDS:
            if command_lower.startswith(safe.lower()):
                is_safe = True
                break

        if not is_safe:
            return False, f"Command not in allowlist. Safe commands: git, ls, dotnet, python, etc."

        return True, ""

    def _validate_directory(self, directory: str) -> tuple[bool, str]:
        """Check if directory is allowed."""
        if not self.allowed_directories:
            return True, ""  # No restrictions

        abs_dir = os.path.abspath(directory)
        for allowed in self.allowed_directories:
            abs_allowed = os.path.abspath(allowed)
            if abs_dir.startswith(abs_allowed):
                return True, ""

        return False, f"Directory {directory} is outside allowed paths"

    def _log_command(self, command: str, working_dir: str, result: CommandResult):
        """Log command execution."""
        self.command_log.append({
            "timestamp": datetime.now().isoformat(),
            "command": command,
            "working_dir": working_dir,
            "return_code": result.return_code,
            "success": result.success
        })

    def run(self, command: str, working_dir: str = None,
            timeout: int = None, capture_output: bool = True) -> CommandResult:
        """
        Run a shell command.

        Args:
            command: Command to run
            working_dir: Working directory (default: current)
            timeout: Timeout in seconds (default: class timeout)
            capture_output: Capture stdout/stderr

        Returns:
            CommandResult with output and status
        """
        working_dir = working_dir or os.getcwd()
        timeout = timeout or self.timeout

        # Validate command
        valid, error = self._validate_command(command)
        if not valid:
            return CommandResult(
                success=False,
                stdout="",
                stderr="",
                return_code=-1,
                error=error
            )

        # Validate directory
        valid, error = self._validate_directory(working_dir)
        if not valid:
            return CommandResult(
                success=False,
                stdout="",
                stderr="",
                return_code=-1,
                error=error
            )

        try:
            # Run command
            result = subprocess.run(
                command,
                shell=True,
                cwd=working_dir,
                capture_output=capture_output,
                text=True,
                timeout=timeout
            )

            cmd_result = CommandResult(
                success=result.returncode == 0,
                stdout=result.stdout or "",
                stderr=result.stderr or "",
                return_code=result.returncode
            )

            self._log_command(command, working_dir, cmd_result)
            return cmd_result

        except subprocess.TimeoutExpired:
            return CommandResult(
                success=False,
                stdout="",
                stderr="",
                return_code=-1,
                error=f"Command timed out after {timeout} seconds"
            )
        except Exception as e:
            return CommandResult(
                success=False,
                stdout="",
                stderr="",
                return_code=-1,
                error=str(e)
            )

    def git_status(self, repo_path: str) -> CommandResult:
        """Get git status for a repository."""
        return self.run("git status --porcelain", working_dir=repo_path)

    def git_diff(self, repo_path: str, file_path: str = None) -> CommandResult:
        """Get git diff for a file or entire repo."""
        if file_path:
            return self.run(f"git diff {file_path}", working_dir=repo_path)
        return self.run("git diff", working_dir=repo_path)

    def git_log(self, repo_path: str, count: int = 10) -> CommandResult:
        """Get recent git commits."""
        return self.run(f"git log --oneline -n {count}", working_dir=repo_path)

    def git_add(self, repo_path: str, files: str = ".") -> CommandResult:
        """Stage files for commit."""
        return self.run(f"git add {files}", working_dir=repo_path)

    def git_commit(self, repo_path: str, message: str) -> CommandResult:
        """Create a commit."""
        # Escape message for shell
        safe_message = message.replace('"', '\\"')
        return self.run(f'git commit -m "{safe_message}"', working_dir=repo_path)


# Tool definitions for Claude API
COMMAND_TOOLS_SCHEMA = [
    {
        "name": "run_command",
        "description": "Run a shell command. Only safe commands are allowed (git, ls, dotnet, python, etc.). Dangerous commands (rm -rf, curl, sudo) are blocked.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The command to run"
                },
                "working_dir": {
                    "type": "string",
                    "description": "Working directory for the command"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Timeout in seconds (default: 60)"
                }
            },
            "required": ["command"]
        }
    },
    {
        "name": "git_status",
        "description": "Get the git status of a repository (modified, staged, untracked files).",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the git repository"
                }
            },
            "required": ["repo_path"]
        }
    },
    {
        "name": "git_diff",
        "description": "Get the git diff showing changes in the repository.",
        "input_schema": {
            "type": "object",
            "properties": {
                "repo_path": {
                    "type": "string",
                    "description": "Path to the git repository"
                },
                "file_path": {
                    "type": "string",
                    "description": "Optional: specific file to diff"
                }
            },
            "required": ["repo_path"]
        }
    }
]
