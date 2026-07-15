import json
from dataclasses import FrozenInstanceError

import pytest

from .result import GameResult, GameResultStatus


def test_successful_result_preserves_immutable_output_and_has_no_error():
    original = {"scene": {"objects": ["door", {"locked": True}]}}
    result = GameResult.success("command-result-001", original)

    original["scene"]["objects"].append("changed")

    assert result.status is GameResultStatus.SUCCESS
    assert result.error is None
    assert result.output["scene"]["objects"] == (
        "door",
        {"locked": True},
    )
    with pytest.raises(TypeError):
        result.output["scene"]["objects"][1]["locked"] = False
    with pytest.raises(FrozenInstanceError):
        result.error = "changed"


@pytest.mark.parametrize(
    ("factory", "status"),
    [
        (GameResult.unknown_command, GameResultStatus.UNKNOWN_COMMAND),
        (GameResult.invalid_command, GameResultStatus.INVALID_COMMAND),
        (
            GameResult.invalid_handler_result,
            GameResultStatus.INVALID_HANDLER_RESULT,
        ),
        (GameResult.handler_failure, GameResultStatus.HANDLER_FAILURE),
    ],
)
def test_failure_result_factories_enforce_status_and_safe_error(factory, status):
    result = factory("command-result-002", "Safe caller-facing error.")

    assert result.command_id == "command-result-002"
    assert result.status is status
    assert result.output is None
    assert result.error == "Safe caller-facing error."


def test_result_serialization_is_json_compatible_and_independent():
    result = GameResult.success(
        "command-result-003",
        {"events": [{"type": "test-only"}]},
    )

    serialized = result.to_dict()
    serialized["output"]["events"][0]["type"] = "changed"

    fresh = result.to_dict()
    assert fresh == {
        "command_id": "command-result-003",
        "error": None,
        "output": {"events": [{"type": "test-only"}]},
        "status": "success",
    }
    assert json.loads(json.dumps(fresh, allow_nan=False)) == fresh


@pytest.mark.parametrize(
    "factory",
    [
        lambda: GameResult(
            command_id="command-result-004",
            status=GameResultStatus.SUCCESS,
            error="must not be present",
        ),
        lambda: GameResult(
            command_id="command-result-004",
            status=GameResultStatus.HANDLER_FAILURE,
        ),
        lambda: GameResult(
            command_id="command-result-004",
            status=GameResultStatus.UNKNOWN_COMMAND,
            output={"unexpected": True},
            error="Safe error.",
        ),
        lambda: GameResult(
            command_id=" ",
            status=GameResultStatus.SUCCESS,
        ),
        lambda: GameResult(
            command_id="command-result-004",
            status="success",
        ),
        lambda: GameResult.success(
            "command-result-004",
            {"unsupported": object()},
        ),
    ],
    ids=[
        "success-error",
        "failure-without-error",
        "failure-output",
        "invalid-command-id",
        "untyped-status",
        "invalid-output",
    ],
)
def test_result_invariant_violations_are_rejected(factory):
    with pytest.raises(ValueError):
        factory()
