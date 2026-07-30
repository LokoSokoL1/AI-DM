from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

import pytest

from dungeon_manager.adapters.in_process_controlled_fixture import (
    InProcessControlledFixtureAdapter,
)
from dungeon_manager.adapters.in_process_permissions import (
    InProcessPermissionContext,
    compose_permissioned_controlled_fixture,
)
from dungeon_manager.campaign_runtime import (
    initialize_controlled_fixture,
    load_controlled_campaign_runtime,
)
from dungeon_manager.ai import tool_call_parser
from dungeon_manager.ai.narration_provider import (
    NarrationProvider,
    NarrationProviderResult,
    NarrationProviderStatus,
)
from dungeon_manager.ai.tool_agent import ToolAgent
from dungeon_manager.ai.tool_executor import ToolExecutor
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
    ClientDiceMode,
    ContractVersion,
    DurableCommitState,
    IdentityKind,
    LocalPublicationState,
    MechanicalState,
    OperationCorrelationRequest,
    ProjectionState,
    ResolveControlledRoundRequest,
    SelectPlayerCharacterRequest,
    SubmissionState,
    SynchronizationState,
)
from .controlled_fixture import ControlledFixtureFacade
from .permission_contracts import (
    ActorAssignment,
    ActorControlDisposition,
    ActorReference,
    BaseRole,
    CampaignReference,
    GrantCapability,
    GrantReference,
    GrantState,
    IdentityState,
    ParticipantReference,
    PermissionCapability,
    PermissionContractVersion,
    PermissionGrant,
    PermissionReason,
    PermissionRequest,
    PerspectiveKind,
    SessionIdentity,
    SessionReference,
    SpeakerMode,
    SpeakerSelection,
    ViewingPerspective,
    VisibilityAudience,
    VisibilityAudienceKind,
    VisibilityEntryKey,
)


TIME = datetime(2026, 7, 30, 14, 0, tzinfo=timezone.utc)
STAGES = ("nekria_initiative", "goblin_initiative", "attack", "damage")
CAMPAIGN = CampaignReference("vertical-slice-v1")
NEKRIA = ActorReference("nekria")
GOBLIN = ActorReference("goblin-1")
PLAYER = ParticipantReference("player-1")
DM = ParticipantReference("dm-1")
PLAYER_SESSION = SessionReference("session-player-1")
DM_SESSION = SessionReference("session-dm-1")


def authority_reference(kind, value):
    return AuthorityReference(kind, value)


def fixture(tmp_path):
    fixture_path = tmp_path / "fixture"
    journal_path = tmp_path / "events.sqlite"
    storage = JSONStorage(fixture_path)
    store = EventJournalStore(journal_path)
    assert initialize_controlled_fixture(storage, store).status.value == "success"
    loaded = load_controlled_campaign_runtime(storage, store)
    assert loaded.status.value == "success"
    return fixture_path, journal_path, storage, store, loaded.runtime


def select_request(slug):
    return SelectPlayerCharacterRequest(
        ContractVersion.V1,
        authority_reference(IdentityKind.CALLER_OPERATION, f"select-op-{slug}"),
        authority_reference(IdentityKind.COMMAND, f"select-command-{slug}"),
        authority_reference(IdentityKind.EVENT, f"select-event-{slug}"),
        authority_reference(IdentityKind.ACTOR, "nekria"),
        TIME,
    )


def round_request(slug, *, mode=ClientDiceMode.MANUAL, faces=None):
    return ResolveControlledRoundRequest(
        ContractVersion.V1,
        authority_reference(IdentityKind.CALLER_OPERATION, f"round-op-{slug}"),
        authority_reference(IdentityKind.COMMAND, f"round-command-{slug}"),
        authority_reference(IdentityKind.EVENT, f"round-event-{slug}"),
        TIME,
        mode,
        {stage: f"{stage}-{slug}" for stage in STAGES},
        (
            {stage: None for stage in STAGES}
            if faces is None
            else faces
        ),
    )


def permission_request(
    capability,
    *,
    session=PLAYER_SESSION,
    actor=NEKRIA,
    speaker=None,
    perspective=None,
):
    return PermissionRequest(
        PermissionContractVersion.V1,
        session,
        CAMPAIGN,
        capability,
        (
            SpeakerSelection(SpeakerMode.ACTOR, actor)
            if speaker is None
            else speaker
        ),
        (
            ViewingPerspective(PerspectiveKind.PARTICIPANT, PLAYER)
            if perspective is None
            else perspective
        ),
        actor,
    )


