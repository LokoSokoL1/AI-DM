import json
from dataclasses import FrozenInstanceError

import pytest

from .command import CommandProvenance, CommandSource, GameCommand


def provenance(source=CommandSource.SYSTEM, initiator_id="engine-test"):
    return CommandProvenance(source=source, initiator_id=initiator_id)


def test_command_generates_a_stable_non_empty_id_by_default():
    first = GameCommand(
        command_type="test.inspect",
        provenance=provenance(),
    )
    second = GameCommand(
        command_type="test.inspect",
        provenance=provenance(),
    )

    assert isinstance(first.command_id, str)
    assert first.command_id.strip() == first.command_id
    assert first.command_id
    assert first.command_id != second.command_id


def test_command_accepts_an_explicit_deterministic_id():
    command = GameCommand(
        command_id="command-test-001",
        command_type="test.inspect",
        payload={"location": "Old Crypt"},
        provenance=provenance(),
    )

    assert command.command_id == "command-test-001"
    assert command.to_dict()["command_id"] == "command-test-001"


@pytest.mark.parametrize("command_id", [None, "", "   ", " padded ", 42])
def test_invalid_command_ids_are_rejected(command_id):
    with pytest.raises(ValueError, match="Command ID"):
        GameCommand(
            command_id=command_id,
            command_type="test.inspect",
            provenance=provenance(),
        )


@pytest.mark.parametrize("command_type", [None, "", "   ", " padded ", 42])
def test_invalid_command_types_are_rejected(command_type):
    with pytest.raises(ValueError, match="Command type"):
        GameCommand(
            command_type=command_type,
            provenance=provenance(),
        )


@pytest.mark.parametrize("source", list(CommandSource))
def test_provenance_covers_every_supported_initiator_source(source):
    command = GameCommand(
        command_type="test.inspect",
        provenance=provenance(source, f"{source.value}-initiator"),
    )

    assert command.provenance.source is source
    assert command.to_dict()["provenance"] == {
        "source": source.value,
        "initiator_id": f"{source.value}-initiator",
    }


def test_actor_identity_is_optional_and_separate_from_initiator_identity():
    without_actor = GameCommand(
        command_type="test.inspect",
        provenance=provenance(CommandSource.AI, "local-model"),
    )
    with_actor = GameCommand(
        command_type="test.inspect",
        provenance=provenance(CommandSource.AI, "local-model"),
        actor_id="npc-guard-17",
    )

    assert without_actor.actor_id is None
    assert with_actor.actor_id == "npc-guard-17"
    assert with_actor.provenance.initiator_id == "local-model"


def test_command_payload_is_deeply_immutable_and_defensively_copied():
    original = {
        "location": {
            "name": "Old Crypt",
            "features": ["sealed door", {"light": False}],
        }
    }
    command = GameCommand(
        command_type="test.inspect",
        payload=original,
        provenance=provenance(),
    )

    original["location"]["name"] = "Changed"
    original["location"]["features"].append("invented")

    assert command.payload["location"]["name"] == "Old Crypt"
    assert command.payload["location"]["features"] == (
        "sealed door",
        {"light": False},
    )
    with pytest.raises(TypeError):
        command.payload["location"]["name"] = "Changed"
    with pytest.raises(AttributeError):
        command.payload["location"]["features"].append("invented")
    with pytest.raises(FrozenInstanceError):
        command.actor_id = "another-actor"


def test_command_serialization_is_json_compatible_and_independent():
    command = GameCommand(
        command_id="command-test-serialization",
        command_type="test.inspect",
        payload={"targets": ["door", {"trap": None}]},
        provenance=provenance(CommandSource.HUMAN, "user-1"),
        actor_id="character-1",
    )

    serialized = command.to_dict()
    serialized["payload"]["targets"][1]["trap"] = "changed"
    serialized["provenance"]["initiator_id"] = "changed"

    fresh = command.to_dict()
    assert fresh["payload"]["targets"][1]["trap"] is None
    assert fresh["provenance"]["initiator_id"] == "user-1"
    assert json.loads(json.dumps(fresh, allow_nan=False)) == fresh


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {1: "non-string key"},
        {"unsupported": object()},
        {"not_finite": float("nan")},
    ],
    ids=["non-object", "non-string-key", "unsupported", "not-finite"],
)
def test_invalid_payload_structures_are_rejected(payload):
    with pytest.raises(ValueError, match="Command payload"):
        GameCommand(
            command_type="test.inspect",
            payload=payload,
            provenance=provenance(),
        )


def test_circular_payload_is_rejected_clearly():
    payload = {}
    payload["self"] = payload

    with pytest.raises(ValueError, match="circular references"):
        GameCommand(
            command_type="test.inspect",
            payload=payload,
            provenance=provenance(),
        )


def test_invalid_provenance_and_optional_identifiers_are_rejected():
    with pytest.raises(ValueError, match="Command source"):
        CommandProvenance(source="human")
    with pytest.raises(ValueError, match="initiator ID"):
        CommandProvenance(source=CommandSource.HUMAN, initiator_id=" ")
    with pytest.raises(ValueError, match="actor ID"):
        GameCommand(
            command_type="test.inspect",
            provenance=provenance(),
            actor_id=" actor ",
        )
