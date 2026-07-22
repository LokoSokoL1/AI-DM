"""Headless end-to-end acceptance journeys for the accepted first playable."""

from __future__ import annotations

import gc
import weakref
from datetime import datetime, timezone
from typing import Any

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


TIME = datetime(2026, 7, 24, 12, 0, tzinfo=timezone.utc)


class _OrderingStore(EventJournalStore):
    """Observes a successful durable write before local publication returns."""

    def __init__(self, path) -> None:
        super().__init__(path)
        self.after_append = None

    def append(self, entries, *, expected_tail_sequence, expected_journal_id=None):
        result = super().append(
            entries,
            expected_tail_sequence=expected_tail_sequence,
            expected_journal_id=expected_journal_id,
        )
        if result.status.value == "success" and result.appended_count and self.after_append:
            self.after_append()
        return result


class _RecordingNarrationProvider(NarrationProvider):
    """A deterministic narration-only provider with no runtime authority."""

    def __init__(self, calls: list[Any]) -> None:
        self.__calls = calls

    def narrate(self, packet):
        self.__calls.append(packet)
        return NarrationProviderResult(
            NarrationProviderStatus.SUCCESS,
            packet.source_event_id,
            packet.source_event_sequence,
            text="Verified narration is transient presentation only.",
        )


def _runtime(tmp_path):
    fixture_path = tmp_path / "fixture"
    journal_path = tmp_path / "events.sqlite"
    storage = JSONStorage(fixture_path)
    store = _OrderingStore(journal_path)
    assert initialize_controlled_fixture(storage, store).status.value == "success"
    loaded = load_controlled_campaign_runtime(storage, store)
    assert loaded.status.value == "success"
    runtime = loaded.runtime
    assert runtime.event_journal.tail_sequence == runtime.state_holder.snapshot.last_sequence == 0
    assert runtime.selected_player_character_id is None
    return fixture_path, journal_path, storage, store, loaded, runtime


def _select_and_enter(runtime, slug):
    selected = runtime.select_player_character(
        NEKRIA_ID,
        command_id=f"acceptance-select-{slug}",
        event_id=f"acceptance-select-event-{slug}",
        occurred_at=TIME,
    )
    assert selected.published_event_entries[0].sequence == 1
    assert selected.published_event_entries[0].event.event_type == "campaign.player_character_selected"
    assert runtime.selected_player_character_id == NEKRIA_ID
    composition = compose_controlled_combat_domain(runtime)
    assert composition.status.value == "success"
    assert composition.domain.definition.scene_id == runtime.current_scene_id
    assert tuple(participant_id for participant_id, _ in composition.domain.seed.participant_hit_points) == (
        "nekria",
        "goblin-1",
    )
    return selected, composition, ControlledRoundRuntime(runtime, composition.domain)


def _round_arguments(slug, *, mode, faces, source=None):
    return {
        "command_id": f"acceptance-round-{slug}",
        "event_id": f"acceptance-round-event-{slug}",
        "occurred_at": TIME,
        "mode": mode,
        "roll_ids": {
            "nekria_initiative": f"acceptance-nekria-init-{slug}",
            "goblin_initiative": f"acceptance-goblin-init-{slug}",
            "attack": f"acceptance-attack-{slug}",
            "damage": f"acceptance-damage-{slug}",
        },
        "manual_faces": faces,
        "automatic_source": source,
    }


def _facts(runtime):
    return {
        "entries": [entry.to_dict() for entry in runtime.event_journal.entries],
        "state": runtime.state_holder.snapshot.to_dict(),
        "selected": runtime.selected_player_character_id,
        "tail": runtime.event_journal.tail_sequence,
        "durable_health": runtime.pipeline.durable_journal_health.to_dict(),
        "projection_health": runtime.state_holder.health.to_dict(),
    }


def _assert_completed_result(runtime, store, result, *, expected):
    pipeline = result.pipeline_result
    assert result.status is ControlledRoundRuntimeStatus.SUCCESS
    assert pipeline.durable_publication.status.value == "committed_synchronized"
    assert pipeline.publication_disposition.value == "published"
    assert pipeline.projection_disposition.value == "projected"
    assert len(pipeline.published_event_entries) == 1
    entry = pipeline.published_event_entries[0]
    assert entry.sequence == 2
    assert entry.event.event_id == expected["event_id"]
    assert entry.event.originating_command_id == expected["command_id"]
    assert entry.event.event_type == "combat.controlled_round_resolved"
    durable = store.load()
    assert durable.tail_sequence == 2
    assert [item.to_dict() for item in durable.entries] == [
        item.to_dict() for item in runtime.event_journal.entries
    ]
    payload = entry.event.to_dict()["payload"]
    assert payload["initiative"]["order"] == list(expected["order"])
    assert payload["no_action"] == expected["no_action"]
    assert payload["attack"]["attack_roll"]["natural_faces"] == [expected["attack_face"]]
    assert payload["attack"]["attack_roll"]["total"] == expected["attack_total"]
    assert payload["attack"]["hit"] is expected["hit"]
    assert payload["goblin"] == expected["goblin"]
    assert payload["final"] == expected["final"]
    assert runtime.state_holder.snapshot.data["controlled_combat"] == entry.event.payload
    assert runtime.event_journal.tail_sequence == runtime.state_holder.snapshot.last_sequence == 2
    return entry, payload


