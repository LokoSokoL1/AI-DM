from __future__ import annotations

import hashlib
from datetime import datetime, timezone

import pytest

from dungeon_manager.adapters.in_process_controlled_fixture import (
    InProcessControlledFixtureAdapter,
)
from dungeon_manager.ai import tool_call_parser
from dungeon_manager.ai.narration_provider import (
    NarrationProvider,
    NarrationProviderResult,
    NarrationProviderStatus,
)
from dungeon_manager.ai.tool_agent import ToolAgent
from dungeon_manager.ai.tool_executor import ToolExecutor
from dungeon_manager.campaign_runtime import (
    initialize_controlled_fixture,
    load_controlled_campaign_runtime,
)
from dungeon_manager.engine.audited_pipeline import AuditedCommandPipeline
from dungeon_manager.engine.dice import SequenceFaceSource
from dungeon_manager.engine.event_journal_store import EventJournalStore
from dungeon_manager.engine.game_engine import GameEngine
from dungeon_manager.storage.json_storage import JSONStorage
from dungeon_manager.tools.registry import ToolRegistry
from dungeon_manager.verified_narration import VerifiedNarrationBoundary

from .contracts import (
    AuthorityReference,
    CapabilityKey,
    CapabilityReason,
    CapabilityStatus,
    ClientDiceMode,
    ContractVersion,
    DiagnosticCode,
    DurableCommitState,
    IdentityKind,
    LocalPublicationState,
    MechanicalState,
    OperationCorrelationRequest,
    PresentationState,
    ProjectionState,
    ResolveControlledRoundRequest,
    SelectPlayerCharacterRequest,
    SubmissionState,
    SynchronizationState,
)
from .controlled_fixture import ControlledFixtureFacade


TIME = datetime(2026, 7, 29, 18, 0, tzinfo=timezone.utc)
STAGES = ("nekria_initiative", "goblin_initiative", "attack", "damage")


class _OrderingStore(EventJournalStore):
    def __init__(self, path):
        super().__init__(path)
        self.after_append = None

    def append(self, entries, *, expected_tail_sequence, expected_journal_id=None):
        result = super().append(
            entries,
            expected_tail_sequence=expected_tail_sequence,
            expected_journal_id=expected_journal_id,
        )
        if result.status.value == "success" and result.appended_count:
            if self.after_append is not None:
                self.after_append()
        return result


class _FailingNarrationProvider(NarrationProvider):
    def __init__(self):
        self.calls = 0

    def narrate(self, packet):
        self.calls += 1
        raise RuntimeError(
            "C:\\secret\\events.sqlite bearer-token prompt hidden-payload"
        )


class _SuccessfulNarrationProvider(NarrationProvider):
    def __init__(self):
        self.calls = []

    def narrate(self, packet):
        self.calls.append(packet)
        return NarrationProviderResult(
            NarrationProviderStatus.SUCCESS,
            packet.source_event_id,
            packet.source_event_sequence,
            text="Verified transient presentation.",
        )


def reference(kind, value):
    return AuthorityReference(kind, value)


def fixture(tmp_path, *, store_type=EventJournalStore):
    fixture_path = tmp_path / "fixture"
    journal_path = tmp_path / "events.sqlite"
    storage = JSONStorage(fixture_path)
    store = store_type(journal_path)
    assert initialize_controlled_fixture(storage, store).status.value == "success"
    loaded = load_controlled_campaign_runtime(storage, store)
    assert loaded.status.value == "success"
    return fixture_path, journal_path, storage, store, loaded.runtime


def facade_for(runtime, **adapter_options):
    adapter = InProcessControlledFixtureAdapter(runtime, **adapter_options)
    return adapter, ControlledFixtureFacade(adapter)


def select_request(
    slug,
    *,
    actor="nekria",
    operation="select-operation",
):
    return SelectPlayerCharacterRequest(
        ContractVersion.V1,
        reference(IdentityKind.CALLER_OPERATION, operation),
        reference(IdentityKind.COMMAND, f"select-command-{slug}"),
        reference(IdentityKind.EVENT, f"select-event-{slug}"),
        reference(IdentityKind.ACTOR, actor),
        TIME,
    )


