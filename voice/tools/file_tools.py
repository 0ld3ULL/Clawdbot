"""
File Tools for DEVA - Read, edit, write, search code files.

These tools give DEVA the ability to directly modify game project code.
"""

import os
import re
import glob
import shutil
from datetime import datetime
from typing import Optional, List, Dict, Any
from dataclasses import dataclass


@dataclass
class ToolResult:
    """Result from a tool execution."""
    success: bool
    output: str
    error: Optional[str] = None


class FileTools:
    """
    File operations for DEVA.

    Safety features:
    - Creates backups before edits
    - Validates paths are within allowed directories
    - Logs all operations
    """

    def __init__(self, allowed_roots: List[str] = None, backup_dir: str = None):
        """
        Initialize file tools.

        Args:
            allowed_roots: List of allowed root directories (safety)
            backup_dir: Directory for backups before edits
        """
        self.allowed_roots = allowed_roots or []
        self.backup_dir = backup_dir or os.path.join(
            os.path.dirname(__file__), "..", "..", "data", "backups"
        )
        os.makedirs(self.backup_dir, exist_ok=True)
        self.operation_log = []

    def _validate_path(self, file_path: str) -> tuple[bool, str]:
        """Check if path is within allowed directories."""
        if not self.allowed_roots:
            return True, ""  # No restrictions if no roots specified

        abs_path = os.path.abspath(file_path)
        for root in self.allowed_roots:
            abs_root = os.path.abspath(root)
            if abs_path.startswith(abs_root):
                return True, ""

        return False, f"Path {file_path} is outside allowed directories"

    def _create_backup(self, file_path: str) -> Optional[str]:
        """Create a backup of a file before editing."""
        if not os.path.exists(file_path):
            return None

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.basename(file_path)
        backup_name = f"{timestamp}_{filename}"
        backup_path = os.path.join(self.backup_dir, backup_name)

        shutil.copy2(file_path, backup_path)
        return backup_path

    def _log_operation(self, operation: str, file_path: str, details: str = ""):
        """Log an operation for audit trail."""
        self.operation_log.append({
            "timestamp": datetime.now().isoformat(),
            "operation": operation,
            "file": file_path,
            "details": details
        })

    # === Tool Implementations ===

    def read_file(self, file_path: str, limit: int = None) -> ToolResult:
        """
        Read the contents of a file.

        Args:
            file_path: Path to the file to read
            limit: Optional line limit (for large files)

        Returns:
            ToolResult with file contents or error
        """
        valid, error = self._validate_path(file_path)
        if not valid:
            return ToolResult(success=False, output="", error=error)

        if not os.path.exists(file_path):
            return ToolResult(success=False, output="", error=f"File not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                if limit:
                    lines = []
                    for i, line in enumerate(f):
                        if i >= limit:
                            lines.append(f"\n... (truncated at {limit} lines)")
                            break
                        lines.append(line)
                    content = ''.join(lines)
                else:
                    content = f.read()

            self._log_operation("read", file_path, f"{len(content)} chars")
            return ToolResult(success=True, output=content)

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def write_file(self, file_path: str, content: str) -> ToolResult:
        """
        Write content to a file (creates or overwrites).

        Args:
            file_path: Path to the file
            content: Content to write

        Returns:
            ToolResult indicating success or failure
        """
        valid, error = self._validate_path(file_path)
        if not valid:
            return ToolResult(success=False, output="", error=error)

        try:
            # Create backup if file exists
            if os.path.exists(file_path):
                backup = self._create_backup(file_path)
                backup_msg = f" (backup: {os.path.basename(backup)})" if backup else ""
            else:
                backup_msg = " (new file)"
                # Create parent directories if needed
                os.makedirs(os.path.dirname(file_path), exist_ok=True)

            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)

            self._log_operation("write", file_path, f"{len(content)} chars{backup_msg}")
            return ToolResult(
                success=True,
                output=f"Successfully wrote {len(content)} characters to {file_path}{backup_msg}"
            )

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def edit_file(self, file_path: str, old_string: str, new_string: str,
                  replace_all: bool = False) -> ToolResult:
        """
        Edit a file by replacing old_string with new_string.

        Args:
            file_path: Path to the file to edit
            old_string: The text to replace
            new_string: The replacement text
            replace_all: Replace all occurrences (default: first only)

        Returns:
            ToolResult indicating success or failure
        """
        valid, error = self._validate_path(file_path)
        if not valid:
            return ToolResult(success=False, output="", error=error)

        if not os.path.exists(file_path):
            return ToolResult(success=False, output="", error=f"File not found: {file_path}")

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Check if old_string exists
            if old_string not in content:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"String not found in file. Make sure you're using the exact text including whitespace."
                )

            # Count occurrences
            count = content.count(old_string)
            if count > 1 and not replace_all:
                return ToolResult(
                    success=False,
                    output="",
                    error=f"Found {count} occurrences of the string. Use replace_all=True to replace all, or provide more context to make the match unique."
                )

            # Create backup
            backup = self._create_backup(file_path)

            # Perform replacement
            if replace_all:
                new_content = content.replace(old_string, new_string)
                replaced = count
            else:
                new_content = content.replace(old_string, new_string, 1)
                replaced = 1

            # Write back
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_content)

            backup_msg = f" (backup: {os.path.basename(backup)})" if backup else ""
            self._log_operation("edit", file_path, f"replaced {replaced} occurrence(s){backup_msg}")

            return ToolResult(
                success=True,
                output=f"Successfully replaced {replaced} occurrence(s) in {file_path}{backup_msg}"
            )

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def list_files(self, directory: str, pattern: str = "*", recursive: bool = True) -> ToolResult:
        """
        List files in a directory matching a pattern.

        Args:
            directory: Directory to search
            pattern: Glob pattern (e.g., "*.cs", "*.unity")
            recursive: Search subdirectories

        Returns:
            ToolResult with list of matching files
        """
        valid, error = self._validate_path(directory)
        if not valid:
            return ToolResult(success=False, output="", error=error)

        if not os.path.exists(directory):
            return ToolResult(success=False, output="", error=f"Directory not found: {directory}")

        try:
            if recursive:
                full_pattern = os.path.join(directory, "**", pattern)
                files = glob.glob(full_pattern, recursive=True)
            else:
                full_pattern = os.path.join(directory, pattern)
                files = glob.glob(full_pattern)

            # Sort by modification time (newest first)
            files = sorted(files, key=os.path.getmtime, reverse=True)

            # Format output
            output_lines = [f"Found {len(files)} files matching '{pattern}' in {directory}:"]
            for f in files[:100]:  # Limit to 100 files
                rel_path = os.path.relpath(f, directory)
                output_lines.append(f"  {rel_path}")

            if len(files) > 100:
                output_lines.append(f"  ... and {len(files) - 100} more")

            return ToolResult(success=True, output="\n".join(output_lines))

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def search_code(self, directory: str, pattern: str,
                    file_pattern: str = "*.cs",
                    context_lines: int = 2,
                    max_results: int = 20) -> ToolResult:
        """
        Search for text/regex in files.

        Args:
            directory: Directory to search
            pattern: Text or regex to search for
            file_pattern: File glob pattern (e.g., "*.cs")
            context_lines: Lines of context around matches
            max_results: Maximum number of results to return

        Returns:
            ToolResult with search results
        """
        valid, error = self._validate_path(directory)
        if not valid:
            return ToolResult(success=False, output="", error=error)

        if not os.path.exists(directory):
            return ToolResult(success=False, output="", error=f"Directory not found: {directory}")

        try:
            # Compile regex
            try:
                regex = re.compile(pattern, re.IGNORECASE)
            except re.error:
                # Fall back to literal search
                regex = re.compile(re.escape(pattern), re.IGNORECASE)

            # Find files
            full_pattern = os.path.join(directory, "**", file_pattern)
            files = glob.glob(full_pattern, recursive=True)

            results = []
            total_matches = 0

            for file_path in files:
                if total_matches >= max_results:
                    break

                try:
                    with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                        lines = f.readlines()

                    for i, line in enumerate(lines):
                        if regex.search(line):
                            total_matches += 1
                            if total_matches > max_results:
                                break

                            # Get context
                            start = max(0, i - context_lines)
                            end = min(len(lines), i + context_lines + 1)
                            context = []
                            for j in range(start, end):
                                prefix = ">>> " if j == i else "    "
                                context.append(f"{prefix}{j + 1}: {lines[j].rstrip()}")

                            rel_path = os.path.relpath(file_path, directory)
                            results.append({
                                "file": rel_path,
                                "line": i + 1,
                                "context": "\n".join(context)
                            })

                except Exception:
                    continue  # Skip files that can't be read

            # Format output
            if not results:
                return ToolResult(success=True, output=f"No matches found for '{pattern}' in {file_pattern} files")

            output_lines = [f"Found {total_matches} matches for '{pattern}':"]
            for r in results:
                output_lines.append(f"\n{r['file']}:{r['line']}")
                output_lines.append(r['context'])

            if total_matches >= max_results:
                output_lines.append(f"\n... (limited to {max_results} results)")

            return ToolResult(success=True, output="\n".join(output_lines))

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def get_file_info(self, file_path: str) -> ToolResult:
        """
        Get information about a file (size, modified time, etc.).

        Args:
            file_path: Path to the file

        Returns:
            ToolResult with file information
        """
        valid, error = self._validate_path(file_path)
        if not valid:
            return ToolResult(success=False, output="", error=error)

        if not os.path.exists(file_path):
            return ToolResult(success=False, output="", error=f"File not found: {file_path}")

        try:
            stat = os.stat(file_path)
            modified = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")

            # Count lines for text files
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    line_count = sum(1 for _ in f)
            except:
                line_count = None

            info = [
                f"File: {file_path}",
                f"Size: {stat.st_size:,} bytes",
                f"Modified: {modified}",
            ]
            if line_count is not None:
                info.append(f"Lines: {line_count:,}")

            return ToolResult(success=True, output="\n".join(info))

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def restore_backup(self, backup_name: str, target_path: str) -> ToolResult:
        """
        Restore a file from backup.

        Args:
            backup_name: Name of the backup file
            target_path: Path to restore to

        Returns:
            ToolResult indicating success or failure
        """
        backup_path = os.path.join(self.backup_dir, backup_name)

        if not os.path.exists(backup_path):
            return ToolResult(success=False, output="", error=f"Backup not found: {backup_name}")

        valid, error = self._validate_path(target_path)
        if not valid:
            return ToolResult(success=False, output="", error=error)

        try:
            shutil.copy2(backup_path, target_path)
            self._log_operation("restore", target_path, f"from {backup_name}")
            return ToolResult(success=True, output=f"Restored {backup_name} to {target_path}")

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def list_backups(self, limit: int = 20) -> ToolResult:
        """List recent backups."""
        try:
            backups = glob.glob(os.path.join(self.backup_dir, "*"))
            backups = sorted(backups, key=os.path.getmtime, reverse=True)[:limit]

            if not backups:
                return ToolResult(success=True, output="No backups found")

            output_lines = [f"Recent backups ({len(backups)}):"]
            for b in backups:
                name = os.path.basename(b)
                size = os.path.getsize(b)
                output_lines.append(f"  {name} ({size:,} bytes)")

            return ToolResult(success=True, output="\n".join(output_lines))

        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))


