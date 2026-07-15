import logging

import pytest

from .command import CommandProvenance, CommandSource, GameCommand
from .game_engine import GameEngine
from .result import GameResult, GameResultStatus


def make_command(command_type="test.inspect", command_id="command-engine-001"):
    return GameCommand(
        command_id=command_id,
        command_type=command_type,
        payload={"location": "Old Crypt"},
        provenance=CommandProvenance(
            source=CommandSource.SYSTEM,
            initiator_id="engine-test",
        ),
    )


def test_successful_dispatch_invokes_exact_handler_once_and_preserves_result():
    engine = GameEngine()
    received = []
    command = make_command()
    expected = GameResult.success(command.command_id, {"inspected": True})

    def handler(dispatched_command):
        received.append(dispatched_command)
        return expected

    engine.register_handler(command.command_type, handler)

    result = engine.dispatch(command)

    assert result is expected
    assert received == [command]


def test_normal_domain_failure_output_is_not_treated_as_handler_exception():
    engine = GameEngine()
    command = make_command()
    expected = GameResult.success(
        command.command_id,
        {"success": False, "message": "Nothing to inspect."},
    )
    engine.register_handler(command.command_type, lambda received: expected)

    result = engine.dispatch(command)

    assert result is expected
    assert result.status is GameResultStatus.SUCCESS
    assert result.output["success"] is False


def test_unknown_command_returns_controlled_result_without_other_execution():
    engine = GameEngine()
    other_calls = []
    engine.register_handler("test.other", lambda command: other_calls.append(command))
    command = make_command("test.missing")

    result = engine.dispatch(command)

    assert result == GameResult.unknown_command(
        command.command_id,
        "No handler is registered for this command type.",
    )
    assert other_calls == []


def test_command_type_resolution_is_exact_and_case_sensitive():
    engine = GameEngine()
    call_count = 0

    def handler(command):
        nonlocal call_count
        call_count += 1
        return GameResult.success(command.command_id)

    engine.register_handler("test.inspect", handler)
    result = engine.dispatch(make_command("Test.inspect"))

    assert result.status is GameResultStatus.UNKNOWN_COMMAND
    assert call_count == 0


def test_duplicate_handler_registration_is_rejected_without_replacement():
    engine = GameEngine()

    def first(command):
        return GameResult.success(command.command_id, "first")

    def second(command):
        return GameResult.success(command.command_id, "second")

    engine.register_handler("test.inspect", first)

    with pytest.raises(ValueError, match="Duplicate"):
        engine.register_handler("test.inspect", second)

    assert engine.dispatch(make_command()).output == "first"


@pytest.mark.parametrize(
    ("command_type", "handler"),
    [
        ("", lambda command: None),
        (" padded ", lambda command: None),
        ("test.inspect", None),
        ("test.inspect", lambda: None),
        ("test.inspect", lambda command, extra=None: None),
        ("test.inspect", lambda *commands: None),
    ],
    ids=[
        "empty-type",
        "padded-type",
        "non-callable",
        "no-command-parameter",
        "extra-parameter",
        "variadic",
    ],
)
def test_invalid_handler_registrations_are_rejected(command_type, handler):
    with pytest.raises(ValueError):
        GameEngine().register_handler(command_type, handler)


def test_async_handler_registration_is_rejected():
    async def async_handler(command):
        return GameResult.success(command.command_id)

    with pytest.raises(ValueError, match="synchronous"):
        GameEngine().register_handler("test.inspect", async_handler)


def test_handler_exception_is_logged_and_converted_without_retry(caplog):
    engine = GameEngine()
    selected_calls = 0
    other_calls = 0

    def failing_handler(command):
        nonlocal selected_calls
        selected_calls += 1
        raise RuntimeError("private handler detail")

    def other_handler(command):
        nonlocal other_calls
        other_calls += 1
        return GameResult.success(command.command_id)

    engine.register_handler("test.inspect", failing_handler)
    engine.register_handler("test.other", other_handler)

    with caplog.at_level(logging.ERROR, logger="DungeonManager"):
        result = engine.dispatch(make_command())

    assert result == GameResult.handler_failure(
        "command-engine-001",
        "The command handler failed.",
    )
    assert "private handler detail" not in result.error
    assert "private handler detail" in caplog.text
    assert selected_calls == 1
    assert other_calls == 0


def test_explicit_controlled_handler_failure_is_preserved_as_normal_return():
    engine = GameEngine()
    command = make_command()
    expected = GameResult.handler_failure(
        command.command_id,
        "The test-only handler declined safely.",
    )
    engine.register_handler(command.command_type, lambda received: expected)

    result = engine.dispatch(command)

    assert result is expected
    assert result.error == "The test-only handler declined safely."


def test_wrong_handler_result_type_is_rejected_safely():
    engine = GameEngine()
    command = make_command()
    engine.register_handler(
        command.command_type,
        lambda received: {"success": True},
    )

    result = engine.dispatch(command)

    assert result == GameResult.invalid_handler_result(
        command.command_id,
        "The command handler returned an invalid result.",
    )


def test_mismatched_result_command_id_is_rejected_safely():
    engine = GameEngine()
    command = make_command()
    engine.register_handler(
        command.command_type,
        lambda received: GameResult.success("different-command-id"),
    )

    result = engine.dispatch(command)

    assert result.status is GameResultStatus.INVALID_HANDLER_RESULT
    assert result.command_id == command.command_id
    assert result.error == "The command handler returned an invalid result."


def test_structurally_corrupted_handler_result_is_rejected_safely():
    engine = GameEngine()
    command = make_command()
    corrupted = GameResult.success(command.command_id)
    object.__setattr__(corrupted, "error", "corrupted")
    engine.register_handler(command.command_type, lambda received: corrupted)

    result = engine.dispatch(command)

    assert result.status is GameResultStatus.INVALID_HANDLER_RESULT
    assert result.command_id == command.command_id


def test_registered_command_collection_cannot_mutate_engine_state():
    engine = GameEngine()
    engine.register_handler(
        "test.second",
        lambda command: GameResult.success(command.command_id),
    )
    engine.register_handler(
        "test.first",
        lambda command: GameResult.success(command.command_id),
    )

    registered = engine.registered_command_types

    assert registered == ("test.first", "test.second")
    with pytest.raises(AttributeError):
        registered.append("test.invented")
    registered += ("test.invented",)
    assert engine.registered_command_types == ("test.first", "test.second")


def test_structurally_invalid_command_returns_linked_controlled_result():
    engine = GameEngine()
    calls = 0

    def handler(command):
        nonlocal calls
        calls += 1
        return GameResult.success(command.command_id)

    engine.register_handler("test.inspect", handler)
    command = make_command()
    object.__setattr__(command, "command_type", " ")

    result = engine.dispatch(command)

    assert result == GameResult.invalid_command(
        command.command_id,
        "The game command is structurally invalid.",
    )
    assert calls == 0


def test_dispatch_rejects_non_command_values_before_handler_lookup():
    with pytest.raises(TypeError, match="requires a GameCommand"):
        GameEngine().dispatch({"command_type": "test.inspect"})