def round_request(
    slug,
    *,
    operation="round-operation",
    mode=ClientDiceMode.MANUAL,
    faces=None,
):
    return ResolveControlledRoundRequest(
        ContractVersion.V1,
        reference(IdentityKind.CALLER_OPERATION, operation),
        reference(IdentityKind.COMMAND, f"round-command-{slug}"),
        reference(IdentityKind.EVENT, f"round-event-{slug}"),
        TIME,
        mode,
        {stage: f"{stage}-{slug}" for stage in STAGES},
        (
            {stage: None for stage in STAGES}
            if faces is None
            else faces
        ),
    )


def file_snapshot(root):
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in root.rglob("*")
        if path.is_file() and not path.name.endswith("-shm")
    }


def test_capability_discovery_is_side_effect_free_and_fail_closed(tmp_path):
    fixture_path, journal_path, storage, store, runtime = fixture(tmp_path)
    source = SequenceFaceSource([1, 1, 1, 1])

    class Presentation:
        calls = 0

        def narrate(self, result):
            self.calls += 1
            raise AssertionError("Capability discovery cannot narrate.")

    presentation = Presentation()
    adapter, facade = facade_for(
        runtime,
        automatic_source=source,
        presentation=presentation,
    )
    before_files = file_snapshot(tmp_path)
    before_entries = runtime.event_journal.entries
    before_state = runtime.state_holder.snapshot
    before_handlers = runtime.game_engine.registered_command_types

    descriptors = facade.capabilities()

    assert {
        item.key: item.status for item in descriptors
    } == {
        CapabilityKey.INSPECT_CONTROLLED_FIXTURE: CapabilityStatus.SUPPORTED,
        CapabilityKey.SELECT_PLAYER_CHARACTER: CapabilityStatus.SUPPORTED,
        CapabilityKey.RESOLVE_CONTROLLED_ROUND: CapabilityStatus.UNAVAILABLE,
        CapabilityKey.RECONSTRUCT_OPERATION: CapabilityStatus.SUPPORTED,
        CapabilityKey.VERIFIED_TRANSIENT_NARRATION: CapabilityStatus.SUPPORTED,
        CapabilityKey.CONTROLLED_GOBLIN_ACTION: CapabilityStatus.UNSUPPORTED,
    }
    assert facade.capability(
        CapabilityKey.RESOLVE_CONTROLLED_ROUND
    ).reason is CapabilityReason.PLAYER_SELECTION_REQUIRED
    assert facade.capability(
        CapabilityKey.CONTROLLED_GOBLIN_ACTION
    ).reason is CapabilityReason.CONTROLLED_FIXTURE_HAS_NO_GOBLIN_ACTION
    assert runtime.event_journal.entries == before_entries
    assert runtime.state_holder.snapshot is before_state
    assert runtime.game_engine.registered_command_types == before_handlers
    assert source.calls == []
    assert presentation.calls == 0
    assert file_snapshot(tmp_path) == before_files
    with pytest.raises(ValueError, match="contract version"):
        facade.inspect("phase2-m1-v1")
    with pytest.raises(ValueError, match="capability"):
        facade.capability("unknown.capability")


def test_rejected_and_failed_operations_do_not_conflate_submission_with_mechanics(
    tmp_path,
):
    _, _, _, _, runtime = fixture(tmp_path)
    _, facade = facade_for(runtime)

    rejected = facade.resolve_controlled_round(round_request("before-select"))
    failed = facade.select_player_character(
        select_request("goblin", actor="goblin-1")
    )

    assert rejected.submission is SubmissionState.REJECTED
    assert rejected.mechanics is MechanicalState.NOT_ATTEMPTED
    assert rejected.events == ()
    assert rejected.diagnostic.code is DiagnosticCode.SUBMISSION_REJECTED
    assert failed.submission is SubmissionState.ACCEPTED
    assert failed.mechanics is MechanicalState.FAILED
    assert failed.events == ()
    assert failed.diagnostic.code is DiagnosticCode.MECHANICAL_FAILURE
    assert runtime.event_journal.tail_sequence == 0