# Tool definitions for Claude API
FILE_TOOLS_SCHEMA = [
    {
        "name": "read_file",
        "description": "Read the contents of a file. Use this to examine code before making changes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to read"
                },
                "limit": {
                    "type": "integer",
                    "description": "Optional line limit for large files"
                }
            },
            "required": ["file_path"]
        }
    },
    {
        "name": "edit_file",
        "description": "Edit a file by replacing old_string with new_string. The old_string must match exactly (including whitespace). Creates a backup before editing.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file to edit"
                },
                "old_string": {
                    "type": "string",
                    "description": "The exact text to replace (must be unique in the file)"
                },
                "new_string": {
                    "type": "string",
                    "description": "The replacement text"
                },
                "replace_all": {
                    "type": "boolean",
                    "description": "Replace all occurrences (default: false, only replaces first)"
                }
            },
            "required": ["file_path", "old_string", "new_string"]
        }
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates the file if it doesn't exist, overwrites if it does. Creates a backup before overwriting.",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute path to the file"
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file"
                }
            },
            "required": ["file_path", "content"]
        }
    },
    {
        "name": "list_files",
        "description": "List files in a directory matching a pattern. Useful for finding files before reading/editing them.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory to search in"
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern (e.g., '*.cs', '*.unity'). Default: '*'"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "Search subdirectories (default: true)"
                }
            },
            "required": ["directory"]
        }
    },
    {
        "name": "search_code",
        "description": "Search for text or regex in code files. Returns matching lines with context.",
        "input_schema": {
            "type": "object",
            "properties": {
                "directory": {
                    "type": "string",
                    "description": "Directory to search in"
                },
                "pattern": {
                    "type": "string",
                    "description": "Text or regex pattern to search for"
                },
                "file_pattern": {
                    "type": "string",
                    "description": "File glob pattern (default: '*.cs')"
                },
                "context_lines": {
                    "type": "integer",
                    "description": "Lines of context around matches (default: 2)"
                }
            },
            "required": ["directory", "pattern"]
        }
    },
    {
        "name": "get_file_info",
        "description": "Get information about a file (size, modified time, line count).",
        "input_schema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file"
                }
            },
            "required": ["file_path"]
        }
    }
]