def audiences(kind=VisibilityAudienceKind.PARTICIPANTS):
    audience = (
        VisibilityAudience(kind)
        if kind is not VisibilityAudienceKind.PARTICIPANTS
        else VisibilityAudience(kind, (PLAYER, DM))
    )
    return {key: audience for key in VisibilityEntryKey}


def context(
    *,
    assignments=(),
    grants=(),
    identities=None,
    audience_map=None,
    now=TIME,
):
    if identities is None:
        identities = {
            PLAYER_SESSION: SessionIdentity(
                PLAYER_SESSION, PLAYER, BaseRole.PLAYER
            ),
            DM_SESSION: SessionIdentity(DM_SESSION, DM, BaseRole.DM),
        }
    return InProcessPermissionContext(
        identities=identities,
        assignments=assignments,
        grants=grants,
        audiences=audiences() if audience_map is None else audience_map,
        now=now,
    )


def permissioned(runtime, permission_context, **adapter_options):
    adapter = InProcessControlledFixtureAdapter(runtime, **adapter_options)
    m1 = ControlledFixtureFacade(adapter)
    return compose_permissioned_controlled_fixture(
        m1,
        permission_context,
        campaign=CAMPAIGN,
        controlled_actor=NEKRIA,
    )


def entry_payload(view):
    assert len(view.entries) == 1
    return view.entries[0].payload


def file_snapshot(root):
    return {
        path.relative_to(root).as_posix(): (
            path.stat().st_size,
            hashlib.sha256(path.read_bytes()).hexdigest(),
        )
        for path in root.rglob("*")
        if path.is_file() and not path.name.endswith("-shm")
    }


class _CountingAuthority:
    transient_presentation_available = False

    def __init__(self, view):
        self.view = view
        self.inspect_calls = 0
        self.select_calls = 0
        self.round_calls = 0
        self.reconstruct_calls = 0

    def inspect(self):
        self.inspect_calls += 1
        return self.view

    def select_player_character(self, request):
        self.select_calls += 1
        raise AssertionError("Denied selection must not delegate.")

    def resolve_controlled_round(self, request):
        self.round_calls += 1
        raise AssertionError("Denied round must not delegate.")

    def reconstruct_operation(self, request):
        self.reconstruct_calls += 1
        raise AssertionError("Denied reconstruction must not delegate.")


class _RecordingNarrationProvider(NarrationProvider):
    def __init__(self):
        self.calls = []

    def narrate(self, packet):
        self.calls.append(packet)
        return NarrationProviderResult(
            NarrationProviderStatus.SUCCESS,
            packet.source_event_id,
            packet.source_event_sequence,
            text="Permissioned verified narration.",
        )


def test_every_denial_precedes_m1_and_preserves_files_and_authority(tmp_path):
    _, _, _, _, runtime = fixture(tmp_path)
    real_adapter = InProcessControlledFixtureAdapter(runtime)
    counting = _CountingAuthority(real_adapter.inspect())
    m1 = ControlledFixtureFacade(counting)
    revoked_context = context(
        assignments=(ActorAssignment(PLAYER, CAMPAIGN, NEKRIA),),
        identities={
            PLAYER_SESSION: SessionIdentity(
                PLAYER_SESSION,
                PLAYER,
                BaseRole.PLAYER,
                IdentityState.REVOKED,
            )
        },
    )
    facade = compose_permissioned_controlled_fixture(
        m1,
        revoked_context,
        campaign=CAMPAIGN,
        controlled_actor=NEKRIA,
    )
    before_files = file_snapshot(tmp_path)
    before_entries = runtime.event_journal.entries
    before_state = runtime.state_holder.snapshot

    denied = facade.resolve_controlled_round(
        permission_request(PermissionCapability.RESOLVE_CONTROLLED_ROUND),
        round_request("denied"),
    )

    assert denied.decision.allowed is False
    assert denied.decision.reason is PermissionReason.IDENTITY_REVOKED
    assert denied.entries == ()
    assert "round-event-denied" not in denied.to_json()
    assert counting.inspect_calls == 0
    assert counting.select_calls == 0
    assert counting.round_calls == 0
    assert counting.reconstruct_calls == 0
    assert runtime.event_journal.entries == before_entries
    assert runtime.state_holder.snapshot is before_state
    assert file_snapshot(tmp_path) == before_files


