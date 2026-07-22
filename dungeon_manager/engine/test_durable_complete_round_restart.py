"""Process-boundary proof for the one durable controlled combat round.

This test deliberately retains only serialized authoritative facts between
runtime lifetimes.  It never passes an event, state, dispatcher, provider, or
other process-local object into either restarted runtime.
"""

from __future__ import annotations

import gc
import hashlib
import json
import weakref
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest

from dungeon_manager.ai import tool_call_parser
from dungeon_manager.ai.narration_provider import (
    NarrationProvider,
    NarrationProviderResult,
    NarrationProviderStatus,
)
from dungeon_manager.ai.tool_agent import ToolAgent
from dungeon_manager.ai.tool_executor import ToolExecutor
from dungeon_manager.campaign_runtime import (
    NEKRIA_ID,
    initialize_controlled_fixture,
    load_controlled_campaign_runtime,
)
from dungeon_manager.combat_runtime import compose_controlled_combat_domain
from dungeon_manager.controlled_round_runtime import (
    ControlledRoundRuntime,
    ControlledRoundRuntimeStatus,
)
from dungeon_manager.storage.json_storage import JSONStorage
from dungeon_manager.tools.registry import ToolRegistry
from dungeon_manager.verified_narration import (
    VerifiedNarrationBoundary,
    VerifiedNarrationStatus,
)

from .dice import DiceRollMode, SequenceFaceSource
from .event_journal_store import EventJournalStore
from .game_engine import GameEngine


TIME = datetime(2026, 7, 23, 12, 0, tzinfo=timezone.utc)
_TRANSIENT_TEXT = "Transient narration must not become durable state."


class _RecordingNarrationProvider(NarrationProvider):
    """A recording fake whose external call log survives provider disposal."""

    def __init__(self, calls: list[tuple[str, int]]) -> None:
        self.__calls = calls

    def narrate(self, packet):
        self.__calls.append((packet.source_event_id, packet.source_event_sequence))
        return NarrationProviderResult(
            NarrationProviderStatus.SUCCESS,
            packet.source_event_id,
            packet.source_event_sequence,
            text=_TRANSIENT_TEXT,
        )


