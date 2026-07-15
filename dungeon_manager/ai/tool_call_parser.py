"""Parse tool requests from complete AI responses without executing them."""

import json
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, Optional


_JSON_FENCE = re.compile(
    r"\A```json[ \t]*\r?\n(?P<body>.*?)\r?\n```[ \t]*\Z",
    re.DOTALL | re.IGNORECASE,
)


class ToolCallParseStatus(str, Enum):
    """Possible outcomes when inspecting an AI response."""

    VALID = "valid"
    NO_TOOL_CALL = "no_tool_call"
    MALFORMED = "malformed"


@dataclass(frozen=True)
class ToolCall:
    """A structurally valid tool request, independent of any tool registry."""

    tool: str
    arguments: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolCallParseResult:
    """The result of inspecting one complete AI response."""

    status: ToolCallParseStatus
    tool_call: Optional[ToolCall] = None
    error: Optional[str] = None


def _malformed(error: str) -> ToolCallParseResult:
    return ToolCallParseResult(
        status=ToolCallParseStatus.MALFORMED,
        error=error,
    )


def parse_tool_call(response: str) -> ToolCallParseResult:
    """Inspect a complete AI response for one canonical JSON tool request.

    Plain non-JSON text is an ordinary response. JSON-looking responses and
    complete JSON code fences are parsed as a whole and must match the tool-call
    structure. JSON embedded in surrounding prose is deliberately ignored.
    """

    if not isinstance(response, str):
        return _malformed("AI response must be a string.")

    candidate = response.strip()
    if not candidate:
        return ToolCallParseResult(status=ToolCallParseStatus.NO_TOOL_CALL)

    fenced = _JSON_FENCE.fullmatch(candidate)
    was_fenced = fenced is not None

    if fenced:
        candidate = fenced.group("body").strip()
    elif candidate.lower().startswith("```json"):
        return _malformed("JSON code fence must contain the entire response.")

    try:
        decoded = json.loads(candidate)
    except json.JSONDecodeError as error:
        if was_fenced or candidate.startswith(("{", "[")):
            return _malformed(f"Invalid JSON: {error.msg}.")

        return ToolCallParseResult(status=ToolCallParseStatus.NO_TOOL_CALL)

    if not isinstance(decoded, dict):
        return _malformed("Tool-call response must be a JSON object.")

    if "tool" not in decoded:
        return _malformed("Tool-call response is missing the 'tool' field.")

    tool = decoded["tool"]
    if not isinstance(tool, str) or not tool.strip():
        return _malformed("The 'tool' field must be a non-empty string.")

    arguments = decoded.get("arguments", {})
    if not isinstance(arguments, dict):
        return _malformed("The 'arguments' field must be a JSON object.")

    return ToolCallParseResult(
        status=ToolCallParseStatus.VALID,
        tool_call=ToolCall(tool=tool, arguments=arguments),
    )
