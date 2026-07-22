import ast
import json
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone
from pathlib import Path

import pytest

from dungeon_manager.ai.narration_provider import (
    NarrationProvider,
    NarrationProviderResult,
    NarrationProviderStatus,
)
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
from dungeon_manager.verified_narration import (
    VerifiedNarrationBoundary,
    VerifiedNarrationStatus,
)

from ._json import thaw_json_value
from .controlled_round import (
    CONTROLLED_ROUND_EVENT,
    CONTROLLED_ROUND_SCHEMA_VERSION,
)
from .dice import DiceRollMode, DiceRollProvenance, SequenceFaceSource
from .durable_journal import EventJournalStoreResult, EventJournalStoreStatus
from .event_journal_store import EventJournalStore
from .game_event import GameEvent
from .journals import GameEventJournalEntry
from .verified_narration import (
    NarrationPacketBuildStatus,
    VerifiedNarrationPacket,
    build_verified_narration_packet,
)
from .world_state import WorldState, WorldStateProjector


TIME = datetime(2026, 7, 22, 18, 0, tzinfo=timezone.utc)


class RecordingNarrationProvider(NarrationProvider):
    def __init__(self, *, text="Nekria's verified strike is resolved.", failure=None, raises=None):
        self.text = text
        self.failure = failure
        self.raises = raises
        self.calls = []

    def narrate(self, packet):
        self.calls.append(packet)
        if self.raises is not None:
            raise self.raises
        if self.failure is not None:
            return NarrationProviderResult(
                NarrationProviderStatus.FAILURE,
                packet.source_event_id,
                packet.source_event_sequence,
                reason_code=self.failure,
            )
        return NarrationProviderResult(
            NarrationProviderStatus.SUCCESS,
            packet.source_event_id,
            packet.source_event_sequence,
            text=self.text,
        )


class ObservedEventJournalStore(EventJournalStore):
    def __init__(self, path):
        super().__init__(path)
        self.append_observer = None
        self.fail_appends = False

    def append(self, entries, *, expected_tail_sequence, expected_journal_id=None):
        if self.append_observer is not None:
            self.append_observer()
        if self.fail_appends:
            return EventJournalStoreResult(
                EventJournalStoreStatus.STORAGE_FAILURE,
                journal_id=expected_journal_id,
                previous_tail=expected_tail_sequence,
                tail_sequence=expected_tail_sequence,
                reason_code="append_failed",
                error="The event-journal batch could not be persisted.",
            )
        return super().append(
            entries,
            expected_tail_sequence=expected_tail_sequence,
            expected_journal_id=expected_journal_id,
        )


def _round_arguments(*, mode=DiceRollMode.MANUAL, faces=None, source=None):
    return {
        "command_id": "round-command-narration-001",
        "event_id": "round-event-narration-001",
        "occurred_at": TIME,
        "mode": mode,
        "roll_ids": {
            "nekria_initiative": "nekria-initiative-narration-001",
            "goblin_initiative": "goblin-initiative-narration-001",
            "attack": "attack-narration-001",
            "damage": "damage-narration-001",
        },
        "manual_faces": faces
        or {
            "nekria_initiative": None,
            "goblin_initiative": None,
            "attack": None,
            "damage": None,
        },
        "automatic_source": source,
    }


def _runtime(tmp_path, *, store=None):
    storage = JSONStorage(tmp_path / "fixture")
    store = store or EventJournalStore(tmp_path / "events.sqlite")
    assert initialize_controlled_fixture(storage, store).status.value == "success"
    loaded = load_controlled_campaign_runtime(storage, store)
    assert loaded.status.value == "success"
    runtime = loaded.runtime
    selection = runtime.select_player_character(
        NEKRIA_ID,
        command_id="select-nekria-narration",
        event_id="selected-nekria-narration",
        occurred_at=TIME,
    )
    assert selection.publication_disposition.value == "published"
    composition = compose_controlled_combat_domain(runtime)
    assert composition.status.value == "success"
    return ControlledRoundRuntime(runtime, composition.domain), runtime, store, storage


def _resolve_manual(controlled, faces):
    return controlled.resolve(**_round_arguments(faces=faces))


