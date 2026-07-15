import json

import pytest

from .tool_call_parser import (
    ToolCall,
    ToolCallParseStatus,
    parse_tool_call,
)


def test_valid_tool_call_with_arguments():
    response = """
    {
        "tool": "create_character",
        "arguments": {
            "name": "Arven",
            "race": "Human",
            "character_class": "Fighter"
        }
    }
    """

    result = parse_tool_call(response)

    assert result.status is ToolCallParseStatus.VALID
    assert result.tool_call == ToolCall(
        tool="create_character",
        arguments={
            "name": "Arven",
            "race": "Human",
            "character_class": "Fighter",
        },
    )
    assert result.error is None


def test_valid_tool_call_without_arguments_defaults_to_empty_object():
    result = parse_tool_call('{"tool": "load_character"}')

    assert result.status is ToolCallParseStatus.VALID
    assert result.tool_call == ToolCall(tool="load_character", arguments={})


def test_ordinary_non_json_text_has_no_tool_call():
    result = parse_tool_call("Arven enters the torchlit hall.")

    assert result.status is ToolCallParseStatus.NO_TOOL_CALL
    assert result.tool_call is None
    assert result.error is None


def test_malformed_json_is_reported():
    result = parse_tool_call('{"tool": "create_character",')

    assert result.status is ToolCallParseStatus.MALFORMED
    assert result.tool_call is None
    assert result.error is not None


def test_missing_tool_field_is_reported():
    result = parse_tool_call('{"arguments": {"name": "Arven"}}')

    assert result.status is ToolCallParseStatus.MALFORMED
    assert result.tool_call is None


@pytest.mark.parametrize("tool", [None, "", "   ", 42, []])
def test_invalid_or_empty_tool_value_is_reported(tool):
    result = parse_tool_call(json.dumps({"tool": tool}))

    assert result.status is ToolCallParseStatus.MALFORMED
    assert result.tool_call is None


@pytest.mark.parametrize("arguments", [None, [], "Arven", 42])
def test_arguments_with_wrong_type_are_reported(arguments):
    response = json.dumps(
        {
            "tool": "create_character",
            "arguments": arguments,
        }
    )

    result = parse_tool_call(response)

    assert result.status is ToolCallParseStatus.MALFORMED
    assert result.tool_call is None


def test_json_code_fence_is_supported():
    response = """```json
{"tool": "load_character", "arguments": {"name": "Arven"}}
```"""

    result = parse_tool_call(response)

    assert result.status is ToolCallParseStatus.VALID
    assert result.tool_call == ToolCall(
        tool="load_character",
        arguments={"name": "Arven"},
    )


def test_non_object_json_is_reported():
    result = parse_tool_call('["create_character"]')

    assert result.status is ToolCallParseStatus.MALFORMED
    assert result.tool_call is None


def test_json_embedded_in_prose_is_not_searched():
    response = 'Use this request: {"tool": "load_character"}'

    result = parse_tool_call(response)

    assert result.status is ToolCallParseStatus.NO_TOOL_CALL
    assert result.tool_call is None