def test_manual_journey_uses_stable_operation_correlation_and_exact_order(
    tmp_path,
):
    _, _, _, store, runtime = fixture(tmp_path)
    _, facade = facade_for(runtime)

    selected = facade.select_player_character(select_request("manual"))
    assert selected.operation.value == "select-operation"
    assert selected.command.value == "select-command-manual"
    assert selected.events[0].event.value == "select-event-manual"
    assert selected.submission is SubmissionState.ACCEPTED
    assert selected.mechanics is MechanicalState.SUCCEEDED
    assert selected.durable_commit is DurableCommitState.COMMITTED
    assert selected.local_publication is LocalPublicationState.PUBLISHED
    assert selected.projection is ProjectionState.PROJECTED
    assert selected.synchronization is SynchronizationState.SYNCHRONIZED

    pending_faces = {stage: None for stage in STAGES}
    requests = [
        round_request("manual-1", faces=pending_faces),
        round_request(
            "manual-2",
            faces={**pending_faces, "nekria_initiative": 12},
        ),
        round_request(
            "manual-3",
            faces={
                **pending_faces,
                "nekria_initiative": 12,
                "goblin_initiative": 4,
            },
        ),
        round_request(
            "manual-4",
            faces={
                **pending_faces,
                "nekria_initiative": 12,
                "goblin_initiative": 4,
                "attack": 10,
            },
        ),
    ]
    pending = [facade.resolve_controlled_round(request) for request in requests]

    assert [item.operation.value for item in pending] == [
        "round-operation"
    ] * 4
    assert [item.mechanics for item in pending] == [
        MechanicalState.INPUT_REQUIRED
    ] * 4
    assert [item.mechanical_details["outcome"] for item in pending] == [
        "nekria_initiative_input_required",
        "goblin_initiative_input_required",
        "attack_input_required",
        "damage_input_required",
    ]
    assert all(item.events == () for item in pending)
    assert runtime.event_journal.tail_sequence == store.load().tail_sequence == 1

    completed_request = round_request(
        "manual-final",
        faces={
            "nekria_initiative": 12,
            "goblin_initiative": 4,
            "attack": 10,
            "damage": 2,
        },
    )
    completed = facade.resolve_controlled_round(completed_request)

    assert completed.operation.value == "round-operation"
    assert completed.command.value == "round-command-manual-final"
    assert completed.events[0].event.value == "round-event-manual-final"
    assert completed.events[0].sequence == 2
    assert completed.mechanics is MechanicalState.SUCCEEDED
    assert completed.durable_commit is DurableCommitState.COMMITTED
    assert completed.local_publication is LocalPublicationState.PUBLISHED
    assert completed.projection is ProjectionState.PROJECTED
    assert completed.synchronization is SynchronizationState.SYNCHRONIZED
    assert completed.presentation_status is PresentationState.NOT_REQUESTED
    view = facade.inspect()
    assert view.controlled_round_resolved is True
    assert [item.sequence for item in view.events] == [1, 2]
    assert facade.capability(
        CapabilityKey.RESOLVE_CONTROLLED_ROUND
    ).reason is CapabilityReason.ROUND_ALREADY_RESOLVED