def test_verified_nekria_first_miss_packet_is_exact_immutable_and_transient(tmp_path):
    controlled, runtime, store, _ = _runtime(tmp_path)
    resolved = _resolve_manual(
        controlled,
        {
            "nekria_initiative": 12,
            "goblin_initiative": 4,
            "attack": 9,
            "damage": None,
        },
    )
    provider = RecordingNarrationProvider()
    boundary = VerifiedNarrationBoundary(runtime, provider)
    durable_before = store.load().entries
    state_before = runtime.state_holder.snapshot

    narration = boundary.narrate(resolved)

    assert narration.status is VerifiedNarrationStatus.SUCCESS
    packet = narration.packet
    assert isinstance(packet, VerifiedNarrationPacket)
    assert provider.calls == [packet]
    assert packet.source_event_id == "round-event-narration-001"
    assert packet.source_event_sequence == 2
    assert (packet.campaign_id, packet.scene_id, packet.encounter_id) == (
        "vertical-slice-v1",
        "controlled-goblin-encounter",
        "controlled-goblin-encounter",
    )
    assert (packet.attacker_id, packet.target_id, packet.attack_id) == (
        "nekria",
        "goblin-1",
        "nekria-rapier",
    )
    assert packet.dice_mode is DiceRollMode.MANUAL
    assert packet.nekria_initiative.to_dict() == {
        "modifier": 3,
        "natural_face": 12,
        "provenance": "human_manual",
        "total": 15,
    }
    assert packet.goblin_initiative.to_dict() == {
        "modifier": 2,
        "natural_face": 4,
        "provenance": "human_manual",
        "total": 6,
    }
    assert packet.initiative_order == ("nekria", "goblin-1")
    assert packet.goblin_no_action_occurred is False
    assert packet.goblin_no_action_reason is None
    assert packet.attack.natural_face == 9
    assert packet.attack.modifier == 5
    assert packet.attack.total == 14
    assert packet.target_armor_class == 15
    assert packet.hit is False and packet.damage is None
    assert (packet.goblin_hit_points_before, packet.goblin_hit_points_after) == (7, 7)
    assert packet.goblin_applied_damage == 0
    assert packet.goblin_defeated is False
    assert packet.final_round_number == 1
    assert packet.final_active_participant_id == "goblin-1"
    assert packet.encounter_completed is False
    assert narration.text == "Nekria's verified strike is resolved."
    assert store.load().entries == durable_before
    assert runtime.state_holder.snapshot == state_before
    with pytest.raises(FrozenInstanceError):
        packet.hit = True
    serialized = packet.to_dict()
    serialized["initiative_order"].reverse()
    serialized["attack"]["total"] = 999
    assert packet.initiative_order == ("nekria", "goblin-1")
    assert packet.attack.total == 14


def test_verified_goblin_first_automatic_hit_records_no_action_and_surviving_turn(tmp_path):
    controlled, runtime, store, _ = _runtime(tmp_path)
    source = SequenceFaceSource([3, 18, 10, 2])
    resolved = controlled.resolve(
        **_round_arguments(mode=DiceRollMode.AUTOMATIC, source=source)
    )
    source_calls_before = tuple(source.calls)
    provider = RecordingNarrationProvider()

    narration = VerifiedNarrationBoundary(runtime, provider).narrate(resolved)

    packet = narration.packet
    assert narration.status is VerifiedNarrationStatus.SUCCESS
    assert packet.dice_mode is DiceRollMode.AUTOMATIC
    assert packet.initiative_order == ("goblin-1", "nekria")
    assert packet.goblin_no_action_occurred is True
    assert packet.goblin_no_action_reason == "controlled_slice_no_goblin_behavior"
    assert packet.nekria_initiative.total == 6
    assert packet.goblin_initiative.total == 20
    assert packet.attack.to_dict() == {
        "modifier": 5,
        "natural_face": 10,
        "provenance": "engine_automatic",
        "total": 15,
    }
    assert packet.hit is True
    assert packet.damage.to_dict() == {
        "modifier": 3,
        "natural_face": 2,
        "provenance": "engine_automatic",
        "total": 5,
    }
    assert packet.goblin_hit_points_after == 2
    assert packet.goblin_applied_damage == 5
    assert packet.final_round_number == 2
    assert packet.final_active_participant_id == "goblin-1"
    assert packet.encounter_completed is False
    assert tuple(source.calls) == source_calls_before
    assert store.load().tail_sequence == runtime.state_holder.snapshot.last_sequence == 2


