"""Opt-in live validation of the bounded ToolAgent loop against Ollama.

This module is deliberately standalone. Importing it, collecting tests, or
running the normal deterministic suite cannot contact Ollama. A live run must
set ``DUNGEON_MANAGER_RUN_LIVE_OLLAMA=1`` and execute the module directly.
"""

import hashlib
import json
import os
import sys
import uuid
from collections import Counter
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlparse

import requests

from dungeon_manager.ai.manager import AIManager
from dungeon_manager.ai.ollama_provider import OllamaProvider
from dungeon_manager.ai.provider import AIProvider
from dungeon_manager.ai.tool_agent import (
    ToolAgent,
    ToolAgentResultStatus,
)
from dungeon_manager.ai.tool_call_parser import ToolCallParseStatus, parse_tool_call
from dungeon_manager.ai.tool_executor import ToolExecutionStatus
from dungeon_manager.config_loader import load_config
from dungeon_manager.managers.character_manager import CharacterManager
from dungeon_manager.storage.json_storage import JSONStorage
from dungeon_manager.tools.character_tools import CharacterTools
from dungeon_manager.tools.registry import ToolRegistry


OPT_IN_ENVIRONMENT_VARIABLE = "DUNGEON_MANAGER_RUN_LIVE_OLLAMA"
REPORT_SCHEMA = "dungeon_manager.live_tool_loop_validation.v1"
_LOOPBACK_HOSTS = {"localhost", "127.0.0.1", "::1"}


class CountingProvider(AIProvider):
    """Count requests while delegating unchanged to the configured provider."""

    def __init__(self, provider):
        self.provider = provider
        self.call_count = 0

    def generate(self, prompt: str) -> str:
        self.call_count += 1
        return self.provider.generate(prompt)


class CountingCharacterTools(CharacterTools):
    """Count underlying character-tool calls without changing their behavior."""

    def __init__(self, manager):
        super().__init__(manager)
        self.invocations = Counter()

    def create_character(
        self,
        name: str,
        race: str = "",
        character_class: str = "",
    ):
        self.invocations["create_character"] += 1
        return super().create_character(name, race, character_class)

    def load_character(self, name: str):
        self.invocations["load_character"] += 1
        return super().load_character(name)


class CountingToolRegistry(ToolRegistry):
    """Count registry execution attempts while retaining real registry logic."""

    def __init__(self, character_tools):
        self.execute_calls = []
        super().__init__(character_tools)

    def execute(self, tool_name: str, **kwargs):
        self.execute_calls.append(
            {"tool": tool_name, "arguments": dict(kwargs)}
        )
        return super().execute(tool_name, **kwargs)


class CountingExecutor:
    """Count executor calls while delegating to the real ToolExecutor."""

    def __init__(self, executor):
        self.executor = executor
        self.calls = []

    def execute(self, tool_call):
        self.calls.append(tool_call)
        return self.executor.execute(tool_call)