def test_automatic_journey_preserves_durable_order_and_presentation_failure(
    tmp_path,
):
    _, _, _, store, runtime = fixture(tmp_path, store_type=_OrderingStore)
    selection_adapter, selection_facade = facade_for(runtime)
    selection_facade.select_player_character(select_request("automatic"))
    source = SequenceFaceSource([3, 18, 20, 8])
    provider = _FailingNarrationProvider()
    narration = VerifiedNarrationBoundary(runtime, provider)
    adapter, facade = facade_for(
        runtime,
        automatic_source=source,
        presentation=narration,
    )
    observed = []

    def after_append():
        observed.append(
            (
                store.load().tail_sequence,
                runtime.event_journal.tail_sequence,
                runtime.state_holder.snapshot.last_sequence,
            )
        )

    store.after_append = after_append
    result = facade.resolve_controlled_round(
        round_request("automatic", mode=ClientDiceMode.AUTOMATIC)
    )
    store.after_append = None

    assert source.calls == [(1, 20), (1, 20), (1, 20), (1, 8)]
    assert observed == [(2, 1, 1)]
    assert result.submission is SubmissionState.ACCEPTED
    assert result.mechanics is MechanicalState.SUCCEEDED
    assert result.durable_commit is DurableCommitState.COMMITTED
    assert result.local_publication is LocalPublicationState.PUBLISHED
    assert result.projection is ProjectionState.PROJECTED
    assert result.synchronization is SynchronizationState.SYNCHRONIZED
    assert result.presentation_status is PresentationState.FAILED
    assert result.presentation is None
    assert result.diagnostic.code is DiagnosticCode.PRESENTATION_FAILURE
    assert provider.calls == 1
    serialized = result.to_json().lower()
    for secret in ("secret", "sqlite", "bearer", "prompt", "hidden-payload"):
        assert secret not in serialized
    assert runtime.event_journal.tail_sequence == 2
    assert runtime.state_holder.snapshot.last_sequence == 2


def test_successful_transient_presentation_is_event_bound_and_non_authoritative(
    tmp_path,
):
    _, _, _, _, runtime = fixture(tmp_path)
    selection_adapter, selection_facade = facade_for(runtime)
    selection_facade.select_player_character(select_request("narration"))
    provider = _SuccessfulNarrationProvider()
    boundary = VerifiedNarrationBoundary(runtime, provider)
    _, facade = facade_for(
        runtime,
        automatic_source=SequenceFaceSource([12, 4, 10, 2]),
        presentation=boundary,
    )
    entries_before = runtime.event_journal.entries

    result = facade.resolve_controlled_round(
        round_request("narration", mode=ClientDiceMode.AUTOMATIC)
    )

    assert result.presentation_status is PresentationState.SUCCEEDED
    assert result.presentation.text == "Verified transient presentation."
    assert result.presentation.source_event == result.events[0]
    assert len(provider.calls) == 1
    assert provider.calls[0].source_event_id == result.events[0].event.value
    assert provider.calls[0].source_event_sequence == result.events[0].sequence
    assert runtime.event_journal.entries[:1] == entries_before
    assert len(runtime.event_journal.entries) == 2
    assert runtime.state_holder.snapshot.last_sequence == 2
    assert "Verified transient presentation." not in str(
        runtime.state_holder.snapshot.to_dict()
    )