def test_verified_defeating_hit_has_terminal_facts_without_active_participant(tmp_path):
    controlled, runtime, _, _ = _runtime(tmp_path)
    resolved = _resolve_manual(
        controlled,
        {
            "nekria_initiative": 1,
            "goblin_initiative": 20,
            "attack": 20,
            "damage": 8,
        },
    )

    packet = VerifiedNarrationBoundary(
        runtime, RecordingNarrationProvider()
    ).narrate(resolved).packet

    assert packet.initiative_order == ("goblin-1", "nekria")
    assert packet.goblin_hit_points_before == 7
    assert packet.damage.total == 11
    assert packet.goblin_hit_points_after == 0
    assert packet.goblin_applied_damage == 7
    assert packet.goblin_defeated is True
    assert packet.final_round_number == 1
    assert packet.final_active_participant_id is None
    assert packet.encounter_completed is True


@pytest.mark.parametrize("provider_kind", ["reported_failure", "exception"])
def test_provider_failure_is_controlled_one_shot_and_cannot_change_authority(tmp_path, provider_kind):
    controlled, runtime, store, _ = _runtime(tmp_path)
    resolved = _resolve_manual(
        controlled,
        {
            "nekria_initiative": 12,
            "goblin_initiative": 4,
            "attack": 9,
            "damage": None,
        },
    )
    provider = (
        RecordingNarrationProvider(failure="provider_unavailable")
        if provider_kind == "reported_failure"
        else RecordingNarrationProvider(raises=RuntimeError("secret provider detail"))
    )
    boundary = VerifiedNarrationBoundary(runtime, provider)
    durable_before = store.load().entries
    local_before = runtime.event_journal.entries
    state_before = runtime.state_holder.snapshot

    failed = boundary.narrate(resolved)
    repeated = boundary.narrate(resolved)

    assert failed.status is VerifiedNarrationStatus.PROVIDER_FAILURE
    assert failed.packet is None and failed.text is None
    assert len(provider.calls) == 1
    assert repeated.status is VerifiedNarrationStatus.ALREADY_ATTEMPTED
    assert store.load().entries == durable_before
    assert runtime.event_journal.entries == local_before
    assert runtime.state_holder.snapshot == state_before
    assert "secret" not in json.dumps(failed.to_dict())


def test_mismatched_or_untyped_provider_result_is_rejected_without_retry(tmp_path):
    controlled, runtime, _, _ = _runtime(tmp_path)
    resolved = _resolve_manual(
        controlled,
        {
            "nekria_initiative": 12,
            "goblin_initiative": 4,
            "attack": 9,
            "damage": None,
        },
    )

    class WrongProvider(NarrationProvider):
        def __init__(self):
            self.calls = 0

        def narrate(self, packet):
            self.calls += 1
            return {"text": "not a typed provider result"}

    provider = WrongProvider()
    boundary = VerifiedNarrationBoundary(runtime, provider)

    assert boundary.narrate(resolved).status is VerifiedNarrationStatus.INVALID_PROVIDER_RESULT
    assert boundary.narrate(resolved).status is VerifiedNarrationStatus.ALREADY_ATTEMPTED
    assert provider.calls == 1


def test_incomplete_round_never_invokes_provider_or_mutates_state(tmp_path):
    controlled, runtime, store, _ = _runtime(tmp_path)
    incomplete = controlled.resolve(**_round_arguments())
    provider = RecordingNarrationProvider()
    boundary = VerifiedNarrationBoundary(runtime, provider)
    before = runtime.state_holder.snapshot

    narration = boundary.narrate(incomplete)

    assert incomplete.status is ControlledRoundRuntimeStatus.INITIATIVE_INPUT_REQUIRED
    assert narration.status is VerifiedNarrationStatus.INELIGIBLE
    assert provider.calls == []
    assert store.load().tail_sequence == 1
    assert runtime.state_holder.snapshot == before


