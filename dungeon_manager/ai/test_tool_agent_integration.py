import json

import pytest

from dungeon_manager.ai.provider import AIProvider
from dungeon_manager.ai.tool_call_parser import ToolCall
from dungeon_manager.ai.tool_executor import (
    ToolExecutionStatus,
)
from dungeon_manager.storage.json_storage import JSONStorage
from dungeon_manager.tools.registry import ToolRegistry

from .tool_agent import (
    ToolAgent,
    ToolAgentResultStatus,
)


class StubProvider(AIProvider):
    def __init__(self, response):
        self.response = response
        self.prompts = []

    def generate(self, prompt):
        self.prompts.append(prompt)
        if len(self.prompts) > 1:
            raise AssertionError("ToolAgent must not make a follow-up request")
        return self.response


class RecordingRegistry:
    def __init__(self, tools):
        self.tools = tools
        self.execute_calls = []

    def get_tools(self):
        return self.tools

    def execute(self, tool_name, **arguments):
        self.execute_calls.append((tool_name, arguments))
        return self.tools[tool_name](**arguments)


class RecordingExecutor:
    def __init__(self, executor):
        self.executor = executor
        self.calls = []

    def execute(self, tool_call):
        self.calls.append(tool_call)
        return self.executor.execute(tool_call)


def create_agent(response, tools):
    provider = StubProvider(response)
    registry = RecordingRegistry(tools)
    agent = ToolAgent(provider, registry)
    executor = RecordingExecutor(agent.tool_executor)
    agent.tool_executor = executor
    return agent, provider, registry, executor


def test_ordinary_text_is_preserved_without_execution():
    raw_response = "Arven enters the torchlit hall."
    agent, provider, registry, executor = create_agent(
        raw_response,
        {"must_not_run": lambda: None},
    )

    result = agent.ask("Continue the scene.")

    assert result.status is ToolAgentResultStatus.ASSISTANT_RESPONSE
    assert result.raw_response == raw_response
    assert result.tool_call is None
    assert result.observation is None
    assert result.parse_error is None
    assert executor.calls == []
    assert registry.execute_calls == []
    assert len(provider.prompts) == 1


def test_valid_tool_call_executes_once_with_correct_arguments():
    received = []

    def create_character(name, level):
        received.append((name, level))
        return {"created": name, "level": level}

    raw_response = json.dumps(
        {
            "tool": "create_character",
            "arguments": {"name": "Arven", "level": 3},
        }
    )
    agent, provider, registry, executor = create_agent(
        raw_response,
        {"create_character": create_character},
    )

    result = agent.ask("Create Arven.")

    expected_call = ToolCall(
        tool="create_character",
        arguments={"name": "Arven", "level": 3},
    )
    assert result.status is ToolAgentResultStatus.TOOL_EXECUTION
    assert result.raw_response == raw_response
    assert result.tool_call == expected_call
    assert result.observation.status is ToolExecutionStatus.SUCCESS
    assert result.observation.output == {"created": "Arven", "level": 3}
    assert executor.calls == [expected_call]
    assert registry.execute_calls == [
        ("create_character", {"name": "Arven", "level": 3})
    ]
    assert received == [("Arven", 3)]
    assert len(provider.prompts) == 1


def test_valid_tool_call_without_arguments_executes_once():
    call_count = 0

    def current_round():
        nonlocal call_count
        call_count += 1
        return 4

    agent, provider, registry, executor = create_agent(
        '{"tool": "current_round"}',
        {"current_round": current_round},
    )

    result = agent.ask("What round is it?")

    expected_call = ToolCall(tool="current_round", arguments={})
    assert result.status is ToolAgentResultStatus.TOOL_EXECUTION
    assert result.tool_call == expected_call
    assert result.observation.status is ToolExecutionStatus.SUCCESS
    assert result.observation.output == 4
    assert executor.calls == [expected_call]
    assert registry.execute_calls == [("current_round", {})]
    assert call_count == 1
    assert len(provider.prompts) == 1


def test_malformed_tool_json_returns_controlled_result_without_execution():
    raw_response = '{"tool": "create_character",'
    agent, provider, registry, executor = create_agent(
        raw_response,
        {"create_character": lambda name: name},
    )

    result = agent.ask("Create Arven.")

    assert result.status is ToolAgentResultStatus.MALFORMED_TOOL_REQUEST
    assert result.raw_response == raw_response
    assert result.tool_call is None
    assert result.observation is None
    assert result.parse_error is not None
    assert executor.calls == []
    assert registry.execute_calls == []
    assert len(provider.prompts) == 1


def test_unknown_tool_preserves_executor_result():
    agent, provider, registry, executor = create_agent(
        '{"tool": "missing_tool"}',
        {"known_tool": lambda: None},
    )

    result = agent.ask("Use the missing tool.")

    assert result.status is ToolAgentResultStatus.TOOL_EXECUTION
    assert result.observation.status is ToolExecutionStatus.UNKNOWN_TOOL
    assert result.observation.error == "Unknown tool: missing_tool"
    assert executor.calls == [ToolCall(tool="missing_tool", arguments={})]
    assert registry.execute_calls == []
    assert len(provider.prompts) == 1


