from dataclasses import dataclass
from enum import Enum
from typing import Optional, cast

from dungeon_manager.ai.provider import AIProvider
from dungeon_manager.ai.tool_call_parser import (
    ToolCall,
    ToolCallParseStatus,
    parse_tool_call,
)
from dungeon_manager.ai.tool_executor import ToolExecutionResult, ToolExecutor
from dungeon_manager.tools.registry import ToolRegistry


class ToolAgentResultStatus(str, Enum):
    """Possible outcomes after processing one provider response."""

    ASSISTANT_RESPONSE = "assistant_response"
    MALFORMED_TOOL_REQUEST = "malformed_tool_request"
    TOOL_EXECUTION = "tool_execution"


@dataclass(frozen=True)
class ToolAgentResult:
    """Typed result of one provider/parse/optional-execution pass."""

    status: ToolAgentResultStatus
    raw_response: str
    tool_call: Optional[ToolCall] = None
    observation: Optional[ToolExecutionResult] = None
    parse_error: Optional[str] = None


class ToolAgent:
    """
    Connects the AI provider with available tools.
    """

    def __init__(
        self,
        ai_provider: AIProvider,
        tool_registry: Optional[ToolRegistry] = None,
    ):

        self.ai_provider = ai_provider
        self.tool_registry = (
            tool_registry if tool_registry is not None else ToolRegistry()
        )
        self.tool_executor = ToolExecutor(self.tool_registry)


    def get_available_tools(self):

        return list(
            self.tool_registry.get_tools().keys()
        )


    def ask(self, prompt: str) -> ToolAgentResult:

        tools = self.get_available_tools()

        enhanced_prompt = f"""
You are Dungeon Manager AI.

Available tools:
{tools}

User request:
{prompt}

Respond normally.
"""

        raw_response = self.ai_provider.generate(
            enhanced_prompt
        )

        parse_result = parse_tool_call(raw_response)

        if parse_result.status is ToolCallParseStatus.NO_TOOL_CALL:
            return ToolAgentResult(
                status=ToolAgentResultStatus.ASSISTANT_RESPONSE,
                raw_response=raw_response,
            )

        if parse_result.status is ToolCallParseStatus.MALFORMED:
            return ToolAgentResult(
                status=ToolAgentResultStatus.MALFORMED_TOOL_REQUEST,
                raw_response=raw_response,
                parse_error=parse_result.error,
            )

        tool_call = cast(ToolCall, parse_result.tool_call)
        observation = self.tool_executor.execute(tool_call)

        return ToolAgentResult(
            status=ToolAgentResultStatus.TOOL_EXECUTION,
            raw_response=raw_response,
            tool_call=tool_call,
            observation=observation,
        )