def test_provider_is_not_called_before_durable_append_and_success_adds_no_event(tmp_path):
    store = ObservedEventJournalStore(tmp_path / "events.sqlite")
    controlled, runtime, store, _ = _runtime(tmp_path, store=store)
    provider = RecordingNarrationProvider()
    store.append_observer = lambda: pytest.fail("Narration ran before durable append") if provider.calls else None
    resolved = _resolve_manual(
        controlled,
        {
            "nekria_initiative": 12,
            "goblin_initiative": 4,
            "attack": 9,
            "damage": None,
        },
    )
    tail_before_narration = store.load().tail_sequence

    narration = VerifiedNarrationBoundary(runtime, provider).narrate(resolved)

    assert narration.status is VerifiedNarrationStatus.SUCCESS
    assert tail_before_narration == store.load().tail_sequence == 2
    assert runtime.event_journal.tail_sequence == runtime.state_holder.snapshot.last_sequence == 2


def test_publication_or_projection_failure_is_ineligible_for_narration(tmp_path):
    failing_store = ObservedEventJournalStore(tmp_path / "publication.sqlite")
    controlled, runtime, failing_store, _ = _runtime(
        tmp_path / "publication", store=failing_store
    )
    failing_store.fail_appends = True
    provider = RecordingNarrationProvider()
    publication_failure = _resolve_manual(
        controlled,
        {
            "nekria_initiative": 12,
            "goblin_initiative": 4,
            "attack": 9,
            "damage": None,
        },
    )

    assert publication_failure.status is ControlledRoundRuntimeStatus.PUBLICATION_FAILURE
    assert VerifiedNarrationBoundary(runtime, provider).narrate(publication_failure).status is VerifiedNarrationStatus.INELIGIBLE
    assert provider.calls == []
    assert failing_store.load().tail_sequence == runtime.event_journal.tail_sequence == runtime.state_holder.snapshot.last_sequence == 1

    controlled, runtime, store, _ = _runtime(tmp_path / "projection")
    failing_projector = WorldStateProjector()

    def reject_projection(state_data, event):
        raise ValueError("controlled test projection failure")

    failing_projector.register_reducer(
        CONTROLLED_ROUND_EVENT,
        CONTROLLED_ROUND_SCHEMA_VERSION,
        reject_projection,
    )
    runtime.pipeline._projector = failing_projector
    projection_failure = _resolve_manual(
        controlled,
        {
            "nekria_initiative": 12,
            "goblin_initiative": 4,
            "attack": 9,
            "damage": None,
        },
    )
    projection_provider = RecordingNarrationProvider()

    assert projection_failure.status is ControlledRoundRuntimeStatus.PUBLICATION_FAILURE
    assert VerifiedNarrationBoundary(runtime, projection_provider).narrate(projection_failure).status is VerifiedNarrationStatus.INELIGIBLE
    assert projection_provider.calls == []
    assert store.load().tail_sequence == runtime.event_journal.tail_sequence == 2
    assert runtime.state_holder.snapshot.last_sequence == 1


def test_packet_builder_rejects_projection_disagreement_and_malformed_event(tmp_path):
    controlled, runtime, _, _ = _runtime(tmp_path)
    resolved = _resolve_manual(
        controlled,
        {
            "nekria_initiative": 12,
            "goblin_initiative": 4,
            "attack": 9,
            "damage": None,
        },
    )
    entry = resolved.pipeline_result.published_event_entries[0]
    state_data = thaw_json_value(runtime.state_holder.snapshot.data)
    state_data["controlled_combat"]["final"]["round_number"] = 2
    mismatched_state = WorldState(state_data, entry.sequence)

    mismatch = build_verified_narration_packet(entry, mismatched_state)

    assert mismatch.status is NarrationPacketBuildStatus.SOURCE_MISMATCH
    assert mismatch.packet is None
    malformed_payload = thaw_json_value(entry.event.payload)
    malformed_payload["attack"]["target_ac"] = 999
    malformed_event = GameEvent(
        event_type=entry.event.event_type,
        provenance=entry.event.provenance,
        payload=malformed_payload,
        originating_command_id=entry.event.originating_command_id,
        actor_id=entry.event.actor_id,
        schema_version=entry.event.schema_version,
        occurred_at=entry.event.occurred_at,
        event_id="malformed-round-event",
    )
    malformed = build_verified_narration_packet(
        GameEventJournalEntry(entry.sequence, malformed_event),
        runtime.state_holder.snapshot,
    )
    assert malformed.status is NarrationPacketBuildStatus.INVALID_EVENT
    assert malformed.packet is None


