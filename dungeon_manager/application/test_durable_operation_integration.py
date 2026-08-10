from __future__ import annotations

from dataclasses import replace

from dungeon_manager.adapters.durable_controlled_fixture import (
    compose_durable_permissioned_controlled_fixture,
)
from dungeon_manager.adapters.in_process_controlled_fixture import (
    InProcessControlledFixtureAdapter,
)
from dungeon_manager.ai.narration_provider import (
    NarrationProvider,
    NarrationProviderResult,
    NarrationProviderStatus,
)
from dungeon_manager.campaign_runtime import load_controlled_campaign_runtime
from dungeon_manager.engine.dice import SequenceFaceSource
from dungeon_manager.engine.event_journal_store import EventJournalStore
from dungeon_manager.storage.json_storage import JSONStorage
from dungeon_manager.verified_narration import VerifiedNarrationBoundary

from .contracts import AuthorityReference, ClientDiceMode, IdentityKind
from .controlled_fixture import ControlledFixtureFacade
from .durable_operation_contracts import DurableReplayDisposition
from .permission_contracts import (
    ActorAssignment,
    PermissionCapability,
    SessionReference,
)
from .test_permissioned_controlled_fixture import (
    CAMPAIGN,
    NEKRIA,
    PLAYER,
    context,
    entry_payload,
    fixture,
    permission_request,
    round_request,
    select_request,
)


class RecordingNarrationProvider(NarrationProvider):
    def __init__(self):
        self.calls = []

    def narrate(self, packet):
        self.calls.append(packet)
        return NarrationProviderResult(
            NarrationProviderStatus.SUCCESS,
            packet.source_event_id,
            packet.source_event_sequence,
            text="Transient M3 narration.",
        )


def composed(runtime, operation_path, *, source, provider):
    adapter = InProcessControlledFixtureAdapter(
        runtime,
        automatic_source=source,
        presentation=VerifiedNarrationBoundary(runtime, provider),
    )
    return compose_durable_permissioned_controlled_fixture(
        ControlledFixtureFacade(adapter),
        context(assignments=(ActorAssignment(PLAYER, CAMPAIGN, NEKRIA),)),
        operation_path,
        campaign=CAMPAIGN,
        controlled_actor=NEKRIA,
    )


def disposition(view):
    return entry_payload(view)["disposition"]


def test_authorization_precedes_ledger_access_and_outcome_disclosure(tmp_path):
    _, _, _, _, runtime = fixture(tmp_path)
    operation_path = tmp_path / "operations.sqlite"
    facade = composed(
        runtime,
        operation_path,
        source=SequenceFaceSource(()),
        provider=RecordingNarrationProvider(),
    )
    denied = facade.select_player_character(
        permission_request(
            PermissionCapability.SELECT_PLAYER_CHARACTER,
            session=SessionReference("unknown-session"),
        ),
        select_request("denied"),
    )

    assert not denied.decision.allowed
    assert denied.entries == ()
    assert not operation_path.exists()


def test_real_m1_m2_effects_happen_once_and_terminal_retries_survive_restart(
    tmp_path,
):
    fixture_path, journal_path, _, store, runtime = fixture(tmp_path)
    operation_path = tmp_path / "operations.sqlite"
    source = SequenceFaceSource((18, 4, 17, 6))
    provider = RecordingNarrationProvider()
    facade = composed(runtime, operation_path, source=source, provider=provider)

    selection_permission = permission_request(
        PermissionCapability.SELECT_PLAYER_CHARACTER
    )
    round_permission = permission_request(
        PermissionCapability.RESOLVE_CONTROLLED_ROUND
    )
    selection = select_request("m3")
    round_operation = round_request("m3", mode=ClientDiceMode.AUTOMATIC)

    first_selection = facade.select_player_character(
        selection_permission, selection
    )
    retry_selection = facade.select_player_character(
        selection_permission, selection
    )
    first_round = facade.resolve_controlled_round(
        round_permission, round_operation
    )
    tail_after_first_round = runtime.event_journal.tail_sequence
    state_after_first_round = runtime.state_holder.snapshot
    dice_calls_after_first_round = tuple(source.calls)
    retry_round = facade.resolve_controlled_round(
        round_permission, round_operation
    )

    assert disposition(first_selection) == DurableReplayDisposition.DELEGATED.value
    assert disposition(retry_selection) == DurableReplayDisposition.REPLAYED.value
    assert disposition(first_round) == DurableReplayDisposition.DELEGATED.value
    assert disposition(retry_round) == DurableReplayDisposition.REPLAYED.value
    assert runtime.event_journal.tail_sequence == tail_after_first_round == 2
    assert runtime.state_holder.snapshot == state_after_first_round
    assert tuple(source.calls) == dice_calls_after_first_round
    assert len(provider.calls) == 1
    assert entry_payload(first_round)["transient_presentation"]["value"]["text"] == (
        "Transient M3 narration."
    )
    assert entry_payload(retry_round)["transient_presentation"] is None
    assert "presentation" not in entry_payload(first_round)["terminal_outcome"]

    fresh_store = EventJournalStore(journal_path)
    loaded = load_controlled_campaign_runtime(
        JSONStorage(fixture_path), fresh_store
    )
    assert loaded.status.value == "success"
    fresh_source = SequenceFaceSource(())
    fresh_provider = RecordingNarrationProvider()
    restarted = composed(
        loaded.runtime,
        operation_path,
        source=fresh_source,
        provider=fresh_provider,
    )
    restarted_selection = restarted.select_player_character(
        selection_permission, selection
    )
    restarted_round = restarted.resolve_controlled_round(
        round_permission, round_operation
    )

    assert disposition(restarted_selection) == DurableReplayDisposition.REPLAYED.value
    assert disposition(restarted_round) == DurableReplayDisposition.REPLAYED.value
    assert fresh_source.calls == []
    assert fresh_provider.calls == []
    assert loaded.runtime.event_journal.tail_sequence == 2

    collision = replace(
        round_operation,
        command=AuthorityReference(IdentityKind.COMMAND, "changed-command"),
    )
    collision_result = restarted.resolve_controlled_round(
        round_permission, collision
    )
    assert disposition(collision_result) == DurableReplayDisposition.COLLISION.value
    assert fresh_source.calls == []
    assert fresh_provider.calls == []