def test_invalid_arguments_preserve_executor_result_without_execution():
    agent, provider, registry, executor = create_agent(
        '{"tool": "load_character"}',
        {"load_character": lambda name: name},
    )

    result = agent.ask("Load a character.")

    assert result.status is ToolAgentResultStatus.TOOL_EXECUTION
    assert result.observation.status is ToolExecutionStatus.INVALID_ARGUMENTS
    assert result.observation.error == "Invalid arguments for tool: load_character"
    assert executor.calls == [ToolCall(tool="load_character", arguments={})]
    assert registry.execute_calls == []
    assert len(provider.prompts) == 1


def test_tool_exception_preserves_controlled_executor_failure():
    call_count = 0

    def failing_tool():
        nonlocal call_count
        call_count += 1
        raise RuntimeError("private implementation detail")

    agent, provider, registry, executor = create_agent(
        '{"tool": "failing_tool"}',
        {"failing_tool": failing_tool},
    )

    result = agent.ask("Run the failing tool.")

    assert result.status is ToolAgentResultStatus.TOOL_EXECUTION
    assert result.observation.status is ToolExecutionStatus.TOOL_FAILURE
    assert result.observation.error == "Tool execution failed: failing_tool"
    assert "private implementation detail" not in result.observation.error
    assert executor.calls == [ToolCall(tool="failing_tool", arguments={})]
    assert registry.execute_calls == [("failing_tool", {})]
    assert call_count == 1
    assert len(provider.prompts) == 1


def test_successful_tool_output_is_preserved_unchanged():
    expected_output = {
        "success": False,
        "message": "Character not found",
    }

    def load_character(name):
        return expected_output

    agent, provider, registry, executor = create_agent(
        '{"tool": "load_character", "arguments": {"name": "Missing"}}',
        {"load_character": load_character},
    )

    result = agent.ask("Load Missing.")

    assert result.status is ToolAgentResultStatus.TOOL_EXECUTION
    assert result.observation.status is ToolExecutionStatus.SUCCESS
    assert result.observation.output is expected_output
    assert len(executor.calls) == 1
    assert len(registry.execute_calls) == 1
    assert len(provider.prompts) == 1


@pytest.mark.parametrize(
    "response",
    [
        "An ordinary answer.",
        '{"tool":',
        '{"tool": "missing_tool"}',
        '{"tool": "known_tool"}',
    ],
    ids=["ordinary", "malformed", "unknown", "successful"],
)
def test_provider_is_called_once_without_follow_up_or_retry(response):
    agent, provider, _, _ = create_agent(response, {"known_tool": lambda: "ok"})

    agent.ask("Handle this once.")

    assert len(provider.prompts) == 1


def test_existing_prompt_and_tool_discovery_behavior_is_preserved():
    agent, provider, _, _ = create_agent(
        "Ready.",
        {
            "create_character": lambda: None,
            "load_character": lambda: None,
        },
    )

    assert agent.get_available_tools() == ["create_character", "load_character"]

    agent.ask("Describe Arven.")

    assert provider.prompts == [
        """
You are Dungeon Manager AI.

Available tools:
['create_character', 'load_character']

User request:
Describe Arven.

Respond normally.
"""
    ]


def test_provider_errors_still_propagate():
    class FailingProvider(AIProvider):
        def generate(self, prompt):
            raise RuntimeError("provider unavailable")

    agent = ToolAgent(FailingProvider(), RecordingRegistry({}))

    with pytest.raises(RuntimeError, match="provider unavailable"):
        agent.ask("Continue.")


def test_real_registry_path_uses_only_temporary_storage(tmp_path):
    raw_response = json.dumps(
        {
            "tool": "create_character",
            "arguments": {
                "name": "Temp Arven",
                "race": "Human",
                "character_class": "Fighter",
            },
        }
    )
    provider = StubProvider(raw_response)
    registry = ToolRegistry()
    registry.character_tools.manager.storage = JSONStorage(tmp_path)
    agent = ToolAgent(provider, registry)

    result = agent.ask("Create Temp Arven.")

    assert result.status is ToolAgentResultStatus.TOOL_EXECUTION
    assert result.observation.status is ToolExecutionStatus.SUCCESS
    assert result.observation.output == {
        "success": True,
        "message": "Created character Temp Arven",
        "character": {
            "name": "Temp Arven",
            "race": "Human",
            "class": "Fighter",
        },
    }
    assert len(provider.prompts) == 1

    stored_path = tmp_path / "characters" / "temp arven.json"
    assert stored_path.exists()
    assert json.loads(stored_path.read_text(encoding="utf-8"))["name"] == "Temp Arven"
