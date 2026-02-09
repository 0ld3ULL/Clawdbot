"""
Tool registration and access control.

Implements deny-by-default: tools only available if explicitly
listed in the project's allowed_tools config.
"""

import yaml
import logging
from pathlib import Path
from core.engine import ToolDefinition, ToolRegistry

logger = logging.getLogger(__name__)


def load_tool_permissions(config_path: str = "config/tools.yaml") -> dict:
    """Load tool permission config."""
    path = Path(config_path)
    if not path.exists():
        logger.warning(f"Tool config not found: {config_path}")
        return {}

    with open(path) as f:
        config = yaml.safe_load(f)

    return config


def get_approval_required_tools(config_path: str = "config/tools.yaml") -> list[str]:
    """Get list of tools that always require human approval."""
    config = load_tool_permissions(config_path)
    return config.get("approval_required", [])


def get_project_allowed_tools(project_id: str,
                              config_path: str = "config/tools.yaml") -> list[str]:
    """Get allowed tools for a specific project."""
    config = load_tool_permissions(config_path)
    projects = config.get("projects", {})
    project = projects.get(project_id, {})
    return project.get("allowed_tools", [])


def build_registry(twitter_tool=None, tiktok_tool=None) -> ToolRegistry:
    """
    Build the tool registry with all available tools.
    Tools are registered but access is controlled per-project.
    """
    registry = ToolRegistry()
    approval_required = get_approval_required_tools()

    # --- Twitter Tools ---
    if twitter_tool:
        async def tweet_execute(**kwargs):
            return await twitter_tool.execute(kwargs)

        registry.register(ToolDefinition(
            name="twitter_post",
            description=(
                "Post a tweet on Twitter/X as David Flip. "
                "Provide the tweet text (max 280 chars). "
                "Optionally include media_path for an image/video attachment."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "Tweet text (max 280 characters)",
                    },
                    "media_path": {
                        "type": "string",
                        "description": "Optional path to media file",
                    },
                },
                "required": ["text"],
            },
            requires_approval="twitter_post" in approval_required,
            execute_fn=tweet_execute,
        ))

        async def thread_execute(**kwargs):
            return await twitter_tool.execute({"action": "thread", **kwargs})

        registry.register(ToolDefinition(
            name="twitter_thread",
            description=(
                "Post a thread of tweets on Twitter/X as David Flip. "
                "Provide a list of tweet texts (max 5, each max 280 chars)."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "tweets": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "List of tweet texts for the thread",
                    },
                },
                "required": ["tweets"],
            },
            requires_approval="twitter_thread" in approval_required,
            execute_fn=thread_execute,
        ))

        async def reply_execute(**kwargs):
            return await twitter_tool.execute({"action": "reply", **kwargs})

        registry.register(ToolDefinition(
            name="twitter_reply",
            description=(
                "Reply to a tweet on Twitter/X as David Flip. "
                "Provide the tweet_id to reply to and the reply text."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "tweet_id": {
                        "type": "string",
                        "description": "ID of the tweet to reply to",
                    },
                    "text": {
                        "type": "string",
                        "description": "Reply text (max 280 characters)",
                    },
                },
                "required": ["tweet_id", "text"],
            },
            requires_approval="twitter_reply" in approval_required,
            execute_fn=reply_execute,
        ))

    # --- Brave Search ---
    async def brave_search_execute(**kwargs):
        # Placeholder - will be implemented when Brave API key is available
        return {"error": "Brave Search not yet configured"}

    registry.register(ToolDefinition(
        name="brave_search",
        description="Search the web using Brave Search API. Returns relevant results.",
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of results (default 5)",
                },
            },
            "required": ["query"],
        },
        requires_approval=False,
        execute_fn=brave_search_execute,
    ))

    # --- TikTok Tool ---
    if tiktok_tool:
        async def tiktok_execute(**kwargs):
            return await tiktok_tool.execute(kwargs)

        registry.register(ToolDefinition(
            name="tiktok_post",
            description=(
                "Post a video to TikTok as David Flip. "
                "Currently operates in manual mode: prepares video + caption "
                "for operator to upload. Provide video_path and script."
            ),
            parameters={
                "type": "object",
                "properties": {
                    "video_path": {
                        "type": "string",
                        "description": "Path to the video file to post",
                    },
                    "script": {
                        "type": "string",
                        "description": "Video script (used for caption generation)",
                    },
                    "theme_title": {
                        "type": "string",
                        "description": "Optional theme title for caption",
                    },
                },
                "required": ["video_path", "script"],
            },
            requires_approval="tiktok_post" in approval_required,
            execute_fn=tiktok_execute,
        ))

    # --- File Tools (memory only) ---
    async def read_file_execute(**kwargs):
        path = kwargs.get("path", "")
        # Safety: only allow reading from data/memory/
        if not path.startswith("data/memory/"):
            return {"error": "Can only read files from data/memory/"}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return {"content": f.read()}
        except FileNotFoundError:
            return {"error": f"File not found: {path}"}

    registry.register(ToolDefinition(
        name="read_file",
        description="Read a file from the agent's memory directory.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path (must be under data/memory/)",
                },
            },
            "required": ["path"],
        },
        requires_approval=False,
        execute_fn=read_file_execute,
    ))

    async def write_file_memory_execute(**kwargs):
        path = kwargs.get("path", "")
        content = kwargs.get("content", "")
        if not path.startswith("data/memory/"):
            return {"error": "Can only write to data/memory/"}
        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            return {"status": "written", "path": path}
        except Exception as e:
            return {"error": str(e)}

    registry.register(ToolDefinition(
        name="write_file_memory",
        description="Write a file to the agent's memory directory.",
        parameters={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "File path (must be under data/memory/)",
                },
                "content": {
                    "type": "string",
                    "description": "Content to write",
                },
            },
            "required": ["path", "content"],
        },
        requires_approval=False,
        execute_fn=write_file_memory_execute,
    ))

    return registry