@pytest.mark.parametrize(
    ("identities", "reason"),
    [
        ({}, PermissionReason.IDENTITY_UNRESOLVED),
        (
            {
                PLAYER_SESSION: SessionIdentity(
                    PLAYER_SESSION,
                    PLAYER,
                    BaseRole.PLAYER,
                    expires_at=TIME,
                )
            },
            PermissionReason.IDENTITY_EXPIRED,
        ),
    ],
)
def test_unknown_and_expired_session_denials_are_sanitized(
    tmp_path, identities, reason
):
    _, _, _, _, runtime = fixture(tmp_path)
    facade = permissioned(runtime, context(identities=identities))

    result = facade.inspect(
        permission_request(
            PermissionCapability.INSPECT,
            actor=None,
            speaker=SpeakerSelection(SpeakerMode.OOC),
        )
    )

    assert result.decision.reason is reason
    assert result.entries == ()
    assert "participant" not in result.to_json()


def test_permission_filtered_capabilities_do_not_turn_speech_into_action(tmp_path):
    _, _, _, _, runtime = fixture(tmp_path)
    speak_only = PermissionGrant(
        GrantReference("speak-goblin"),
        PLAYER,
        CAMPAIGN,
        GOBLIN,
        GrantCapability.SPEAK_AS,
    )
    facade = permissioned(runtime, context(grants=(speak_only,)))
    discovery = permission_request(
        PermissionCapability.DISCOVER_CAPABILITIES,
        actor=GOBLIN,
        speaker=SpeakerSelection(SpeakerMode.ACTOR, GOBLIN),
    )

    result = facade.capabilities(discovery)
    keys = {
        item["key"]
        for item in entry_payload(result)["capabilities"]
    }

    assert CapabilityKey.INSPECT_CONTROLLED_FIXTURE.value in keys
    assert CapabilityKey.SELECT_PLAYER_CHARACTER.value not in keys
    assert CapabilityKey.RESOLVE_CONTROLLED_ROUND.value not in keys
    assert CapabilityKey.RECONSTRUCT_OPERATION.value not in keys
    assert CapabilityKey.VERIFIED_TRANSIENT_NARRATION.value not in keys
    assert CapabilityKey.CONTROLLED_GOBLIN_ACTION.value in keys


def test_act_as_without_speak_as_exposes_control_only_for_the_granted_actor(
    tmp_path,
):
    _, _, _, _, runtime = fixture(tmp_path)
    act_nekria = PermissionGrant(
        GrantReference("act-nekria"),
        PLAYER,
        CAMPAIGN,
        NEKRIA,
        GrantCapability.ACT_AS,
    )
    facade = permissioned(runtime, context(grants=(act_nekria,)))
    discovery = permission_request(
        PermissionCapability.DISCOVER_CAPABILITIES
    )

    result = facade.capabilities(discovery)
    keys = {
        item["key"]
        for item in entry_payload(result)["capabilities"]
    }

    assert CapabilityKey.SELECT_PLAYER_CHARACTER.value in keys
    assert CapabilityKey.RESOLVE_CONTROLLED_ROUND.value in keys
    assert CapabilityKey.RECONSTRUCT_OPERATION.value in keys


def test_dm_speaker_mode_allows_dm_inspection_but_not_arbitrary_actor_control(
    tmp_path,
):
    _, _, _, _, runtime = fixture(tmp_path)
    facade = permissioned(runtime, context())
    dm_inspect = permission_request(
        PermissionCapability.INSPECT,
        session=DM_SESSION,
        actor=None,
        speaker=SpeakerSelection(SpeakerMode.DM),
        perspective=ViewingPerspective(PerspectiveKind.DM),
    )
    dm_round = permission_request(
        PermissionCapability.RESOLVE_CONTROLLED_ROUND,
        session=DM_SESSION,
        speaker=SpeakerSelection(SpeakerMode.DM),
        perspective=ViewingPerspective(PerspectiveKind.DM),
    )

    inspected = facade.inspect(dm_inspect)
    denied = facade.resolve_controlled_round(
        dm_round, round_request("dm-denied")
    )

    assert inspected.decision.allowed is True
    assert inspected.decision.actor_control is ActorControlDisposition.AI_DEFAULT
    assert denied.decision.reason is PermissionReason.SPEAKER_NOT_ALLOWED
    assert runtime.event_journal.tail_sequence == 0