def _narrate(runtime, result, entry):
    calls: list[Any] = []
    provider = _RecordingNarrationProvider(calls)
    boundary = VerifiedNarrationBoundary(runtime, provider)
    durable_before = tuple(runtime.event_journal.entries)
    state_before = runtime.state_holder.snapshot
    narration = boundary.narrate(result)
    assert narration.status is VerifiedNarrationStatus.SUCCESS
    assert calls == [narration.packet]
    assert narration.packet.source_event_id == entry.event.event_id
    assert narration.packet.source_event_sequence == entry.sequence
    assert runtime.event_journal.entries == durable_before
    assert runtime.state_holder.snapshot == state_before
    return calls, provider, boundary, narration


def _restart_from_durable(*, fixture_path, journal_path, authoritative, calls, monkeypatch):
    prohibited_calls: list[str] = []

    def prohibited(name):
        def fail(*args, **kwargs):
            prohibited_calls.append(name)
            raise AssertionError(f"Restart hydration must not invoke {name}.")

        return fail

    monkeypatch.setattr(GameEngine, "dispatch", prohibited("dispatch"))
    monkeypatch.setattr("dungeon_manager.engine.controlled_round.resolve_dice_roll", prohibited("dice"))
    monkeypatch.setattr(EventJournalStore, "append", prohibited("append"))
    monkeypatch.setattr(NarrationProvider, "narrate", prohibited("narration"))
    monkeypatch.setattr(ToolAgent, "ask", prohibited("tool_agent"))
    monkeypatch.setattr(tool_call_parser, "parse_tool_call", prohibited("parser"))
    monkeypatch.setattr(ToolRegistry, "get_tools", prohibited("registry_lookup"))
    monkeypatch.setattr(ToolRegistry, "get_tool_specs", prohibited("registry_lookup"))
    monkeypatch.setattr(ToolRegistry, "execute", prohibited("tool"))
    monkeypatch.setattr(ToolExecutor, "execute", prohibited("executor"))

    restarted = load_controlled_campaign_runtime(
        JSONStorage(fixture_path), EventJournalStore(journal_path)
    )
    assert restarted.status.value == "success"
    fresh = restarted.runtime
    assert _facts(fresh) == authoritative
    assert calls and len(calls) == 1
    assert prohibited_calls == []
    return fresh


