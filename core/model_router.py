"""
Multi-model routing engine.

Routes tasks to the cheapest capable model, with auto-escalation on failure.
Based on Ganzak's 97% cost reduction framework.

Routing: Ollama (15%) → Haiku (75%) → Sonnet (10%) → Opus (3-5%)
"""

import os
import yaml
import logging
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Any

import anthropic
import openai

logger = logging.getLogger(__name__)


class ModelTier(Enum):
    LOCAL = "local"        # Ollama, $0
    CHEAP = "cheap"        # Haiku, ~$0.80/M input
    MID = "mid"            # Sonnet, ~$3/M input
    PREMIUM = "premium"    # Opus, ~$15/M input


@dataclass
class ModelConfig:
    provider: str    # "ollama", "anthropic", "openai"
    name: str        # Model identifier
    tier: ModelTier
    cost_in: float   # Per 1M input tokens
    cost_out: float  # Per 1M output tokens
    max_context: int


class ModelRouter:

    # Escalation chain: try cheaper models first
    ESCALATION_ORDER = [
        ModelTier.LOCAL, ModelTier.CHEAP, ModelTier.MID, ModelTier.PREMIUM
    ]

    def __init__(self, config_path: str = "config/models.yaml"):
        self.models: dict[ModelTier, ModelConfig] = {}
        self.task_routing: dict[str, ModelTier] = {}
        self.default_tier = ModelTier.CHEAP

        # Initialize API clients
        self._anthropic = None
        self._openai = None
        self._ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")

        self._load_config(config_path)
        self._init_clients()

    def _load_config(self, config_path: str):
        """Load model routing configuration from YAML."""
        path = Path(config_path)
        if not path.exists():
            logger.warning(f"Config not found at {config_path}, using defaults")
            self._load_defaults()
            return

        with open(path) as f:
            config = yaml.safe_load(f)

        # Load model definitions
        for tier_name, model_def in config.get("models", {}).items():
            tier = ModelTier(tier_name)
            self.models[tier] = ModelConfig(
                provider=model_def["provider"],
                name=model_def["name"],
                tier=tier,
                cost_in=model_def.get("cost_per_1m_input", 0),
                cost_out=model_def.get("cost_per_1m_output", 0),
                max_context=model_def.get("max_context", 8192),
            )

        # Load task routing
        for task, tier_name in config.get("task_routing", {}).items():
            self.task_routing[task] = ModelTier(tier_name)

        self.default_tier = ModelTier(config.get("default_tier", "cheap"))

    def _load_defaults(self):
        """Fallback defaults if no config file."""
        self.models = {
            ModelTier.CHEAP: ModelConfig(
                provider="anthropic",
                name="claude-3-5-haiku-20241022",
                tier=ModelTier.CHEAP,
                cost_in=0.80, cost_out=4.00,
                max_context=200000,
            ),
            ModelTier.MID: ModelConfig(
                provider="anthropic",
                name="claude-sonnet-4-20250514",
                tier=ModelTier.MID,
                cost_in=3.00, cost_out=15.00,
                max_context=200000,
            ),
        }

    def _init_clients(self):
        """Initialize API clients from environment variables."""
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            self._anthropic = anthropic.Anthropic(api_key=api_key)

        openai_key = os.environ.get("OPENAI_API_KEY")
        if openai_key:
            self._openai = openai.OpenAI(api_key=openai_key)

    def select_model(self, task_type: str) -> ModelConfig:
        """Select the appropriate model for a task type."""
        tier = self.task_routing.get(task_type, self.default_tier)
        model = self.models.get(tier)
        if model is None:
            # Fall back to cheapest available
            for t in self.ESCALATION_ORDER:
                if t in self.models:
                    return self.models[t]
            raise RuntimeError("No models configured")
        return model

    def escalate(self, current_model: ModelConfig) -> ModelConfig | None:
        """Get the next model up in the escalation chain."""
        current_idx = self.ESCALATION_ORDER.index(current_model.tier)
        for tier in self.ESCALATION_ORDER[current_idx + 1:]:
            if tier in self.models:
                return self.models[tier]
        return None  # No higher model available

    async def invoke(self, model: ModelConfig,
                     messages: list[dict],
                     tools: list[dict] | None = None,
                     max_tokens: int = 4096) -> dict:
        """
        Invoke a model and return the response.

        Args:
            model: The model configuration to use
            messages: List of message dicts with 'role' and 'content'
            tools: Optional tool definitions for the model
            max_tokens: Maximum tokens in response

        Returns:
            dict with 'content', 'tool_calls', 'usage' keys
        """
        if model.provider == "anthropic":
            return await self._invoke_anthropic(model, messages, tools, max_tokens)
        elif model.provider == "ollama":
            return await self._invoke_ollama(model, messages, max_tokens)
        elif model.provider == "openai":
            return await self._invoke_openai(model, messages, tools, max_tokens)
        else:
            raise ValueError(f"Unknown provider: {model.provider}")

    async def _invoke_anthropic(self, model: ModelConfig,
                                messages: list[dict],
                                tools: list[dict] | None,
                                max_tokens: int) -> dict:
        """Call Anthropic API."""
        if not self._anthropic:
            raise RuntimeError("Anthropic API key not configured")

        # Separate system messages from conversation
        system_parts = []
        conversation = []
        for msg in messages:
            if msg["role"] == "system":
                system_parts.append(msg["content"])
            else:
                conversation.append(msg)

        kwargs = {
            "model": model.name,
            "max_tokens": max_tokens,
            "messages": conversation,
        }
        if system_parts:
            kwargs["system"] = "\n\n".join(system_parts)
        if tools:
            kwargs["tools"] = tools

        response = self._anthropic.messages.create(**kwargs)

        # Parse response
        tool_calls = []
        text_content = ""
        for block in response.content:
            if block.type == "text":
                text_content += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "arguments": block.input,
                })

        return {
            "content": text_content,
            "tool_calls": tool_calls,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens,
                "total_tokens": (response.usage.input_tokens
                                 + response.usage.output_tokens),
            },
            "model": model.name,
            "stop_reason": response.stop_reason,
        }

    async def _invoke_ollama(self, model: ModelConfig,
                             messages: list[dict],
                             max_tokens: int) -> dict:
        """Call local Ollama model."""
        try:
            import ollama as ollama_lib
            client = ollama_lib.Client(host=self._ollama_host)

            response = client.chat(
                model=model.name,
                messages=messages,
            )

            # Ollama doesn't provide exact token counts, estimate
            prompt_tokens = sum(len(m.get("content", "")) // 4 for m in messages)
            completion_tokens = len(response["message"]["content"]) // 4

            return {
                "content": response["message"]["content"],
                "tool_calls": [],
                "usage": {
                    "input_tokens": prompt_tokens,
                    "output_tokens": completion_tokens,
                    "total_tokens": prompt_tokens + completion_tokens,
                },
                "model": model.name,
                "stop_reason": "end_turn",
            }
        except Exception as e:
            logger.warning(f"Ollama call failed: {e}")
            raise

    async def _invoke_openai(self, model: ModelConfig,
                             messages: list[dict],
                             tools: list[dict] | None,
                             max_tokens: int) -> dict:
        """Call OpenAI API."""
        if not self._openai:
            raise RuntimeError("OpenAI API key not configured")

        kwargs = {
            "model": model.name,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            # Convert Anthropic tool format to OpenAI format
            kwargs["tools"] = [
                {"type": "function", "function": t} for t in tools
            ]

        response = self._openai.chat.completions.create(**kwargs)
        choice = response.choices[0]

        tool_calls = []
        if choice.message.tool_calls:
            import json
            for tc in choice.message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments),
                })

        return {
            "content": choice.message.content or "",
            "tool_calls": tool_calls,
            "usage": {
                "input_tokens": response.usage.prompt_tokens,
                "output_tokens": response.usage.completion_tokens,
                "total_tokens": response.usage.total_tokens,
            },
            "model": model.name,
            "stop_reason": choice.finish_reason,
        }
