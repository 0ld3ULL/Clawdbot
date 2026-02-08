"""
Wall Mode - Load entire Unity/Unreal projects into context.

"Taking it to the wall" - holistic codebase analysis for game development.
Game bugs often live in system interactions, not individual files.

Usage:
    collector = WallCollector(project_path)
    context = collector.collect()  # Full project
    context = collector.collect(subsystem="voice")  # Just voice system
    context = collector.collect(query="player falls through floor")  # Relevant files
"""

import os
import re
import fnmatch
from pathlib import Path
from typing import Optional, List, Dict, Set
from dataclasses import dataclass, field


# Approximate tokens per character (conservative estimate for code)
CHARS_PER_TOKEN = 3.5

# Context window limits
# NOTE: These are EFFECTIVE limits based on research, not marketing claims.
# Llama 4 Scout's 10M is not usable - accuracy drops to 15.6% after 256K.
# See research/wall-mode-model-research.md for details.
CONTEXT_LIMITS = {
    "gemini_flash": 800_000,     # 800K safe limit (1M claimed, leave margin)
    "gemini_flash_free": 200_000,  # 200K free tier limit (250K/min quota)
    "gemini_pro": 900_000,       # 900K safe limit (1-2M claimed)
    "claude": 180_000,           # 180K safe limit (200K claimed)
    "llama4_scout": 200_000,     # 200K EFFECTIVE limit (10M is marketing)
}

# Default model for Wall Mode
# Use "gemini_flash_free" for free tier, "gemini_flash" for paid
DEFAULT_WALL_MODEL = "gemini_flash"  # Paid tier - 800K tokens


@dataclass
class FileInfo:
    """Information about a collected file."""
    path: str
    relative_path: str
    content: str
    lines: int
    chars: int
    tokens: int  # Estimated
    subsystems: List[str] = field(default_factory=list)


@dataclass
class CollectionResult:
    """Result of collecting project files."""
    files: List[FileInfo]
    total_files: int
    total_lines: int
    total_chars: int
    total_tokens: int
    subsystems_found: Set[str]
    excluded_paths: List[str]
    context_text: str  # Formatted for LLM