def test_manual_first_playable_journey_is_staged_durable_and_restartable(tmp_path, monkeypatch):
    def run_original():
        fixture_path, journal_path, storage, store, loaded, runtime = _runtime(tmp_path)
        selected, composition, controlled = _select_and_enter(runtime, "manual")
        empty = {"nekria_initiative": None, "goblin_initiative": None, "attack": None, "damage": None}
        first = controlled.resolve(**_round_arguments("manual", mode=DiceRollMode.MANUAL, faces=empty))
        second = controlled.resolve(**_round_arguments("manual-2", mode=DiceRollMode.MANUAL, faces={**empty, "nekria_initiative": 12}))
        third = controlled.resolve(**_round_arguments("manual-3", mode=DiceRollMode.MANUAL, faces={**empty, "nekria_initiative": 12, "goblin_initiative": 4}))
        fourth = controlled.resolve(**_round_arguments("manual-4", mode=DiceRollMode.MANUAL, faces={**empty, "nekria_initiative": 12, "goblin_initiative": 4, "attack": 10}))
        assert [item.status for item in (first, second, third, fourth)] == [ControlledRoundRuntimeStatus.INITIATIVE_INPUT_REQUIRED, ControlledRoundRuntimeStatus.INITIATIVE_INPUT_REQUIRED, ControlledRoundRuntimeStatus.ATTACK_INPUT_REQUIRED, ControlledRoundRuntimeStatus.DAMAGE_INPUT_REQUIRED]
        assert [item.details["roll_id"] for item in (first, second, third, fourth)] == ["acceptance-nekria-init-manual", "acceptance-goblin-init-manual-2", "acceptance-attack-manual-3", "acceptance-damage-manual-4"]
        assert store.load().tail_sequence == runtime.event_journal.tail_sequence == 1
        assert "controlled_combat" not in runtime.state_holder.snapshot.data
        durable_before_local = []

        def observe_durable_before_local():
            durable_before_local.append((store.load().tail_sequence, runtime.event_journal.tail_sequence, runtime.state_holder.snapshot.last_sequence, "controlled_combat" in runtime.state_holder.snapshot.data))

        store.after_append = observe_durable_before_local
        result = controlled.resolve(**_round_arguments("manual-final", mode=DiceRollMode.MANUAL, faces={"nekria_initiative": 12, "goblin_initiative": 4, "attack": 10, "damage": 2}))
        store.after_append = None
        entry, _ = _assert_completed_result(runtime, store, result, expected={"command_id": "acceptance-round-manual-final", "event_id": "acceptance-round-event-manual-final", "order": ("nekria", "goblin-1"), "no_action": {"occurred": False, "reason_code": None}, "attack_face": 10, "attack_total": 15, "hit": True, "goblin": {"applied_damage": 5, "defeated": False, "previous_hit_points": 7, "resulting_hit_points": 2, "rolled_damage": 5}, "final": {"active_participant_id": "goblin-1", "encounter_status": "active", "round_number": 1}})
        assert durable_before_local == [(2, 1, 1, False)]
        calls, provider, boundary, narration = _narrate(runtime, result, entry)
        references = {"runtime": weakref.ref(runtime), "pipeline": weakref.ref(runtime.pipeline), "engine": weakref.ref(runtime.game_engine), "journal": weakref.ref(runtime.event_journal), "holder": weakref.ref(runtime.state_holder), "controlled": weakref.ref(controlled), "domain": weakref.ref(composition.domain), "store": weakref.ref(store), "provider": weakref.ref(provider), "boundary": weakref.ref(boundary)}
        return fixture_path, journal_path, _facts(runtime), calls, references

    fixture_path, journal_path, authoritative, calls, references = run_original()
    gc.collect()
    assert all(reference() is None for reference in references.values())
    _restart_from_durable(fixture_path=fixture_path, journal_path=journal_path, authoritative=authoritative, calls=calls, monkeypatch=monkeypatch)


def test_automatic_first_playable_journey_is_durable_narrated_and_restartable(tmp_path, monkeypatch):
    def run_original():
        fixture_path, journal_path, storage, store, loaded, runtime = _runtime(tmp_path)
        selected, composition, controlled = _select_and_enter(runtime, "automatic")
        source = SequenceFaceSource([3, 18, 20, 8])
        durable_before_local = []

        def observe_durable_before_local():
            durable_before_local.append((store.load().tail_sequence, runtime.event_journal.tail_sequence, runtime.state_holder.snapshot.last_sequence, "controlled_combat" in runtime.state_holder.snapshot.data))

        store.after_append = observe_durable_before_local
        result = controlled.resolve(**_round_arguments("automatic", mode=DiceRollMode.AUTOMATIC, faces={"nekria_initiative": None, "goblin_initiative": None, "attack": None, "damage": None}, source=source))
        store.after_append = None
        assert source.calls == [(1, 20), (1, 20), (1, 20), (1, 8)]
        entry, _ = _assert_completed_result(runtime, store, result, expected={"command_id": "acceptance-round-automatic", "event_id": "acceptance-round-event-automatic", "order": ("goblin-1", "nekria"), "no_action": {"occurred": True, "reason_code": "controlled_slice_no_goblin_behavior"}, "attack_face": 20, "attack_total": 25, "hit": True, "goblin": {"applied_damage": 7, "defeated": True, "previous_hit_points": 7, "resulting_hit_points": 0, "rolled_damage": 11}, "final": {"active_participant_id": None, "encounter_status": "completed", "round_number": 1}})
        assert durable_before_local == [(2, 1, 1, False)]
        calls, provider, boundary, narration = _narrate(runtime, result, entry)
        references = {"runtime": weakref.ref(runtime), "pipeline": weakref.ref(runtime.pipeline), "engine": weakref.ref(runtime.game_engine), "journal": weakref.ref(runtime.event_journal), "holder": weakref.ref(runtime.state_holder), "controlled": weakref.ref(controlled), "domain": weakref.ref(composition.domain), "store": weakref.ref(store), "provider": weakref.ref(provider), "boundary": weakref.ref(boundary), "source": weakref.ref(source)}
        return fixture_path, journal_path, _facts(runtime), calls, references

    fixture_path, journal_path, authoritative, calls, references = run_original()
    gc.collect()
    assert all(reference() is None for reference in references.values())
    _restart_from_durable(fixture_path=fixture_path, journal_path=journal_path, authoritative=authoritative, calls=calls, monkeypatch=monkeypatch)
