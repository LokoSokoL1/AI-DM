"""Execute validated tool calls through the central tool registry."""

import inspect
import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from dungeon_manager.ai.tool_call_parser import ToolCall
from dungeon_manager.tools.registry import ToolRegistry


logger = logging.getLogger("DungeonManager")


class ToolExecutionStatus(str, Enum):
    """Possible outcomes when executing a validated tool call."""

    SUCCESS = "success"
    UNKNOWN_TOOL = "unknown_tool"
    INVALID_ARGUMENTS = "invalid_arguments"
    TOOL_FAILURE = "tool_failure"


@dataclass(frozen=True)
class ToolExecutionResult:
    """Typed result of one tool-execution attempt."""

    status: ToolExecutionStatus
    output: Any = None
    error: Optional[str] = None


class ToolExecutor:
    """Execute one validated tool call without parsing, retries, or AI access."""

    def __init__(self, tool_registry: Optional[ToolRegistry] = None):
        self.tool_registry = (
            tool_registry if tool_registry is not None else ToolRegistry()
        )

    def execute(self, tool_call: ToolCall) -> ToolExecutionResult:
        """Resolve and execute a validated tool call exactly once."""

        tools = self.tool_registry.get_tools()
        tool = tools.get(tool_call.tool)

        if tool is None:
            logger.warning("Unknown tool requested: %s", tool_call.tool)
            return ToolExecutionResult(
                status=ToolExecutionStatus.UNKNOWN_TOOL,
                error=f"Unknown tool: {tool_call.tool}",
            )

        try:
            tool_signature = inspect.signature(tool)
        except (TypeError, ValueError):
            logger.exception(
                "Could not inspect arguments for tool: %s",
                tool_call.tool,
            )
            return ToolExecutionResult(
                status=ToolExecutionStatus.TOOL_FAILURE,
                error=f"Tool execution failed: {tool_call.tool}",
            )

        try:
            tool_signature.bind(**tool_call.arguments)
        except TypeError as error:
            logger.warning(
                "Invalid arguments for tool %s: %s",
                tool_call.tool,
                error,
            )
            return ToolExecutionResult(
                status=ToolExecutionStatus.INVALID_ARGUMENTS,
                error=f"Invalid arguments for tool: {tool_call.tool}",
            )

        try:
            output = self.tool_registry.execute(
                tool_call.tool,
                **tool_call.arguments,
            )
        except Exception:
            logger.exception("Tool execution failed: %s", tool_call.tool)
            return ToolExecutionResult(
                status=ToolExecutionStatus.TOOL_FAILURE,
                error=f"Tool execution failed: {tool_call.tool}",
            )

        return ToolExecutionResult(
            status=ToolExecutionStatus.SUCCESS,
            output=output,
        )