def test_speaker_change_never_widens_explicit_visibility(tmp_path):
    _, _, _, _, runtime = fixture(tmp_path)
    hidden = audiences(VisibilityAudienceKind.DM_ONLY)
    facade = permissioned(
        runtime,
        context(
            assignments=(ActorAssignment(PLAYER, CAMPAIGN, NEKRIA),),
            audience_map=hidden,
        ),
    )
    actor_view = facade.inspect(
        permission_request(PermissionCapability.INSPECT)
    )
    ooc_view = facade.inspect(
        permission_request(
            PermissionCapability.INSPECT,
            actor=None,
            speaker=SpeakerSelection(SpeakerMode.OOC),
        )
    )

    assert actor_view.decision.allowed is True
    assert ooc_view.decision.allowed is True
    assert actor_view.entries == ()
    assert ooc_view.entries == ()


def test_assigned_player_manual_journey_preserves_m1_authoritative_order(
    tmp_path,
):
    _, _, _, store, runtime = fixture(tmp_path)
    facade = permissioned(
        runtime,
        context(assignments=(ActorAssignment(PLAYER, CAMPAIGN, NEKRIA),)),
    )
    selected = facade.select_player_character(
        permission_request(PermissionCapability.SELECT_PLAYER_CHARACTER),
        select_request("manual"),
    )
    pending_faces = {stage: None for stage in STAGES}
    pending = facade.resolve_controlled_round(
        permission_request(PermissionCapability.RESOLVE_CONTROLLED_ROUND),
        round_request("manual-pending", faces=pending_faces),
    )
    completed = facade.resolve_controlled_round(
        permission_request(PermissionCapability.RESOLVE_CONTROLLED_ROUND),
        round_request(
            "manual-complete",
            faces={
                "nekria_initiative": 12,
                "goblin_initiative": 4,
                "attack": 10,
                "damage": 2,
            },
        ),
    )

    selected_payload = entry_payload(selected)
    pending_payload = entry_payload(pending)
    completed_payload = entry_payload(completed)
    assert selected.decision.actor_control is ActorControlDisposition.DIRECT_CONTROL
    assert selected_payload["mechanics"] == MechanicalState.SUCCEEDED.value
    assert pending_payload["mechanics"] == MechanicalState.INPUT_REQUIRED.value
    assert pending_payload["events"] == ()
    assert completed_payload["mechanics"] == MechanicalState.SUCCEEDED.value
    assert completed_payload["durable_commit"] == DurableCommitState.COMMITTED.value
    assert completed_payload["local_publication"] == LocalPublicationState.PUBLISHED.value
    assert completed_payload["projection"] == ProjectionState.PROJECTED.value
    assert completed_payload["synchronization"] == SynchronizationState.SYNCHRONIZED.value
    assert completed_payload["events"][0]["event"]["value"] == (
        "round-event-manual-complete"
    )
    assert runtime.event_journal.tail_sequence == store.load().tail_sequence == 2
    assert runtime.state_holder.snapshot.last_sequence == 2


def test_assigned_player_automatic_journey_delegates_once_to_unchanged_m1(
    tmp_path,
):
    _, _, _, store, runtime = fixture(tmp_path)
    source = SequenceFaceSource([3, 18, 20, 8])
    facade = permissioned(
        runtime,
        context(assignments=(ActorAssignment(PLAYER, CAMPAIGN, NEKRIA),)),
        automatic_source=source,
    )
    facade.select_player_character(
        permission_request(PermissionCapability.SELECT_PLAYER_CHARACTER),
        select_request("automatic"),
    )
    result = facade.resolve_controlled_round(
        permission_request(PermissionCapability.RESOLVE_CONTROLLED_ROUND),
        round_request("automatic", mode=ClientDiceMode.AUTOMATIC),
    )
    payload = entry_payload(result)

    assert source.calls == [(1, 20), (1, 20), (1, 20), (1, 8)]
    assert result.decision.actor_control is ActorControlDisposition.DIRECT_CONTROL
    assert payload["submission"] == SubmissionState.ACCEPTED.value
    assert payload["mechanics"] == MechanicalState.SUCCEEDED.value
    assert payload["events"][0]["sequence"] == 2
    assert runtime.event_journal.tail_sequence == store.load().tail_sequence == 2
    assert runtime.state_holder.snapshot.last_sequence == 2