def test_boundary_rejects_projection_disagreement_before_provider(tmp_path):
    controlled, runtime, _, _ = _runtime(tmp_path)
    resolved = _resolve_manual(
        controlled,
        {
            "nekria_initiative": 12,
            "goblin_initiative": 4,
            "attack": 9,
            "damage": None,
        },
    )
    mismatched_data = thaw_json_value(runtime.state_holder.snapshot.data)
    mismatched_data["controlled_combat"]["goblin"]["resulting_hit_points"] = 6
    runtime.state_holder._WorldStateHolder__state = WorldState(mismatched_data, 2)
    provider = RecordingNarrationProvider()

    narration = VerifiedNarrationBoundary(runtime, provider).narrate(resolved)

    assert narration.status is VerifiedNarrationStatus.SOURCE_MISMATCH
    assert narration.packet is None
    assert provider.calls == []


def test_restart_hydrates_authority_without_automatic_narration_or_replay(tmp_path):
    controlled, runtime, store, storage = _runtime(tmp_path)
    source = SequenceFaceSource([20, 1, 20, 8])
    resolved = controlled.resolve(
        **_round_arguments(mode=DiceRollMode.AUTOMATIC, source=source)
    )
    provider = RecordingNarrationProvider()
    assert VerifiedNarrationBoundary(runtime, provider).narrate(resolved).status is VerifiedNarrationStatus.SUCCESS
    durable_before = store.load().entries
    source_calls_before = tuple(source.calls)

    fresh_provider = RecordingNarrationProvider()
    fresh_runtime = load_controlled_campaign_runtime(
        JSONStorage(storage.base_path), EventJournalStore(store.path)
    ).runtime

    assert fresh_provider.calls == []
    assert tuple(source.calls) == source_calls_before
    assert fresh_runtime.event_journal.entries == durable_before
    assert fresh_runtime.state_holder.snapshot.data == runtime.state_holder.snapshot.data
    assert EventJournalStore(store.path).load().entries == durable_before
    assert fresh_runtime.state_holder.snapshot.data["controlled_combat"]["goblin"]["defeated"] is True


def test_narration_modules_exclude_tool_agent_tools_and_mutating_dependencies():
    package_root = Path(__file__).resolve().parent.parent
    engine_path = package_root / "engine" / "verified_narration.py"
    provider_path = package_root / "ai" / "narration_provider.py"
    boundary_path = package_root / "verified_narration.py"

    engine_tree = ast.parse(engine_path.read_text(encoding="utf-8"), filename=str(engine_path))
    engine_relative = {
        node.module
        for node in ast.walk(engine_tree)
        if isinstance(node, ast.ImportFrom) and node.level > 0
    }
    assert engine_relative == {"_json", "controlled_round", "dice", "journals", "world_state"}

    combined_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (engine_path, provider_path, boundary_path)
    ).lower()
    for forbidden in (
        "tool_agent",
        "tool_call_parser",
        "tool_executor",
        "toolregistry",
        "ollama",
        "foundry",
        "sqlite3",
        "resolve_dice_roll",
    ):
        assert forbidden not in combined_source
    provider_signature = ast.parse(
        provider_path.read_text(encoding="utf-8"), filename=str(provider_path)
    )
    narrate = next(
        node
        for node in ast.walk(provider_signature)
        if isinstance(node, ast.FunctionDef) and node.name == "narrate"
    )
    assert [argument.arg for argument in narrate.args.args] == ["self", "packet"]


def test_provider_result_is_typed_immutable_and_safely_serialized():
    result = NarrationProviderResult(
        NarrationProviderStatus.SUCCESS,
        "round-event-narration-001",
        2,
        text="A verified result.",
    )
    assert result.to_dict() == {
        "reason_code": None,
        "source_event_id": "round-event-narration-001",
        "source_event_sequence": 2,
        "status": "success",
        "text": "A verified result.",
    }
    with pytest.raises(FrozenInstanceError):
        result.text = "changed"
    with pytest.raises(ValueError):
        NarrationProviderResult(
            NarrationProviderStatus.SUCCESS,
            "round-event-narration-001",
            True,
            text="Invalid sequence.",
        )