def _file_record(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    content = path.read_bytes()
    return {"sha256": hashlib.sha256(content).hexdigest(), "size": len(content)}


def _durable_file_manifest(fixture_root: Path, journal_path: Path) -> dict[str, dict[str, Any] | None]:
    """Hash stable fixture files plus SQLite data and WAL, never `-shm`.

    SQLite's shared-memory sidecar is process-local coordination state, not
    durable campaign data.  The original store has completed its operation
    before this manifest is made, so the remaining SQLite and WAL files are a
    stable baseline for the read-only hydration comparison.
    """

    records: dict[str, dict[str, Any] | None] = {}
    for path in sorted(fixture_root.rglob("*")):
        if path.is_file():
            records[f"fixture/{path.relative_to(fixture_root).as_posix()}"] = _file_record(path)
    records[f"journal/{journal_path.name}"] = _file_record(journal_path)
    records[f"journal/{journal_path.name}-wal"] = _file_record(
        journal_path.with_name(journal_path.name + "-wal")
    )
    return records


def _authoritative_snapshot(runtime) -> dict[str, Any]:
    """Copy only durable identities/content and derived projection facts."""

    return {
        "campaign_id": runtime.definition.campaign_id,
        "journal_id": runtime.definition.journal_id,
        "journal_tail": runtime.event_journal.tail_sequence,
        "entries": [entry.to_dict() for entry in runtime.event_journal.entries],
        "selected_player_character_id": runtime.selected_player_character_id,
        "state": runtime.state_holder.snapshot.to_dict(),
        "state_health": runtime.state_holder.health.to_dict(),
        "durable_health": runtime.pipeline.durable_journal_health.to_dict(),
    }


def _assert_expected_outcome(snapshot: dict[str, Any], expected: dict[str, Any]) -> None:
    assert snapshot["campaign_id"] == "vertical-slice-v1"
    assert snapshot["journal_id"] == "vertical-slice-v1-events"
    assert snapshot["journal_tail"] == 2
    assert snapshot["selected_player_character_id"] == NEKRIA_ID
    assert [entry["sequence"] for entry in snapshot["entries"]] == [1, 2]
    assert [entry["event"]["event_type"] for entry in snapshot["entries"]] == [
        "campaign.player_character_selected",
        "combat.controlled_round_resolved",
    ]
    payload = snapshot["entries"][1]["event"]["payload"]
    assert tuple(payload["initiative"]["order"]) == expected["initiative_order"]
    assert payload["no_action"]["occurred"] is expected["goblin_no_action"]
    assert payload["no_action"]["reason_code"] == expected["goblin_no_action_reason"]
    assert payload["attack"]["hit"] is expected["hit"]
    assert payload["goblin"]["resulting_hit_points"] == expected["goblin_hit_points"]
    assert payload["goblin"]["defeated"] is expected["defeated"]
    assert payload["final"] == expected["final"]
    assert snapshot["state"]["data"]["controlled_combat"] == payload
    assert snapshot["state"]["last_sequence"] == 2
    assert snapshot["state_health"] == {
        "committed_sequence": 2,
        "journal_sequence": 2,
        "projector_status": None,
        "reason_code": None,
        "status": "synchronized",
    }
    assert snapshot["durable_health"] == {
        "durable_tail": 2,
        "journal_id": "vertical-slice-v1-events",
        "local_tail": 2,
        "reason_code": None,
        "status": "synchronized",
    }


@pytest.mark.parametrize(
    ("slug", "mode", "faces", "automatic_faces", "expected"),
    (
        (
            "nekria_first_miss",
            DiceRollMode.MANUAL,
            {"nekria_initiative": 12, "goblin_initiative": 4, "attack": 9, "damage": None},
            None,
            {
                "initiative_order": ("nekria", "goblin-1"),
                "goblin_no_action": False,
                "goblin_no_action_reason": None,
                "hit": False,
                "goblin_hit_points": 7,
                "defeated": False,
                "final": {"active_participant_id": "goblin-1", "encounter_status": "active", "round_number": 1},
            },
        ),
        (
            "goblin_first_surviving_hit",
            DiceRollMode.AUTOMATIC,
            {"nekria_initiative": None, "goblin_initiative": None, "attack": None, "damage": None},
            (3, 18, 10, 2),
            {
                "initiative_order": ("goblin-1", "nekria"),
                "goblin_no_action": True,
                "goblin_no_action_reason": "controlled_slice_no_goblin_behavior",
                "hit": True,
                "goblin_hit_points": 2,
                "defeated": False,
                "final": {"active_participant_id": "goblin-1", "encounter_status": "active", "round_number": 2},
            },
        ),
        (
            "nekria_first_lethal_hit",
            DiceRollMode.MANUAL,
            {"nekria_initiative": 20, "goblin_initiative": 1, "attack": 20, "damage": 8},
            None,
            {
                "initiative_order": ("nekria", "goblin-1"),
                "goblin_no_action": False,
                "goblin_no_action_reason": None,
                "hit": True,
                "goblin_hit_points": 0,
                "defeated": True,
                "final": {"active_participant_id": None, "encounter_status": "completed", "round_number": 1},
            },
        ),
    ),
)
def test_completed_controlled_round_survives_two_genuine_fresh_hydrations(
    tmp_path, monkeypatch, slug, mode, faces, automatic_faces, expected
):
    """Durable fixtures alone reconstruct one completed result twice.

    The restart barriers below make accidental reuse of the original runtime,
    source, provider, dispatcher, event journal, holder, or event objects a
    test failure rather than an assumption.
    """

    fixture_root = tmp_path / "fixture"
    journal_path = tmp_path / "events.sqlite"
    storage = JSONStorage(fixture_root)
    store = EventJournalStore(journal_path)
    assert initialize_controlled_fixture(storage, store).status.value == "success"

    loaded = load_controlled_campaign_runtime(storage, store)
    assert loaded.status.value == "success"
    runtime = loaded.runtime
    selection = runtime.select_player_character(
        NEKRIA_ID,
        command_id=f"select-nekria-restart-{slug}",
        event_id=f"selected-nekria-restart-{slug}",
        occurred_at=TIME,
    )
    assert selection.published_event_entries and selection.published_event_entries[0].sequence == 1
    composition = compose_controlled_combat_domain(runtime)
    assert composition.status.value == "success"
    controlled = ControlledRoundRuntime(runtime, composition.domain)
    source = None if automatic_faces is None else SequenceFaceSource(automatic_faces)
    resolved = controlled.resolve(
        command_id=f"controlled-round-restart-{slug}",
        event_id=f"controlled-round-event-restart-{slug}",
        occurred_at=TIME,
        mode=mode,
        roll_ids={
            "nekria_initiative": f"nekria-init-restart-{slug}",
            "goblin_initiative": f"goblin-init-restart-{slug}",
            "attack": f"attack-restart-{slug}",
            "damage": f"damage-restart-{slug}",
        },
        manual_faces=faces,
        automatic_source=source,
    )
    assert resolved.status is ControlledRoundRuntimeStatus.SUCCESS

    narration_calls: list[tuple[str, int]] = []
    provider = _RecordingNarrationProvider(narration_calls)
    boundary = VerifiedNarrationBoundary(runtime, provider)
    narration = boundary.narrate(resolved)
    assert narration.status is VerifiedNarrationStatus.SUCCESS
    assert narration_calls == [(f"controlled-round-event-restart-{slug}", 2)]

    original = _authoritative_snapshot(runtime)
    _assert_expected_outcome(original, expected)
    assert _TRANSIENT_TEXT not in json.dumps(original, sort_keys=True)
    durable_entries = [entry.to_dict() for entry in EventJournalStore(journal_path).load().entries]
    assert durable_entries == original["entries"]
    durable_files = _durable_file_manifest(fixture_root, journal_path)
    source_calls_before = None if source is None else tuple(source.calls)

    original_refs = {
        "runtime": weakref.ref(runtime),
        "pipeline": weakref.ref(runtime.pipeline),
        "engine": weakref.ref(runtime.game_engine),
        "event_journal": weakref.ref(runtime.event_journal),
        "selection_event": weakref.ref(runtime.event_journal.entries[0].event),
        "controlled_round_event": weakref.ref(runtime.event_journal.entries[1].event),
        "state_holder": weakref.ref(runtime.state_holder),
        "controlled": weakref.ref(controlled),
        "domain": weakref.ref(composition.domain),
        "store": weakref.ref(store),
        "provider": weakref.ref(provider),
        "boundary": weakref.ref(boundary),
    }
    del narration, boundary, provider, resolved, controlled, composition, selection, runtime, loaded, store, storage
    gc.collect()
    assert {name: ref() for name, ref in original_refs.items()} == {
        name: None for name in original_refs
    }

    prohibited_calls: list[str] = []

    def prohibited(name):
        def fail(*args, **kwargs):
            prohibited_calls.append(name)
            raise AssertionError(f"Hydration must not invoke {name}.")

        return fail

    monkeypatch.setattr(GameEngine, "dispatch", prohibited("command_dispatch"))
    monkeypatch.setattr("dungeon_manager.engine.controlled_round.resolve_dice_roll", prohibited("dice"))
    monkeypatch.setattr(EventJournalStore, "append", prohibited("durable_append"))
    monkeypatch.setattr(NarrationProvider, "narrate", prohibited("narration_provider"))
    monkeypatch.setattr(ToolAgent, "ask", prohibited("tool_agent"))
    monkeypatch.setattr(tool_call_parser, "parse_tool_call", prohibited("tool_parser"))
    monkeypatch.setattr(ToolExecutor, "execute", prohibited("tool_executor"))
    monkeypatch.setattr(ToolRegistry, "get_tools", prohibited("tool_registry_lookup"))
    monkeypatch.setattr(ToolRegistry, "get_tool_specs", prohibited("tool_registry_lookup"))
    monkeypatch.setattr(ToolRegistry, "execute", prohibited("tool_registry_execute"))

    first_loaded = load_controlled_campaign_runtime(
        JSONStorage(fixture_root), EventJournalStore(journal_path)
    )
    assert first_loaded.status.value == "success"
    first_runtime = first_loaded.runtime
    first_snapshot = _authoritative_snapshot(first_runtime)
    assert first_snapshot == original
    _assert_expected_outcome(first_snapshot, expected)
    assert [entry.to_dict() for entry in EventJournalStore(journal_path).load().entries] == durable_entries
    assert _durable_file_manifest(fixture_root, journal_path) == durable_files
    assert narration_calls == [(f"controlled-round-event-restart-{slug}", 2)]
    assert source_calls_before is None or tuple(source.calls) == source_calls_before
    assert prohibited_calls == []

    first_refs = {
        "runtime": weakref.ref(first_runtime),
        "pipeline": weakref.ref(first_runtime.pipeline),
        "engine": weakref.ref(first_runtime.game_engine),
        "event_journal": weakref.ref(first_runtime.event_journal),
        "state_holder": weakref.ref(first_runtime.state_holder),
    }
    del first_runtime, first_loaded
    gc.collect()
    assert {name: ref() for name, ref in first_refs.items()} == {
        name: None for name in first_refs
    }

    second_loaded = load_controlled_campaign_runtime(
        JSONStorage(fixture_root), EventJournalStore(journal_path)
    )
    assert second_loaded.status.value == "success"
    second_snapshot = _authoritative_snapshot(second_loaded.runtime)
    assert second_snapshot == original
    _assert_expected_outcome(second_snapshot, expected)
    assert [entry.to_dict() for entry in EventJournalStore(journal_path).load().entries] == durable_entries
    assert _durable_file_manifest(fixture_root, journal_path) == durable_files
    assert narration_calls == [(f"controlled-round-event-restart-{slug}", 2)]
    assert source_calls_before is None or tuple(source.calls) == source_calls_before
    assert prohibited_calls == []