def test_authorized_round_preserves_m1_verified_narration_eligibility(tmp_path):
    _, _, _, _, runtime = fixture(tmp_path)
    assigned_context = context(
        assignments=(ActorAssignment(PLAYER, CAMPAIGN, NEKRIA),)
    )
    selection_facade = permissioned(runtime, assigned_context)
    selection_facade.select_player_character(
        permission_request(PermissionCapability.SELECT_PLAYER_CHARACTER),
        select_request("narration"),
    )
    provider = _RecordingNarrationProvider()
    narration = VerifiedNarrationBoundary(runtime, provider)
    facade = permissioned(
        runtime,
        assigned_context,
        automatic_source=SequenceFaceSource([12, 4, 10, 2]),
        presentation=narration,
    )

    result = facade.resolve_controlled_round(
        permission_request(PermissionCapability.RESOLVE_CONTROLLED_ROUND),
        round_request("narration", mode=ClientDiceMode.AUTOMATIC),
    )
    payload = entry_payload(result)

    assert len(provider.calls) == 1
    assert payload["presentation_status"] == "succeeded"
    assert payload["presentation"]["text"] == (
        "Permissioned verified narration."
    )
    assert payload["presentation"]["source_event"] == payload["events"][0]
    assert runtime.event_journal.tail_sequence == 2
    assert runtime.state_holder.snapshot.last_sequence == 2


def test_permissioned_reconstruction_hides_event_identity_until_authorized(
    tmp_path, monkeypatch
):
    fixture_path, journal_path, _, _, runtime = fixture(tmp_path)
    source = SequenceFaceSource([12, 4, 10, 2])
    assigned_context = context(
        assignments=(ActorAssignment(PLAYER, CAMPAIGN, NEKRIA),)
    )
    facade = permissioned(
        runtime, assigned_context, automatic_source=source
    )
    facade.select_player_character(
        permission_request(PermissionCapability.SELECT_PLAYER_CHARACTER),
        select_request("restart"),
    )
    facade.resolve_controlled_round(
        permission_request(PermissionCapability.RESOLVE_CONTROLLED_ROUND),
        round_request("restart", mode=ClientDiceMode.AUTOMATIC),
    )
    restarted = load_controlled_campaign_runtime(
        JSONStorage(fixture_path), EventJournalStore(journal_path)
    )
    assert restarted.status.value == "success"
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
    fresh = permissioned(restarted.runtime, assigned_context)
    operation = OperationCorrelationRequest(
        ContractVersion.V1,
        authority_reference(IdentityKind.CALLER_OPERATION, "retry"),
        authority_reference(IdentityKind.COMMAND, "round-command-restart"),
    )
    denied_context = context()
    denied_facade = permissioned(restarted.runtime, denied_context)

    denied = denied_facade.reconstruct_operation(
        permission_request(PermissionCapability.RECONSTRUCT_OPERATION),
        operation,
    )
    allowed = fresh.reconstruct_operation(
        permission_request(PermissionCapability.RECONSTRUCT_OPERATION),
        operation,
    )

    assert denied.decision.allowed is False
    assert denied.entries == ()
    assert "round-event-restart" not in denied.to_json()
    payload = entry_payload(allowed)
    assert payload["events"][0]["event"]["value"] == "round-event-restart"
    assert payload["events"][0]["sequence"] == 2
    assert payload["mechanics"] == MechanicalState.SUCCEEDED.value
    assert prohibited_calls == []


def test_process_local_context_is_defensive_and_defaults_to_no_disclosure():
    identities = {
        PLAYER_SESSION: SessionIdentity(
            PLAYER_SESSION, PLAYER, BaseRole.PLAYER
        )
    }
    assignments = [ActorAssignment(PLAYER, CAMPAIGN, NEKRIA)]
    grants = [
        PermissionGrant(
            GrantReference("grant"),
            PLAYER,
            CAMPAIGN,
            GOBLIN,
            GrantCapability.ACT_AS,
            GrantState.ACTIVE,
            TIME + timedelta(hours=1),
        )
    ]
    permission_context = InProcessPermissionContext(
        identities=identities,
        assignments=assignments,
        grants=grants,
        audiences={},
        now=TIME,
    )
    identities.clear()
    assignments.clear()
    grants.clear()

    assert permission_context.resolve_identity(PLAYER_SESSION).participant == PLAYER
    assert permission_context.assignments_for(PLAYER, CAMPAIGN) == (
        ActorAssignment(PLAYER, CAMPAIGN, NEKRIA),
    )
    assert len(permission_context.grants_for(PLAYER, CAMPAIGN)) == 1
    assert permission_context.audience_for(
        VisibilityEntryKey.FIXTURE_INSPECTION
    ).kind is VisibilityAudienceKind.NO_CLIENT_DISCLOSURE