def _temporary_storage_snapshot(storage_root: Path):
    snapshot = []
    for path in sorted(storage_root.rglob("*")):
        if not path.is_file():
            continue
        content = path.read_bytes()
        snapshot.append(
            {
                "path": path.relative_to(storage_root).as_posix(),
                "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    return snapshot


def _count_snapshot(provider, executor, registry, character_tools):
    return {
        "provider": provider.call_count,
        "executor": len(executor.calls),
        "registry": len(registry.execute_calls),
        "underlying_total": sum(character_tools.invocations.values()),
        "underlying_by_tool": dict(character_tools.invocations),
    }


def _count_delta(before, after):
    tool_names = set(before["underlying_by_tool"]) | set(
        after["underlying_by_tool"]
    )
    return {
        "provider_call_count": after["provider"] - before["provider"],
        "executor_invocation_count": after["executor"] - before["executor"],
        "registry_invocation_count": after["registry"] - before["registry"],
        "underlying_tool_invocation_count": (
            after["underlying_total"] - before["underlying_total"]
        ),
        "underlying_tool_invocations_by_name": {
            name: (
                after["underlying_by_tool"].get(name, 0)
                - before["underlying_by_tool"].get(name, 0)
            )
            for name in sorted(tool_names)
            if (
                after["underlying_by_tool"].get(name, 0)
                - before["underlying_by_tool"].get(name, 0)
            )
        },
    }


def _non_empty_text(value):
    return isinstance(value, str) and bool(value.strip())


def _final_text_is_not_a_tool_request(value):
    if not _non_empty_text(value):
        return False
    return parse_tool_call(value).status is ToolCallParseStatus.NO_TOOL_CALL


def _failure_is_communicated(value):
    if not _final_text_is_not_a_tool_request(value):
        return False
    lowered = value.lower()
    failure_phrases = (
        "not found",
        "could not find",
        "couldn't find",
        "does not exist",
        "doesn't exist",
        "no character",
        "unable to find",
    )
    return any(phrase in lowered for phrase in failure_phrases)


def _expected_character_data(name):
    return {
        "name": name,
        "race": "Human",
        "character_class": "Fighter",
        "level": 1,
        "description": "",
        "inventory": [],
        "notes": [],
    }


def _base_scenario_record(name, request, storage_before):
    return {
        "scenario": name,
        "request": request,
        "initial_model_response": None,
        "classified_tool_agent_result": None,
        "parse_error": None,
        "requested_tool": None,
        "requested_arguments": None,
        "execution_status": None,
        "execution_output": None,
        "execution_error": None,
        "final_response": None,
        "provider_call_count": 0,
        "executor_invocation_count": 0,
        "registry_invocation_count": 0,
        "underlying_tool_invocation_count": 0,
        "underlying_tool_invocations_by_name": {},
        "temporary_storage_before": storage_before,
        "temporary_storage_after": None,
        "passed": False,
        "failure_reason": None,
    }


def _record_result(record, result):
    record["initial_model_response"] = result.raw_response
    record["classified_tool_agent_result"] = result.status.value
    record["parse_error"] = result.parse_error
    if result.tool_call is not None:
        record["requested_tool"] = result.tool_call.tool
        record["requested_arguments"] = result.tool_call.arguments
    if result.observation is not None:
        record["execution_status"] = result.observation.status.value
        record["execution_output"] = result.observation.output
        record["execution_error"] = result.observation.error
    record["final_response"] = (
        result.raw_response
        if result.status is ToolAgentResultStatus.ASSISTANT_RESPONSE
        else result.final_response
    )


def _ordinary_failures(record):
    failures = []
    if record["classified_tool_agent_result"] != "assistant_response":
        failures.append("expected ASSISTANT_RESPONSE")
    if record["provider_call_count"] != 1:
        failures.append("expected exactly one provider call")
    for field in (
        "executor_invocation_count",
        "registry_invocation_count",
        "underlying_tool_invocation_count",
    ):
        if record[field] != 0:
            failures.append(f"expected {field} to be zero")
    if record["temporary_storage_before"] != record["temporary_storage_after"]:
        failures.append("ordinary response changed temporary storage")
    if not _non_empty_text(record["final_response"]):
        failures.append("ordinary response was empty")
    return failures


def _tool_count_failures(record, expected_tool):
    failures = []
    if record["provider_call_count"] != 2:
        failures.append("expected exactly two provider calls")
    if record["executor_invocation_count"] != 1:
        failures.append("expected exactly one executor invocation")
    if record["registry_invocation_count"] != 1:
        failures.append("expected exactly one registry invocation")
    if record["underlying_tool_invocation_count"] != 1:
        failures.append("expected exactly one underlying tool invocation")
    if record["underlying_tool_invocations_by_name"] != {expected_tool: 1}:
        failures.append(f"expected only one {expected_tool} invocation")
    return failures


def _create_failures(record, storage_root, character_name):
    failures = _tool_count_failures(record, "create_character")
    expected_arguments = {
        "name": character_name,
        "race": "Human",
        "character_class": "Fighter",
    }
    if record["classified_tool_agent_result"] != "tool_execution":
        failures.append("expected TOOL_EXECUTION")
    if record["requested_tool"] != "create_character":
        failures.append("expected create_character")
    if record["requested_arguments"] != expected_arguments:
        failures.append("create_character arguments did not match exactly")
    if record["execution_status"] != ToolExecutionStatus.SUCCESS.value:
        failures.append("create_character execution was not successful")

    expected_output = {
        "success": True,
        "message": f"Created character {character_name}",
        "character": {
            "name": character_name,
            "race": "Human",
            "class": "Fighter",
        },
    }
    if record["execution_output"] != expected_output:
        failures.append("create_character output did not match")
    if not _final_text_is_not_a_tool_request(record["final_response"]):
        failures.append("final response was empty or requested another tool")

    expected_path = storage_root / "characters" / f"{character_name.lower()}.json"
    expected_files = [f"characters/{character_name.lower()}.json"]
    actual_files = [item["path"] for item in record["temporary_storage_after"]]
    if actual_files != expected_files:
        failures.append("character was not the only temporary storage file")
    if not expected_path.is_file():
        failures.append("character was not persisted in temporary storage")
    else:
        try:
            stored = json.loads(expected_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            failures.append("stored character JSON could not be read")
        else:
            if stored != _expected_character_data(character_name):
                failures.append("stored character data did not match")
    return failures


def _load_existing_failures(record, character_name):
    failures = _tool_count_failures(record, "load_character")
    if record["classified_tool_agent_result"] != "tool_execution":
        failures.append("expected TOOL_EXECUTION")
    if record["requested_tool"] != "load_character":
        failures.append("expected load_character")
    if record["requested_arguments"] != {"name": character_name}:
        failures.append("load_character arguments did not match exactly")
    if record["execution_status"] != ToolExecutionStatus.SUCCESS.value:
        failures.append("load_character execution was not successful")
    if record["execution_output"] != {
        "success": True,
        "character": {
            "name": character_name,
            "race": "Human",
            "class": "Fighter",
            "level": 1,
        },
    }:
        failures.append("loaded character data did not match")
    if record["temporary_storage_before"] != record["temporary_storage_after"]:
        failures.append("load_character changed temporary storage")
    if not _final_text_is_not_a_tool_request(record["final_response"]):
        failures.append("final response was empty or requested another tool")
    return failures


def _load_missing_failures(record, missing_name):
    failures = _tool_count_failures(record, "load_character")
    if record["classified_tool_agent_result"] != "tool_execution":
        failures.append("expected TOOL_EXECUTION")
    if record["requested_tool"] != "load_character":
        failures.append("expected load_character")
    if record["requested_arguments"] != {"name": missing_name}:
        failures.append("load_character arguments did not match exactly")
    if record["execution_status"] != ToolExecutionStatus.SUCCESS.value:
        failures.append("domain failure was not preserved as successful execution")
    if record["execution_output"] != {
        "success": False,
        "message": "Character not found",
    }:
        failures.append("missing-character domain failure did not match")
    if record["temporary_storage_before"] != record["temporary_storage_after"]:
        failures.append("missing load changed temporary storage")
    if not _failure_is_communicated(record["final_response"]):
        failures.append("final response did not communicate the missing character")
    return failures


def _run_scenario(
    name,
    request,
    agent,
    provider,
    executor,
    registry,
    character_tools,
    storage_root,
    evaluate,
):
    storage_before = _temporary_storage_snapshot(storage_root)
    count_before = _count_snapshot(
        provider,
        executor,
        registry,
        character_tools,
    )
    record = _base_scenario_record(name, request, storage_before)

    try:
        result = agent.ask(request)
    except Exception as error:
        record["classified_tool_agent_result"] = "provider_exception"
        record["failure_reason"] = (
            f"{type(error).__name__}: {error}"
        )
    else:
        _record_result(record, result)

    record["temporary_storage_after"] = _temporary_storage_snapshot(storage_root)
    count_after = _count_snapshot(
        provider,
        executor,
        registry,
        character_tools,
    )
    record.update(_count_delta(count_before, count_after))

    if record["failure_reason"] is None:
        failures = evaluate(record)
        record["passed"] = not failures
        record["failure_reason"] = "; ".join(failures) if failures else None
    return record


def run_scenarios(provider, storage_root, character_name, missing_name):
    """Run each required scenario once with real components and injected storage."""

    manager = CharacterManager(JSONStorage(storage_root))
    character_tools = CountingCharacterTools(manager)
    registry = CountingToolRegistry(character_tools)
    counting_provider = CountingProvider(provider)
    agent = ToolAgent(counting_provider, registry)
    executor = CountingExecutor(agent.tool_executor)
    agent.tool_executor = executor

    scenarios = []
    scenarios.append(
        _run_scenario(
            "ordinary_response",
            "In one short sentence, what color is a clear daytime sky?",
            agent,
            counting_provider,
            executor,
            registry,
            character_tools,
            storage_root,
            _ordinary_failures,
        )
    )
    scenarios.append(
        _run_scenario(
            "create_character",
            (
                "Please create a Human Fighter named exactly "
                f"{character_name}."
            ),
            agent,
            counting_provider,
            executor,
            registry,
            character_tools,
            storage_root,
            lambda record: _create_failures(
                record,
                storage_root,
                character_name,
            ),
        )
    )
    scenarios.append(
        _run_scenario(
            "load_existing_character",
            f"Please load the existing character named exactly {character_name}.",
            agent,
            counting_provider,
            executor,
            registry,
            character_tools,
            storage_root,
            lambda record: _load_existing_failures(record, character_name),
        )
    )
    scenarios.append(
        _run_scenario(
            "load_missing_character",
            f"Please load the character named exactly {missing_name}.",
            agent,
            counting_provider,
            executor,
            registry,
            character_tools,
            storage_root,
            lambda record: _load_missing_failures(record, missing_name),
        )
    )

    return {
        "scenarios": scenarios,
        "totals": {
            "provider_call_count": counting_provider.call_count,
            "executor_invocation_count": len(executor.calls),
            "registry_invocation_count": len(registry.execute_calls),
            "underlying_tool_invocation_count": sum(
                character_tools.invocations.values()
            ),
            "underlying_tool_invocations_by_name": dict(
                character_tools.invocations
            ),
        },
        "all_scenarios_passed": all(item["passed"] for item in scenarios),
    }


def _configured_ollama_preflight(config):
    ai_config = config.get("ai", {})
    if ai_config.get("provider") != "ollama":
        raise RuntimeError("Configured AI provider is not Ollama.")

    endpoint = ai_config.get("endpoint")
    model = ai_config.get("model")
    parsed_endpoint = urlparse(endpoint or "")
    if parsed_endpoint.hostname not in _LOOPBACK_HOSTS:
        raise RuntimeError("Configured Ollama endpoint is not loopback-local.")
    if not model:
        raise RuntimeError("Configured Ollama model tag is empty.")

    endpoint = endpoint.rstrip("/")
    version_response = requests.get(f"{endpoint}/api/version", timeout=10)
    version_response.raise_for_status()
    tags_response = requests.get(f"{endpoint}/api/tags", timeout=10)
    tags_response.raise_for_status()
    installed_models = {
        tag
        for item in tags_response.json().get("models", [])
        for tag in (item.get("name"), item.get("model"))
        if tag
    }
    if model not in installed_models:
        raise RuntimeError(
            f"Configured Ollama model is not installed: {model}"
        )

    return {
        "endpoint": endpoint,
        "model": model,
        "ollama_version": version_response.json().get("version"),
    }


def _error_report(message):
    return {
        "schema": REPORT_SCHEMA,
        "all_scenarios_passed": False,
        "error": message,
    }


def main():
    if os.environ.get(OPT_IN_ENVIRONMENT_VARIABLE) != "1":
        print(
            json.dumps(
                _error_report(
                    f"Set {OPT_IN_ENVIRONMENT_VARIABLE}=1 to run live validation."
                ),
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    try:
        config = load_config()
        provider_details = _configured_ollama_preflight(config)
        provider = AIManager(config).provider
        if not isinstance(provider, OllamaProvider):
            raise RuntimeError("AIManager did not construct OllamaProvider.")
    except Exception as error:
        print(
            json.dumps(
                _error_report(f"Preflight failed: {type(error).__name__}: {error}"),
                indent=2,
            ),
            file=sys.stderr,
        )
        return 2

    unique_suffix = uuid.uuid4().hex[:10].upper()
    character_name = f"Talvorn {unique_suffix}"
    missing_name = f"Neverborn {unique_suffix}"

    try:
        with TemporaryDirectory(
            prefix="dungeon-manager-live-validation-"
        ) as temp_directory:
            temporary_root = Path(temp_directory)
            scenario_report = run_scenarios(
                provider,
                temporary_root,
                character_name,
                missing_name,
            )
        cleanup_confirmed = not temporary_root.exists()
    except Exception as error:
        print(
            json.dumps(
                _error_report(
                    f"Validation failed: {type(error).__name__}: {error}"
                ),
                indent=2,
            ),
            file=sys.stderr,
        )
        return 1

    report = {
        "schema": REPORT_SCHEMA,
        "provider": provider_details,
        "temporary_storage": True,
        "project_logging_configured": False,
        "character_name": character_name,
        "missing_character_name": missing_name,
        **scenario_report,
        "temporary_storage_cleanup_confirmed": cleanup_confirmed,
    }
    report["passed"] = (
        report["all_scenarios_passed"] and cleanup_confirmed
    )
    print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
