"""
Core Agent Engine - The Tool Loop.

This is the fundamental execution cycle:
1. Receive task + context
2. Send to LLM with available tools
3. LLM responds with text OR tool call
4. If tool call: validate → (approve if outbound) → execute → loop back to 2
5. If text response: return to caller
6. Safety gates at every step

Inspired by OpenClaw's proven architecture but with safety-first design.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from core.model_router import ModelRouter, ModelConfig
from core.approval_queue import ApprovalQueue
from core.token_budget import TokenBudgetManager
from core.audit_log import AuditLog
from core.kill_switch import KillSwitch, KillSwitchActive

logger = logging.getLogger(__name__)


@dataclass
class ToolDefinition:
    """Definition of a tool the agent can use."""
    name: str
    description: str
    parameters: dict          # JSON Schema for parameters
    requires_approval: bool = False
    execute_fn: Any = None    # Callable that executes the tool


@dataclass
class AgentContext:
    """State for a single agent execution run."""
    project_id: str
    session_id: str
    agent_id: str = ""
    task_type: str = "simple_qa"
    messages: list = field(default_factory=list)
    total_tokens: int = 0
    total_cost: float = 0.0
    model_used: str = ""


class ToolRegistry:
    """Registry of available tools with per-project access control."""

    def __init__(self):
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition):
        """Register a tool."""
        self._tools[tool.name] = tool

    def get(self, name: str) -> ToolDefinition | None:
        return self._tools.get(name)

    def get_allowed(self, allowed_names: list[str]) -> list[ToolDefinition]:
        """Get tools filtered by allowed list."""
        return [t for name, t in self._tools.items() if name in allowed_names]

    def get_tool_schemas(self, allowed_names: list[str]) -> list[dict]:
        """Get tool schemas in Anthropic format for LLM."""
        schemas = []
        for tool in self.get_allowed(allowed_names):
            schemas.append({
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.parameters,
            })
        return schemas

    async def execute(self, name: str, arguments: dict) -> Any:
        """Execute a tool by name."""
        tool = self._tools.get(name)
        if not tool:
            return f"Error: Tool '{name}' not found"
        if not tool.execute_fn:
            return f"Error: Tool '{name}' has no execute function"
        try:
            result = await tool.execute_fn(**arguments)
            return result
        except Exception as e:
            logger.error(f"Tool execution failed: {name} - {e}")
            return f"Error executing {name}: {str(e)}"


class AgentEngine:
    """
    Core agent engine implementing the tool loop with safety gates.
    """

    def __init__(self,
                 model_router: ModelRouter,
                 tool_registry: ToolRegistry,
                 approval_queue: ApprovalQueue,
                 token_budget: TokenBudgetManager,
                 audit_log: AuditLog,
                 kill_switch: KillSwitch,
                 allowed_tools: list[str] | None = None):
        self.router = model_router
        self.tools = tool_registry
        self.queue = approval_queue
        self.budget = token_budget
        self.audit = audit_log
        self.kill = kill_switch
        self.allowed_tools = allowed_tools or []

    async def run(self, context: AgentContext, task: str,
                  system_prompt: str = "",
                  max_iterations: int = 20) -> str:
        """
        Execute the tool loop.

        Returns the final text response, or a status message if
        waiting for approval or blocked by safety.
        """
        # Safety gate 1: Kill switch
        try:
            self.kill.check_or_raise()
        except KillSwitchActive as e:
            return f"[KILLED] System is shut down: {e}"

        # Safety gate 2: Budget check
        if not self.budget.has_budget(context.project_id):
            self.audit.log(
                context.project_id, "block", "budget",
                "Budget exhausted", agent_id=context.agent_id
            )
            return "[BLOCKED] Daily token budget exhausted."

        # Build messages
        if system_prompt:
            context.messages.insert(0, {
                "role": "system",
                "content": system_prompt,
            })

        context.messages.append({"role": "user", "content": task})

        # Get tool schemas for this project
        tool_schemas = self.tools.get_tool_schemas(self.allowed_tools)

        for iteration in range(max_iterations):
            # Kill switch check every iteration
            try:
                self.kill.check_or_raise()
            except KillSwitchActive:
                return "[KILLED] System shut down during execution."

            # Budget check every iteration
            if not self.budget.has_budget(context.project_id):
                return "[BLOCKED] Budget exhausted during execution."

            # Select model
            model = self.router.select_model(context.task_type)
            context.model_used = model.name

            # Call LLM
            try:
                response = await self.router.invoke(
                    model, context.messages,
                    tools=tool_schemas if tool_schemas else None,
                )
            except Exception as e:
                # Try escalating to a more capable model
                logger.warning(f"Model {model.name} failed: {e}")
                next_model = self.router.escalate(model)
                if next_model:
                    logger.info(f"Escalating to {next_model.name}")
                    try:
                        response = await self.router.invoke(
                            next_model, context.messages,
                            tools=tool_schemas if tool_schemas else None,
                        )
                        model = next_model
                        context.model_used = model.name
                    except Exception as e2:
                        self.audit.log(
                            context.project_id, "reject", "llm",
                            f"All models failed: {e2}",
                            agent_id=context.agent_id, success=False
                        )
                        return f"[ERROR] All models failed: {e2}"
                else:
                    self.audit.log(
                        context.project_id, "reject", "llm",
                        f"Model failed, no escalation: {e}",
                        agent_id=context.agent_id, success=False
                    )
                    return f"[ERROR] Model failed: {e}"

            # Track tokens and cost
            usage = response.get("usage", {})
            tokens_in = usage.get("input_tokens", 0)
            tokens_out = usage.get("output_tokens", 0)
            cost = self.budget.calculate_cost(model.name, tokens_in, tokens_out)

            context.total_tokens += tokens_in + tokens_out
            context.total_cost += cost

            self.budget.record_usage(
                context.project_id, model.name,
                tokens_in, tokens_out, cost,
                task_type=context.task_type,
                agent_id=context.agent_id,
            )

            # Process tool calls
            if response.get("tool_calls"):
                for tool_call in response["tool_calls"]:
                    tool_name = tool_call["name"]
                    tool_args = tool_call["arguments"]

                    # Check if tool is allowed
                    if tool_name not in self.allowed_tools:
                        context.messages.append({
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [tool_call],
                        })
                        context.messages.append({
                            "role": "tool",
                            "tool_use_id": tool_call["id"],
                            "content": f"[BLOCKED] Tool '{tool_name}' not allowed.",
                        })
                        self.audit.log(
                            context.project_id, "block", "tool",
                            f"Blocked tool: {tool_name}",
                            agent_id=context.agent_id
                        )
                        continue

                    # Check if tool requires approval
                    tool_def = self.tools.get(tool_name)
                    if tool_def and tool_def.requires_approval:
                        approval_id = self.queue.submit(
                            project_id=context.project_id,
                            agent_id=context.agent_id,
                            action_type=tool_name,
                            action_data=tool_args,
                            context_summary=task[:200],
                            cost_estimate=context.total_cost,
                        )
                        self.audit.log(
                            context.project_id, "info", "approval",
                            f"Queued for approval: {tool_name}",
                            details=json.dumps(tool_args)[:500],
                            agent_id=context.agent_id,
                        )
                        return (
                            f"[AWAITING APPROVAL #{approval_id}] "
                            f"Action: {tool_name}\n"
                            f"Preview: {self.queue.format_preview(self.queue.get_by_id(approval_id))}"
                        )

                    # Execute tool
                    self.audit.log(
                        context.project_id, "info", "tool",
                        f"Executing: {tool_name}",
                        agent_id=context.agent_id,
                    )
                    result = await self.tools.execute(tool_name, tool_args)

                    # Add tool result to conversation
                    context.messages.append({
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [tool_call],
                    })
                    context.messages.append({
                        "role": "tool",
                        "tool_use_id": tool_call["id"],
                        "content": str(result),
                    })

            else:
                # Text response - we're done
                final_text = response.get("content", "")

                self.audit.log(
                    context.project_id, "info", "response",
                    "Agent completed",
                    details=final_text[:200],
                    agent_id=context.agent_id,
                    tokens=context.total_tokens,
                    cost=context.total_cost,
                    model=context.model_used,
                )

                return final_text

        # Max iterations reached
        self.audit.log(
            context.project_id, "warn", "engine",
            f"Max iterations ({max_iterations}) reached",
            agent_id=context.agent_id,
        )
        return "[MAX_ITERATIONS] Agent reached iteration limit."
