import json

import pytest

from dungeon_manager.storage.json_storage import JSONStorage
from dungeon_manager.tools.registry import ToolRegistry

from .tool_call_parser import ToolCall
from .tool_executor import (
    ToolExecutionStatus,
    ToolExecutor,
)


class RecordingRegistry:
    def __init__(self, tools):
        self.tools = tools
        self.execute_calls = []

    def get_tools(self):
        return self.tools

    def execute(self, tool_name, **arguments):
        self.execute_calls.append((tool_name, arguments))
        return self.tools[tool_name](**arguments)


def test_successful_execution_with_arguments_preserves_output():
    received = []
    expected_output = {"created": "Arven"}

    def create_character(name, level):
        received.append((name, level))
        return expected_output

    registry = RecordingRegistry({"create_character": create_character})
    executor = ToolExecutor(registry)

    result = executor.execute(
        ToolCall(
            tool="create_character",
            arguments={"name": "Arven", "level": 3},
        )
    )

    assert result.status is ToolExecutionStatus.SUCCESS
    assert result.output is expected_output
    assert result.error is None
    assert received == [("Arven", 3)]


def test_successful_execution_with_empty_arguments():
    call_count = 0

    def current_round():
        nonlocal call_count
        call_count += 1
        return 4

    registry = RecordingRegistry({"current_round": current_round})

    result = ToolExecutor(registry).execute(
        ToolCall(tool="current_round", arguments={})
    )

    assert result.status is ToolExecutionStatus.SUCCESS
    assert result.output == 4
    assert call_count == 1


def test_arguments_are_forwarded_exactly_once():
    received = []

    def record_action(actor, action):
        received.append({"actor": actor, "action": action})
        return "recorded"

    registry = RecordingRegistry({"record_action": record_action})
    arguments = {"actor": "Arven", "action": "open_door"}

    result = ToolExecutor(registry).execute(
        ToolCall(tool="record_action", arguments=arguments)
    )

    assert result.status is ToolExecutionStatus.SUCCESS
    assert registry.execute_calls == [("record_action", arguments)]
    assert received == [arguments]


def test_unknown_tool_does_not_execute_a_registered_tool():
    known_call_count = 0

    def known_tool():
        nonlocal known_call_count
        known_call_count += 1

    registry = RecordingRegistry({"known_tool": known_tool})

    result = ToolExecutor(registry).execute(
        ToolCall(tool="missing_tool", arguments={})
    )

    assert result.status is ToolExecutionStatus.UNKNOWN_TOOL
    assert result.output is None
    assert registry.execute_calls == []
    assert known_call_count == 0


@pytest.mark.parametrize(
    "arguments",
    [
        {},
        {"name": "Arven", "unexpected": True},
    ],
    ids=["missing", "unexpected"],
)
def test_invalid_arguments_do_not_execute_or_fall_through(arguments):
    selected_call_count = 0
    other_call_count = 0

    def selected_tool(name):
        nonlocal selected_call_count
        selected_call_count += 1

    def other_tool():
        nonlocal other_call_count
        other_call_count += 1

    registry = RecordingRegistry(
        {
            "selected_tool": selected_tool,
            "other_tool": other_tool,
        }
    )

    result = ToolExecutor(registry).execute(
        ToolCall(tool="selected_tool", arguments=arguments)
    )

    assert result.status is ToolExecutionStatus.INVALID_ARGUMENTS
    assert result.output is None
    assert registry.execute_calls == []
    assert selected_call_count == 0
    assert other_call_count == 0


def test_tool_exception_becomes_safe_failure_without_retry_or_fallthrough():
    selected_call_count = 0
    other_call_count = 0

    def selected_tool(name):
        nonlocal selected_call_count
        selected_call_count += 1
        raise TypeError("private implementation detail")

    def other_tool():
        nonlocal other_call_count
        other_call_count += 1

    registry = RecordingRegistry(
        {
            "selected_tool": selected_tool,
            "other_tool": other_tool,
        }
    )

    result = ToolExecutor(registry).execute(
        ToolCall(tool="selected_tool", arguments={"name": "Arven"})
    )

    assert result.status is ToolExecutionStatus.TOOL_FAILURE
    assert result.output is None
    assert result.error == "Tool execution failed: selected_tool"
    assert "private implementation detail" not in result.error
    assert registry.execute_calls == [
        ("selected_tool", {"name": "Arven"})
    ]
    assert selected_call_count == 1
    assert other_call_count == 0


def test_normal_failure_payload_is_preserved_as_successful_invocation():
    expected_output = {
        "success": False,
        "message": "Character not found",
    }

    def load_character(name):
        return expected_output

    registry = RecordingRegistry({"load_character": load_character})

    result = ToolExecutor(registry).execute(
        ToolCall(tool="load_character", arguments={"name": "Missing"})
    )

    assert result.status is ToolExecutionStatus.SUCCESS
    assert result.output is expected_output
    assert result.error is None


def test_uninspectable_tool_returns_controlled_failure_without_execution():
    class UninspectableTool:
        @property
        def __signature__(self):
            raise ValueError("signature unavailable")

        def __call__(self):
            raise AssertionError("uninspectable tool must not execute")

    registry = RecordingRegistry({"uninspectable": UninspectableTool()})

    result = ToolExecutor(registry).execute(
        ToolCall(tool="uninspectable", arguments={})
    )

    assert result.status is ToolExecutionStatus.TOOL_FAILURE
    assert result.output is None
    assert registry.execute_calls == []


def test_character_tool_execution_uses_temporary_json_storage(tmp_path):
    registry = ToolRegistry()
    registry.character_tools.manager.storage = JSONStorage(tmp_path)
    executor = ToolExecutor(registry)

    result = executor.execute(
        ToolCall(
            tool="create_character",
            arguments={
                "name": "Temp Arven",
                "race": "Human",
                "character_class": "Fighter",
            },
        )
    )

    assert result.status is ToolExecutionStatus.SUCCESS
    assert result.output == {
        "success": True,
        "message": "Created character Temp Arven",
        "character": {
            "name": "Temp Arven",
            "race": "Human",
            "class": "Fighter",
        },
    }

    stored_path = tmp_path / "characters" / "temp arven.json"
    assert stored_path.exists()
    assert json.loads(stored_path.read_text(encoding="utf-8")) == {
        "name": "Temp Arven",
        "race": "Human",
        "character_class": "Fighter",
        "level": 1,
        "description": "",
        "inventory": [],
        "notes": [],
    }