class WallCollector:
    """
    Collect and structure Unity/Unreal project code for LLM analysis.

    Features:
    - Smart filtering (excludes packages, third-party code)
    - Subsystem detection (voice, networking, UI, physics, etc.)
    - Token budgeting (fits within context limits)
    - Query-based relevance filtering
    """

    # Paths to exclude (packages, third-party, generated)
    EXCLUDE_PATTERNS = [
        "*/Packages/*",
        "*/Library/*",
        "*/Temp/*",
        "*/Logs/*",
        "*/obj/*",
        "*/bin/*",
        "*/.git/*",
        "*/TextMesh Pro/*",
        "*/Photon/*",
        "*/PUN/*",
        "*/Mirror/*",
        "*/EPIC GAMES/*",
        "*/EOS/*",
        "*/Plugins/*",
        "*/ThirdParty/*",
        "*/External/*",
        "*/Samples~/*",
        "*/Editor Default Resources/*",
        "*~/*",  # Unity backup files
    ]

    # Paths to prioritize (project-specific code)
    PRIORITY_PATTERNS = [
        "*/PLAYAverse/*",
        "*/Scripts/*",
        "*/Game/*",
        "*/Core/*",
        "*/Gameplay/*",
    ]

    # Subsystem detection patterns
    SUBSYSTEM_PATTERNS = {
        "voice": [
            r"voice", r"audio", r"microphone", r"speaker", r"photonvoice",
            r"elevenlabs", r"tts", r"stt", r"speech"
        ],
        "networking": [
            r"photon", r"network", r"rpc", r"sync", r"multiplayer",
            r"lobby", r"room", r"player.*view", r"pun"
        ],
        "player": [
            r"player", r"character", r"avatar", r"controller",
            r"rigidbody.*player", r"firstperson", r"thirdperson"
        ],
        "seating": [
            r"seat", r"sit", r"chair", r"bench", r"sitting"
        ],
        "ui": [
            r"canvas", r"button", r"panel", r"menu", r"hud",
            r"ui.*manager", r"interface"
        ],
        "camera": [
            r"camera", r"cinemachine", r"freelook", r"orbit"
        ],
        "animation": [
            r"animator", r"animation", r"ik", r"blend", r"state.*machine"
        ],
        "rendering": [
            r"shader", r"material", r"urp", r"render", r"light",
            r"post.*process", r"graphics"
        ],
        "physics": [
            r"collider", r"rigidbody", r"trigger", r"raycast",
            r"physics", r"gravity"
        ],
        "events": [
            r"event", r"stage", r"concert", r"performance", r"show"
        ],
    }

    def __init__(self, project_path: str, engine: str = "unity"):
        """
        Initialize collector for a game project.

        Args:
            project_path: Root path of the Unity/Unreal project
            engine: "unity" or "unreal"
        """
        self.project_path = Path(project_path)
        self.engine = engine.lower()

        # Validate project path
        if not self.project_path.exists():
            raise ValueError(f"Project path does not exist: {project_path}")

        # Detect engine if not specified
        if self.engine == "unity":
            self.code_extensions = [".cs"]
            self.scene_extensions = [".unity", ".prefab"]
            self.assets_dir = self.project_path / "Assets"
        elif self.engine == "unreal":
            self.code_extensions = [".cpp", ".h", ".hpp"]
            self.scene_extensions = [".umap", ".uasset"]
            self.assets_dir = self.project_path / "Source"
        else:
            raise ValueError(f"Unknown engine: {engine}")

    def _should_exclude(self, path: Path) -> bool:
        """Check if path should be excluded."""
        path_str = str(path).replace("\\", "/")
        for pattern in self.EXCLUDE_PATTERNS:
            if fnmatch.fnmatch(path_str, pattern):
                return True
        return False

    def _is_priority(self, path: Path) -> bool:
        """Check if path is high priority (project-specific code)."""
        path_str = str(path).replace("\\", "/")
        for pattern in self.PRIORITY_PATTERNS:
            if fnmatch.fnmatch(path_str, pattern):
                return True
        return False

    def _detect_subsystems(self, content: str, filename: str) -> List[str]:
        """Detect which subsystems a file belongs to."""
        subsystems = []
        text = (content + " " + filename).lower()

        for subsystem, patterns in self.SUBSYSTEM_PATTERNS.items():
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    subsystems.append(subsystem)
                    break

        return subsystems

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count for text."""
        return int(len(text) / CHARS_PER_TOKEN)

    def _matches_query(self, content: str, filename: str, query: str) -> bool:
        """Check if file content is relevant to a query."""
        if not query:
            return True

        # Simple keyword matching
        query_words = query.lower().split()
        text = (content + " " + filename).lower()

        # File matches if it contains any query word
        for word in query_words:
            if word in text:
                return True

        return False

    def collect(
        self,
        subsystem: Optional[str] = None,
        query: Optional[str] = None,
        max_tokens: int = CONTEXT_LIMITS[DEFAULT_WALL_MODEL],
        include_scenes: bool = False
    ) -> CollectionResult:
        """
        Collect project files for analysis.

        Args:
            subsystem: Filter to specific subsystem (voice, networking, etc.)
            query: Filter by relevance to query string
            max_tokens: Maximum tokens to collect
            include_scenes: Include scene/prefab files

        Returns:
            CollectionResult with files and formatted context
        """
        files: List[FileInfo] = []
        excluded_paths: List[str] = []
        subsystems_found: Set[str] = set()

        # Determine extensions to search
        extensions = self.code_extensions.copy()
        if include_scenes:
            extensions.extend(self.scene_extensions)

        # Walk the assets directory
        search_path = self.assets_dir if self.assets_dir.exists() else self.project_path

        for root, dirs, filenames in os.walk(search_path):
            root_path = Path(root)

            # Skip excluded directories
            if self._should_exclude(root_path):
                excluded_paths.append(str(root_path))
                dirs.clear()  # Don't descend into excluded dirs
                continue

            for filename in filenames:
                file_path = root_path / filename

                # Check extension
                if not any(filename.endswith(ext) for ext in extensions):
                    continue

                # Check exclusion
                if self._should_exclude(file_path):
                    excluded_paths.append(str(file_path))
                    continue

                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                except Exception as e:
                    excluded_paths.append(f"{file_path} (read error: {e})")
                    continue

                # Detect subsystems
                file_subsystems = self._detect_subsystems(content, filename)
                subsystems_found.update(file_subsystems)

                # Filter by subsystem if specified
                if subsystem and subsystem.lower() not in [s.lower() for s in file_subsystems]:
                    continue

                # Filter by query if specified
                if query and not self._matches_query(content, filename, query):
                    continue

                # Calculate metrics
                lines = content.count("\n") + 1
                chars = len(content)
                tokens = self._estimate_tokens(content)

                relative_path = str(file_path.relative_to(self.project_path))

                files.append(FileInfo(
                    path=str(file_path),
                    relative_path=relative_path,
                    content=content,
                    lines=lines,
                    chars=chars,
                    tokens=tokens,
                    subsystems=file_subsystems
                ))

        # Sort by priority (project code first) then by path
        files.sort(key=lambda f: (not self._is_priority(Path(f.path)), f.relative_path))

        # Apply token budget
        budget_files: List[FileInfo] = []
        current_tokens = 0

        for file_info in files:
            if current_tokens + file_info.tokens <= max_tokens:
                budget_files.append(file_info)
                current_tokens += file_info.tokens
            else:
                excluded_paths.append(f"{file_info.relative_path} (token budget)")

        # Calculate totals
        total_lines = sum(f.lines for f in budget_files)
        total_chars = sum(f.chars for f in budget_files)
        total_tokens = sum(f.tokens for f in budget_files)

        # Format context for LLM
        context_text = self._format_context(
            budget_files,
            subsystem=subsystem,
            query=query,
            total_tokens=total_tokens
        )

        return CollectionResult(
            files=budget_files,
            total_files=len(budget_files),
            total_lines=total_lines,
            total_chars=total_chars,
            total_tokens=total_tokens,
            subsystems_found=subsystems_found,
            excluded_paths=excluded_paths,
            context_text=context_text
        )

    def _format_context(
        self,
        files: List[FileInfo],
        subsystem: Optional[str] = None,
        query: Optional[str] = None,
        total_tokens: int = 0
    ) -> str:
        """Format collected files as context for LLM."""
        lines = []

        # Header
        lines.append("=" * 80)
        lines.append(f"WALL MODE: {self.project_path.name}")
        lines.append("=" * 80)
        lines.append("")

        if subsystem:
            lines.append(f"Subsystem filter: {subsystem}")
        if query:
            lines.append(f"Query filter: {query}")

        lines.append(f"Files: {len(files)}")
        lines.append(f"Estimated tokens: {total_tokens:,}")
        lines.append("")

        # File index
        lines.append("-" * 80)
        lines.append("FILE INDEX")
        lines.append("-" * 80)

        for i, file_info in enumerate(files, 1):
            subsys_str = f" [{', '.join(file_info.subsystems)}]" if file_info.subsystems else ""
            lines.append(f"{i:3}. {file_info.relative_path}{subsys_str}")

        lines.append("")

        # File contents
        lines.append("=" * 80)
        lines.append("FILE CONTENTS")
        lines.append("=" * 80)

        for file_info in files:
            lines.append("")
            lines.append("-" * 80)
            lines.append(f"FILE: {file_info.relative_path}")
            lines.append(f"LINES: {file_info.lines} | SUBSYSTEMS: {', '.join(file_info.subsystems) or 'none'}")
            lines.append("-" * 80)
            lines.append("")
            lines.append(file_info.content)

        lines.append("")
        lines.append("=" * 80)
        lines.append("END OF WALL")
        lines.append("=" * 80)

        return "\n".join(lines)

    def get_subsystem_summary(self) -> Dict[str, int]:
        """Get a summary of files per subsystem."""
        result = self.collect(max_tokens=CONTEXT_LIMITS["llama4_scout"])

        summary = {}
        for subsystem in result.subsystems_found:
            count = sum(1 for f in result.files if subsystem in f.subsystems)
            summary[subsystem] = count

        return dict(sorted(summary.items(), key=lambda x: -x[1]))


def wall(
    project_path: str,
    subsystem: Optional[str] = None,
    query: Optional[str] = None,
    engine: str = "unity"
) -> CollectionResult:
    """
    Quick function to collect project files.

    Examples:
        # Full project
        result = wall("D:/Games/Amphitheatre")

        # Just voice system
        result = wall("D:/Games/Amphitheatre", subsystem="voice")

        # Query-based
        result = wall("D:/Games/Amphitheatre", query="player falls through floor")
    """
    collector = WallCollector(project_path, engine=engine)
    return collector.collect(subsystem=subsystem, query=query)


if __name__ == "__main__":
    import sys

    # Default to Amphitheatre project
    project = sys.argv[1] if len(sys.argv) > 1 else r"D:\Games\PLAYA3ULL GAMES games\Amphitheatre\Amphitheatre"

    print(f"Analyzing: {project}")
    print()

    collector = WallCollector(project)

    # Get subsystem summary
    print("Subsystem Summary:")
    print("-" * 40)
    summary = collector.get_subsystem_summary()
    for subsystem, count in summary.items():
        print(f"  {subsystem}: {count} files")

    print()

    # Collect full project
    result = collector.collect()
    print(f"Full Project:")
    print(f"  Files: {result.total_files}")
    print(f"  Lines: {result.total_lines:,}")
    print(f"  Tokens: {result.total_tokens:,}")
    print(f"  Subsystems: {', '.join(sorted(result.subsystems_found))}")
