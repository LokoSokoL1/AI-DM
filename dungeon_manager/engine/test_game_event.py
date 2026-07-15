import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timedelta, timezone

import pytest

from . import game_event as game_event_module
from .command import CommandProvenance, CommandSource
from .game_event import GameEvent


FIXED_UTC = datetime(2026, 7, 15, 10, 11, 12, 345678, timezone.utc)


def provenance(
    source=CommandSource.SYSTEM,
    initiator_id="engine-event-test",
):
    return CommandProvenance(source=source, initiator_id=initiator_id)


def make_event(**overrides):
    values = {
        "event_id": "event-test-001",
        "event_type": "world.location_revealed",
        "occurred_at": FIXED_UTC,
        "provenance": provenance(),
    }
    values.update(overrides)
    return GameEvent(**values)


def test_event_generates_unique_non_empty_ids_and_accepts_explicit_id():
    first = GameEvent(
        event_type="world.location_revealed",
        provenance=provenance(),
        occurred_at=FIXED_UTC,
    )
    second = GameEvent(
        event_type="world.location_revealed",
        provenance=provenance(),
        occurred_at=FIXED_UTC,
    )
    explicit = make_event(event_id="event-deterministic-001")

    assert first.event_id
    assert first.event_id.strip() == first.event_id
    assert first.event_id != second.event_id
    assert explicit.event_id == "event-deterministic-001"


def test_generated_event_time_uses_isolated_injectable_clock(monkeypatch):
    generated = datetime(
        2026,
        7,
        15,
        12,
        11,
        12,
        345678,
        timezone(timedelta(hours=2)),
    )
    monkeypatch.setattr(game_event_module, "utc_now", lambda: generated)

    event = GameEvent(
        event_type="world.location_revealed",
        provenance=provenance(),
    )

    assert event.occurred_at == FIXED_UTC
    assert event.occurred_at.tzinfo is timezone.utc


def test_explicit_aware_event_time_is_normalized_and_serialized_as_utc():
    local_time = datetime(
        2026,
        7,
        15,
        15,
        41,
        12,
        345678,
        timezone(timedelta(hours=5, minutes=30)),
    )

    event = make_event(occurred_at=local_time)

    assert event.occurred_at == FIXED_UTC
    assert event.occurred_at.tzinfo is timezone.utc
    assert event.to_dict()["occurred_at"] == "2026-07-15T10:11:12.345678Z"


@pytest.mark.parametrize(
    "timestamp",
    [datetime(2026, 7, 15, 10, 11, 12), "2026-07-15T10:11:12Z", None],
    ids=["naive", "string", "none"],
)
def test_naive_or_malformed_event_timestamps_are_rejected(timestamp):
    with pytest.raises(ValueError, match="occurrence time"):
        make_event(occurred_at=timestamp)


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("event_id", " ", "Game event ID"),
        ("event_type", " padded ", "Game event type"),
        ("event_type", "", "Game event type"),
        ("schema_version", 0, "schema version"),
        ("schema_version", True, "schema version"),
        ("provenance", "system", "provenance"),
        ("originating_command_id", " command ", "Originating command ID"),
        ("actor_id", " ", "actor ID"),
    ],
)
def test_invalid_event_structures_are_rejected(field, value, message):
    with pytest.raises(ValueError, match=message):
        make_event(**{field: value})


@pytest.mark.parametrize(
    "payload",
    [
        {1: "non-string key"},
        {"unsupported": object()},
        {"not_finite": float("inf")},
    ],
    ids=["non-string-key", "unsupported", "not-finite"],
)
def test_invalid_event_payloads_are_rejected(payload):
    with pytest.raises(ValueError, match="Game event payload"):
        make_event(payload=payload)


def test_event_payload_is_deeply_immutable_and_defensively_copied():
    original = {
        "location": {
            "features": ["sealed door", {"torch_lit": False}],
        }
    }
    event = make_event(payload=original)

    original["location"]["features"].append("invented")

    assert event.payload["location"]["features"] == (
        "sealed door",
        {"torch_lit": False},
    )
    with pytest.raises(TypeError):
        event.payload["location"]["features"][1]["torch_lit"] = True
    with pytest.raises(FrozenInstanceError):
        event.event_type = "world.changed"


def test_event_preserves_command_provenance_and_actor_linkage():
    event = make_event(
        originating_command_id="command-event-001",
        provenance=provenance(CommandSource.AI, "local-model"),
        actor_id="npc-guard-17",
    )

    assert event.originating_command_id == "command-event-001"
    assert event.provenance.source is CommandSource.AI
    assert event.provenance.initiator_id == "local-model"
    assert event.actor_id == "npc-guard-17"


def test_event_serialization_is_json_compatible_and_independent():
    event = make_event(
        payload={"targets": ["door", {"trap": None}]},
        originating_command_id="command-event-001",
        actor_id="character-1",
    )

    serialized = event.to_dict()
    serialized["payload"]["targets"][1]["trap"] = "changed"
    serialized["provenance"]["initiator_id"] = "changed"

    fresh = event.to_dict()
    assert fresh["payload"]["targets"][1]["trap"] is None
    assert fresh["provenance"]["initiator_id"] == "engine-event-test"
    assert fresh["schema_version"] == 1
    assert json.loads(json.dumps(fresh, allow_nan=False)) == fresh