def test_fresh_facade_reconstructs_correlation_from_durable_facts_only(
    tmp_path, monkeypatch
):
    fixture_path, journal_path, _, _, runtime = fixture(tmp_path)
    source = SequenceFaceSource([12, 4, 10, 2])
    _, facade = facade_for(runtime, automatic_source=source)
    facade.select_player_character(select_request("restart"))
    completed = facade.resolve_controlled_round(
        round_request("restart", mode=ClientDiceMode.AUTOMATIC)
    )
    expected_events = completed.events
    expected_view = facade.inspect().to_dict()
    prohibited_calls = []

    def prohibited(name):
        def fail(*args, **kwargs):
            prohibited_calls.append(name)
            raise AssertionError(f"Reconstruction must not invoke {name}.")

        return fail

    monkeypatch.setattr(GameEngine, "dispatch", prohibited("dispatch"))
    monkeypatch.setattr(
        "dungeon_manager.engine.controlled_round.resolve_dice_roll",
        prohibited("dice"),
    )
    monkeypatch.setattr(EventJournalStore, "append", prohibited("append"))
    monkeypatch.setattr(
        AuditedCommandPipeline,
        "recover_world_state",
        prohibited("repair"),
    )
    monkeypatch.setattr(ToolAgent, "ask", prohibited("tool_agent"))
    monkeypatch.setattr(
        tool_call_parser, "parse_tool_call", prohibited("parser")
    )
    monkeypatch.setattr(ToolRegistry, "execute", prohibited("tool"))
    monkeypatch.setattr(ToolExecutor, "execute", prohibited("executor"))

    restarted = load_controlled_campaign_runtime(
        JSONStorage(fixture_path), EventJournalStore(journal_path)
    )
    assert restarted.status.value == "success"
    _, fresh_facade = facade_for(restarted.runtime)
    reconstructed = fresh_facade.reconstruct_operation(
        OperationCorrelationRequest(
            ContractVersion.V1,
            reference(IdentityKind.CALLER_OPERATION, "round-operation"),
            reference(IdentityKind.COMMAND, "round-command-restart"),
        )
    )

    assert reconstructed.operation.value == "round-operation"
    assert reconstructed.command.value == "round-command-restart"
    assert reconstructed.events == expected_events
    assert reconstructed.submission is SubmissionState.ACCEPTED
    assert reconstructed.mechanics is MechanicalState.SUCCEEDED
    assert reconstructed.durable_commit is DurableCommitState.COMMITTED
    assert reconstructed.local_publication is LocalPublicationState.PUBLISHED
    assert reconstructed.projection is ProjectionState.PROJECTED
    assert reconstructed.synchronization is SynchronizationState.SYNCHRONIZED
    assert reconstructed.presentation_status is PresentationState.NOT_REQUESTED
    assert fresh_facade.inspect().to_dict() == expected_view
    assert prohibited_calls == []


def test_missing_reconstruction_correlation_fails_closed_without_dedup_claim(
    tmp_path,
):
    _, _, _, _, runtime = fixture(tmp_path)
    _, facade = facade_for(runtime)

    result = facade.reconstruct_operation(
        OperationCorrelationRequest(
            ContractVersion.V1,
            reference(IdentityKind.CALLER_OPERATION, "caller-retry-1"),
            reference(IdentityKind.COMMAND, "unknown-command"),
        )
    )

    assert result.operation.value == "caller-retry-1"
    assert result.submission is SubmissionState.UNKNOWN
    assert result.mechanics is MechanicalState.UNKNOWN
    assert result.durable_commit is DurableCommitState.UNKNOWN
    assert result.diagnostic.code is DiagnosticCode.CORRELATION_NOT_FOUND
    assert runtime.event_journal.tail_sequence == 0


def test_facade_sanitizes_unexpected_port_failure_without_false_progress(
    tmp_path,
):
    _, _, _, _, runtime = fixture(tmp_path)
    real_adapter = InProcessControlledFixtureAdapter(runtime)

    class FailingPort:
        transient_presentation_available = False

        def inspect(self):
            return real_adapter.inspect()

        def select_player_character(self, request):
            raise RuntimeError(
                "C:\\campaign\\events.sqlite password token traceback prompt"
            )

        def resolve_controlled_round(self, request):
            raise AssertionError("not used")

        def reconstruct_operation(self, request):
            raise AssertionError("not used")

    facade = ControlledFixtureFacade(FailingPort())
    result = facade.select_player_character(select_request("failure"))

    assert result.submission is SubmissionState.UNKNOWN
    assert result.mechanics is MechanicalState.UNKNOWN
    assert result.durable_commit is DurableCommitState.UNKNOWN
    assert result.local_publication is LocalPublicationState.UNKNOWN
    assert result.projection is ProjectionState.UNKNOWN
    assert result.synchronization is SynchronizationState.UNKNOWN
    assert result.presentation_status is PresentationState.UNKNOWN
    assert result.diagnostic.code is DiagnosticCode.INTERNAL_FAILURE
    serialized = result.to_json().lower()
    for secret in (
        "campaign",
        "sqlite",
        "password",
        "token",
        "traceback",
        "prompt",
    ):
        assert secret not in serialized
