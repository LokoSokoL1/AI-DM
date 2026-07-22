"""Controlled First Playable Vertical Slice fixture and campaign runtime.

This deliberately narrow module owns only the V1 controlled fixture definition,
its explicit initialization, durable startup composition, and player-character
selection.  It does not implement a general campaign/content system or rules.
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from dungeon_manager.models.campaign import Campaign
from dungeon_manager.models.character import Character
from dungeon_manager.storage.json_storage import JSONStorage

from .engine._json import thaw_json_value, validate_trimmed_identifier
from .engine.audited_pipeline import AuditedCommandPipeline, AuditedCommandPipelineResult
from .engine.automation import AutomationMode, AutomationPolicy, CapabilityAutomationRule
from .engine.command import CommandProvenance, CommandSource, GameCommand
from .engine.controlled_round import (
    CONTROLLED_ROUND_EVENT,
    CONTROLLED_ROUND_SCHEMA_VERSION,
    reduce_controlled_round,
)
from .engine.event_journal_store import EventJournalStore
from .engine.game_engine import GameEngine
from .engine.game_event import GameEvent
from .engine.journals import CommandAuditJournal
from .engine.policy_gated_dispatcher import PolicyGatedCommandDispatcher
from .engine.result import GameResult
from .engine.startup_hydration import StartupHydrationStatus, hydrate_durable_runtime
from .engine.world_state import WorldState, WorldStateProjector


logger = logging.getLogger("DungeonManager")

FIXTURE_SCHEMA_VERSION = 1
FIXTURE_MANIFEST_CATEGORY = "vertical_slice_fixtures"
FIXTURE_MANIFEST_NAME = "vertical-slice-v1"
CAMPAIGN_ID = "vertical-slice-v1"
JOURNAL_ID = "vertical-slice-v1-events"
SCENE_ID = "controlled-goblin-encounter"
NEKRIA_ID = "nekria"
GOBLIN_ID = "goblin-1"
SELECT_PLAYER_CHARACTER_COMMAND = "campaign.select_player_character"
PLAYER_CHARACTER_SELECTED_EVENT = "campaign.player_character_selected"

_SAFE_INVALID_INPUT = "Campaign runtime input is invalid."
_SAFE_NOT_FOUND = "The controlled campaign fixture is not available."
_SAFE_INVALID_DEFINITION = "The controlled campaign fixture is invalid."
_SAFE_CAMPAIGN_MISMATCH = "The campaign identity does not match the expected campaign."
_SAFE_JOURNAL_MISMATCH = "The journal identity does not match the expected journal."
_SAFE_HYDRATION_FAILURE = "Campaign runtime hydration failed safely."
_SAFE_INITIALIZATION_FAILURE = "Campaign runtime initialization failed safely."


class ParticipantKind(str, Enum):
    PLAYER_CHARACTER = "player_character"
    NPC = "npc"


class CampaignRuntimeLoadStatus(str, Enum):
    SUCCESS = "success"
    INVALID_INPUT = "invalid_input"
    NOT_FOUND = "not_found"
    INVALID_DEFINITION = "invalid_definition"
    CAMPAIGN_ID_MISMATCH = "campaign_id_mismatch"
    JOURNAL_ID_MISMATCH = "journal_id_mismatch"
    HYDRATION_FAILURE = "hydration_failure"
    INITIALIZATION_FAILURE = "initialization_failure"


class FixtureSetupStatus(str, Enum):
    SUCCESS = "success"
    INVALID_INPUT = "invalid_input"
    ALREADY_EXISTS = "already_exists"
    INITIALIZATION_FAILURE = "initialization_failure"


@dataclass(frozen=True)
class CampaignParticipantDefinition:
    participant_id: str
    kind: ParticipantKind
    character_record_id: str
    selectable_by_player: bool = False

    def __post_init__(self) -> None:
        validate_trimmed_identifier(self.participant_id, "Participant ID")
        validate_trimmed_identifier(self.character_record_id, "Character record ID")
        if not isinstance(self.kind, ParticipantKind):
            raise ValueError("Participant kind must be typed.")
        if not isinstance(self.selectable_by_player, bool):
            raise ValueError("Participant selection flag must be boolean.")
        if self.kind is ParticipantKind.NPC and self.selectable_by_player:
            raise ValueError("NPC participants cannot be player-selectable.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "character_record_id": self.character_record_id,
            "kind": self.kind.value,
            "participant_id": self.participant_id,
            "selectable_by_player": self.selectable_by_player,
        }


@dataclass(frozen=True)
class ControlledSceneDefinition:
    scene_id: str
    participant_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        validate_trimmed_identifier(self.scene_id, "Scene ID")
        if not self.participant_ids:
            raise ValueError("Controlled scene must have participants.")
        if len(set(self.participant_ids)) != len(self.participant_ids):
            raise ValueError("Controlled scene participant IDs must be unique.")
        for participant_id in self.participant_ids:
            validate_trimmed_identifier(participant_id, "Scene participant ID")

    def to_dict(self) -> dict[str, Any]:
        return {"participant_ids": list(self.participant_ids), "scene_id": self.scene_id}


@dataclass(frozen=True)
class ControlledCampaignDefinition:
    schema_version: int
    campaign_id: str
    campaign_record_id: str
    journal_id: str
    current_scene_id: str
    scenes: tuple[ControlledSceneDefinition, ...]
    participants: tuple[CampaignParticipantDefinition, ...]
    selectable_player_character_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        if (
            not isinstance(self.schema_version, int)
            or isinstance(self.schema_version, bool)
            or self.schema_version != FIXTURE_SCHEMA_VERSION
        ):
            raise ValueError("Controlled fixture schema version is unsupported.")
        for value, label in ((self.campaign_id, "Campaign ID"), (self.campaign_record_id, "Campaign record ID"), (self.journal_id, "Journal ID"), (self.current_scene_id, "Current scene ID")):
            validate_trimmed_identifier(value, label)
        if (
            not isinstance(self.scenes, tuple)
            or not isinstance(self.participants, tuple)
            or not isinstance(self.selectable_player_character_ids, tuple)
            or not self.scenes
            or not self.participants
            or not self.selectable_player_character_ids
        ):
            raise ValueError("Controlled fixture definition is incomplete.")
        if any(not isinstance(scene, ControlledSceneDefinition) for scene in self.scenes):
            raise ValueError("Controlled fixture scenes must be typed.")
        if any(not isinstance(item, CampaignParticipantDefinition) for item in self.participants):
            raise ValueError("Controlled fixture participants must be typed.")
        scene_ids = [scene.scene_id for scene in self.scenes]
        participant_ids = [item.participant_id for item in self.participants]
        if len(set(scene_ids)) != len(scene_ids) or len(set(participant_ids)) != len(participant_ids):
            raise ValueError("Controlled fixture IDs must be unique.")
        if self.current_scene_id not in scene_ids:
            raise ValueError("Current scene is missing from the fixture.")
        participants = {item.participant_id: item for item in self.participants}
        current_scene = next(scene for scene in self.scenes if scene.scene_id == self.current_scene_id)
        if any(item not in participants for item in current_scene.participant_ids):
            raise ValueError("Scene references a missing participant.")
        if len(set(self.selectable_player_character_ids)) != len(self.selectable_player_character_ids):
            raise ValueError("Selectable character IDs must be unique.")
        for participant_id in self.selectable_player_character_ids:
            validate_trimmed_identifier(participant_id, "Selectable character ID")
            participant = participants.get(participant_id)
            if participant is None or participant_id not in current_scene.participant_ids:
                raise ValueError("Selectable character is absent from the current scene.")
            if participant.kind is not ParticipantKind.PLAYER_CHARACTER or not participant.selectable_by_player:
                raise ValueError("Selectable participant must be a player character.")

    @property
    def current_scene(self) -> ControlledSceneDefinition:
        return next(scene for scene in self.scenes if scene.scene_id == self.current_scene_id)

    def participant(self, participant_id: str) -> CampaignParticipantDefinition:
        for participant in self.participants:
            if participant.participant_id == participant_id:
                return participant
        raise KeyError(participant_id)

    def to_dict(self) -> dict[str, Any]:
        return {
            "campaign_id": self.campaign_id,
            "campaign_record_id": self.campaign_record_id,
            "current_scene_id": self.current_scene_id,
            "journal_id": self.journal_id,
            "participants": [item.to_dict() for item in self.participants],
            "scenes": [scene.to_dict() for scene in self.scenes],
            "schema_version": self.schema_version,
            "selectable_player_character_ids": list(self.selectable_player_character_ids),
        }

    @classmethod
    def from_dict(cls, value: Any) -> "ControlledCampaignDefinition":
        if not isinstance(value, Mapping) or set(value) != {
            "campaign_id", "campaign_record_id", "current_scene_id", "journal_id",
            "participants", "scenes", "schema_version", "selectable_player_character_ids",
        }:
            raise ValueError("Controlled fixture manifest fields are invalid.")
        if not isinstance(value["participants"], Sequence) or isinstance(value["participants"], (str, bytes)):
            raise ValueError("Controlled fixture participants are invalid.")
        if not isinstance(value["scenes"], Sequence) or isinstance(value["scenes"], (str, bytes)):
            raise ValueError("Controlled fixture scenes are invalid.")
        if not isinstance(value["selectable_player_character_ids"], Sequence) or isinstance(value["selectable_player_character_ids"], (str, bytes)):
            raise ValueError("Controlled fixture selectable characters are invalid.")
        participants = []
        for raw in value["participants"]:
            if not isinstance(raw, Mapping) or set(raw) != {"participant_id", "kind", "character_record_id", "selectable_by_player"}:
                raise ValueError("Controlled fixture participant is invalid.")
            participants.append(CampaignParticipantDefinition(raw["participant_id"], ParticipantKind(raw["kind"]), raw["character_record_id"], raw["selectable_by_player"]))
        scenes = []
        for raw in value["scenes"]:
            if not isinstance(raw, Mapping) or set(raw) != {"scene_id", "participant_ids"}:
                raise ValueError("Controlled fixture scene is invalid.")
            if not isinstance(raw["participant_ids"], Sequence) or isinstance(raw["participant_ids"], (str, bytes)):
                raise ValueError("Controlled fixture scene is invalid.")
            scenes.append(ControlledSceneDefinition(raw["scene_id"], tuple(raw["participant_ids"])))
        return cls(value["schema_version"], value["campaign_id"], value["campaign_record_id"], value["journal_id"], value["current_scene_id"], tuple(scenes), tuple(participants), tuple(value["selectable_player_character_ids"]))


def controlled_fixture_definition() -> ControlledCampaignDefinition:
    return ControlledCampaignDefinition(
        schema_version=FIXTURE_SCHEMA_VERSION,
        campaign_id=CAMPAIGN_ID,
        campaign_record_id=CAMPAIGN_ID,
        journal_id=JOURNAL_ID,
        current_scene_id=SCENE_ID,
        scenes=(ControlledSceneDefinition(SCENE_ID, (NEKRIA_ID, GOBLIN_ID)),),
        participants=(
            CampaignParticipantDefinition(NEKRIA_ID, ParticipantKind.PLAYER_CHARACTER, NEKRIA_ID, True),
            CampaignParticipantDefinition(GOBLIN_ID, ParticipantKind.NPC, GOBLIN_ID, False),
        ),
        selectable_player_character_ids=(NEKRIA_ID,),
    )


@dataclass(frozen=True)
class FixtureSetupResult:
    status: FixtureSetupStatus
    campaign_id: Optional[str] = None
    journal_id: Optional[str] = None
    reason_code: Optional[str] = None
    definition: Optional[ControlledCampaignDefinition] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, FixtureSetupStatus):
            raise ValueError("Fixture setup status must be typed.")
        if self.status is FixtureSetupStatus.SUCCESS:
            if not isinstance(self.definition, ControlledCampaignDefinition) or self.campaign_id != self.definition.campaign_id or self.journal_id != self.definition.journal_id or self.reason_code is not None:
                raise ValueError("Successful fixture setup requires its definition.")
        elif self.definition is not None:
            raise ValueError("Failed fixture setup cannot expose a definition.")

    def to_dict(self) -> dict[str, Any]:
        return {"campaign_id": self.campaign_id, "journal_id": self.journal_id, "reason_code": self.reason_code, "status": self.status.value}


def initialize_controlled_fixture(storage: JSONStorage, journal_store: EventJournalStore) -> FixtureSetupResult:
    """Create only the known fixture at caller-supplied JSON and SQLite targets."""
    if not isinstance(storage, JSONStorage) or not isinstance(journal_store, EventJournalStore):
        return FixtureSetupResult(FixtureSetupStatus.INVALID_INPUT, reason_code="invalid_dependencies")
    definition = controlled_fixture_definition()
    try:
        expected_json = (
            storage.load(FIXTURE_MANIFEST_CATEGORY, FIXTURE_MANIFEST_NAME),
            storage.load("campaigns", definition.campaign_record_id),
            *(storage.load("characters", item.character_record_id) for item in definition.participants),
        )
        sidecars = tuple(journal_store.path.with_name(journal_store.path.name + suffix) for suffix in ("", "-wal", "-shm"))
        if any(value is not None for value in expected_json) or any(path.exists() for path in sidecars):
            return FixtureSetupResult(FixtureSetupStatus.ALREADY_EXISTS, definition.campaign_id, definition.journal_id, "target_exists")
        initialized = journal_store.initialize(journal_id=definition.journal_id)
        if initialized.status.value != "success":
            return FixtureSetupResult(FixtureSetupStatus.INITIALIZATION_FAILURE, definition.campaign_id, definition.journal_id, "journal_initialize_failed")
        storage.save(FIXTURE_MANIFEST_CATEGORY, FIXTURE_MANIFEST_NAME, definition.to_dict())
        storage.save("campaigns", definition.campaign_record_id, {"name": "First Playable Vertical Slice", "description": "Controlled campaign fixture.", "characters": ["Nekria", "Goblin"], "locations": [], "notes": []})
        storage.save("characters", NEKRIA_ID, {"name": "Nekria", "race": "Human", "character_class": "Rogue", "level": 1, "description": "Controlled player character.", "inventory": ["Rapier"], "notes": []})
        storage.save("characters", GOBLIN_ID, {"name": "Goblin", "race": "Goblin", "character_class": "", "level": 1, "description": "Controlled hostile participant.", "inventory": [], "notes": []})
    except Exception:
        logger.exception("Controlled fixture initialization failed safely")
        return FixtureSetupResult(FixtureSetupStatus.INITIALIZATION_FAILURE, definition.campaign_id, definition.journal_id, "fixture_write_failed")
    return FixtureSetupResult(FixtureSetupStatus.SUCCESS, definition.campaign_id, definition.journal_id, definition=definition)


@dataclass(frozen=True)
class LoadedFixtureCharacter:
    participant_id: str
    character: Character


@dataclass(frozen=True)
class CampaignRuntime:
    definition: ControlledCampaignDefinition
    campaign: Campaign
    characters: tuple[LoadedFixtureCharacter, ...]
    pipeline: AuditedCommandPipeline
    state_holder: Any
    event_journal: Any
    game_engine: GameEngine

    @property
    def current_scene_id(self) -> str:
        return self.definition.current_scene_id

    @property
    def participant_ids(self) -> tuple[str, ...]:
        return self.definition.current_scene.participant_ids

    @property
    def selected_player_character_id(self) -> Optional[str]:
        return self.state_holder.snapshot.data["selected_player_character_id"]

    def select_player_character(self, player_character_id: str, *, command_id: str, event_id: str, occurred_at: datetime, initiator_id: str = "player") -> AuditedCommandPipelineResult:
        command = GameCommand(
            command_type=SELECT_PLAYER_CHARACTER_COMMAND,
            command_id=command_id,
            provenance=CommandProvenance(CommandSource.HUMAN, initiator_id),
            actor_id=player_character_id,
            payload={"campaign_id": self.definition.campaign_id, "player_character_id": player_character_id, "event_id": event_id, "occurred_at": occurred_at.isoformat()},
        )
        return self.pipeline.dispatch(command)


@dataclass(frozen=True)
class CampaignRuntimeLoadResult:
    status: CampaignRuntimeLoadStatus
    campaign_id: Optional[str] = None
    journal_id: Optional[str] = None
    journal_tail: Optional[int] = None
    reason_code: Optional[str] = None
    runtime: Optional[CampaignRuntime] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, CampaignRuntimeLoadStatus):
            raise ValueError("Campaign runtime load status must be typed.")
        if self.status is CampaignRuntimeLoadStatus.SUCCESS:
            if not isinstance(self.runtime, CampaignRuntime):
                raise ValueError("Successful runtime loading requires a runtime.")
        elif self.runtime is not None:
            raise ValueError("Failed runtime loading cannot expose partial runtime.")

    def to_dict(self) -> dict[str, Any]:
        return {"campaign_id": self.campaign_id, "journal_id": self.journal_id, "journal_tail": self.journal_tail, "reason_code": self.reason_code, "status": self.status.value}


def _load_legacy_character(storage: JSONStorage, record_id: str) -> Optional[Character]:
    raw = storage.load("characters", record_id)
    if not isinstance(raw, Mapping) or set(raw) != {"name", "race", "character_class", "level", "description", "inventory", "notes"}:
        return None
    try:
        return Character(**dict(raw))
    except (TypeError, ValueError):
        return None


def _explicit_base_state(definition: ControlledCampaignDefinition) -> WorldState:
    return WorldState({
        "campaign_id": definition.campaign_id,
        "current_scene_id": definition.current_scene_id,
        "encounter_state": "inactive",
        "journal_id": definition.journal_id,
        "scene_participant_ids": list(definition.current_scene.participant_ids),
        "selectable_player_character_ids": list(definition.selectable_player_character_ids),
        "selected_player_character_id": None,
    }, last_sequence=0)


def _selection_reducer(state_data: Mapping[str, Any], event: GameEvent) -> Mapping[str, Any]:
    payload = event.payload
    if payload["campaign_id"] != state_data["campaign_id"]:
        raise ValueError("Campaign selection event is invalid.")
    updated = thaw_json_value(state_data)
    updated["selected_player_character_id"] = payload["player_character_id"]
    return updated


def load_controlled_campaign_runtime(storage: JSONStorage, journal_store: EventJournalStore, *, manifest_name: str = FIXTURE_MANIFEST_NAME, expected_campaign_id: str = CAMPAIGN_ID, expected_journal_id: str = JOURNAL_ID) -> CampaignRuntimeLoadResult:
    """Validate and hydrate one existing controlled campaign all-or-nothing."""
    if not isinstance(storage, JSONStorage) or not isinstance(journal_store, EventJournalStore):
        return CampaignRuntimeLoadResult(CampaignRuntimeLoadStatus.INVALID_INPUT, reason_code="invalid_dependencies")
    try:
        validate_trimmed_identifier(manifest_name, "Fixture manifest ID")
        validate_trimmed_identifier(expected_campaign_id, "Expected campaign ID")
        validate_trimmed_identifier(expected_journal_id, "Expected journal ID")
        raw_definition = storage.load(FIXTURE_MANIFEST_CATEGORY, manifest_name)
    except (TypeError, ValueError):
        return CampaignRuntimeLoadResult(CampaignRuntimeLoadStatus.INVALID_INPUT, reason_code="invalid_input")
    except Exception:
        logger.exception("Controlled fixture manifest load failed safely")
        return CampaignRuntimeLoadResult(CampaignRuntimeLoadStatus.NOT_FOUND, reason_code="manifest_unavailable")
    if raw_definition is None:
        return CampaignRuntimeLoadResult(CampaignRuntimeLoadStatus.NOT_FOUND, reason_code="manifest_missing")
    try:
        definition = ControlledCampaignDefinition.from_dict(raw_definition)
    except Exception:
        return CampaignRuntimeLoadResult(CampaignRuntimeLoadStatus.INVALID_DEFINITION, reason_code="invalid_manifest")
    if definition.campaign_id != expected_campaign_id:
        return CampaignRuntimeLoadResult(CampaignRuntimeLoadStatus.CAMPAIGN_ID_MISMATCH, definition.campaign_id, definition.journal_id, reason_code="campaign_id_mismatch")
    if definition.journal_id != expected_journal_id:
        return CampaignRuntimeLoadResult(CampaignRuntimeLoadStatus.JOURNAL_ID_MISMATCH, definition.campaign_id, definition.journal_id, reason_code="journal_id_mismatch")
    try:
        raw_campaign = storage.load("campaigns", definition.campaign_record_id)
        if not isinstance(raw_campaign, Mapping) or set(raw_campaign) != {"name", "description", "characters", "locations", "notes"}:
            return CampaignRuntimeLoadResult(CampaignRuntimeLoadStatus.NOT_FOUND, definition.campaign_id, definition.journal_id, reason_code="campaign_missing")
        campaign = Campaign(**dict(raw_campaign))
        characters = []
        for participant in definition.participants:
            character = _load_legacy_character(storage, participant.character_record_id)
            if character is None:
                return CampaignRuntimeLoadResult(CampaignRuntimeLoadStatus.NOT_FOUND, definition.campaign_id, definition.journal_id, reason_code="character_missing")
            if character.name not in campaign.characters:
                return CampaignRuntimeLoadResult(CampaignRuntimeLoadStatus.INVALID_DEFINITION, definition.campaign_id, definition.journal_id, reason_code="campaign_character_reference_missing")
            characters.append(LoadedFixtureCharacter(participant.participant_id, character))
    except Exception:
        logger.exception("Controlled fixture entity load failed safely")
        return CampaignRuntimeLoadResult(CampaignRuntimeLoadStatus.INVALID_DEFINITION, definition.campaign_id, definition.journal_id, reason_code="invalid_entity_record")
    base_state = _explicit_base_state(definition)
    projector = WorldStateProjector()
    projector.register_reducer(PLAYER_CHARACTER_SELECTED_EVENT, 1, _selection_reducer)
    projector.register_reducer(CONTROLLED_ROUND_EVENT, CONTROLLED_ROUND_SCHEMA_VERSION, reduce_controlled_round)
    hydration = hydrate_durable_runtime(journal_store, expected_journal_id=definition.journal_id, base_state=base_state, projector=projector)
    if hydration.status is not StartupHydrationStatus.SUCCESS:
        status = CampaignRuntimeLoadStatus.HYDRATION_FAILURE
        if hydration.status is StartupHydrationStatus.NOT_FOUND:
            status = CampaignRuntimeLoadStatus.NOT_FOUND
        elif hydration.status is StartupHydrationStatus.JOURNAL_ID_MISMATCH:
            status = CampaignRuntimeLoadStatus.JOURNAL_ID_MISMATCH
        return CampaignRuntimeLoadResult(status, definition.campaign_id, hydration.journal_id or definition.journal_id, hydration.tail_sequence, hydration.reason_code)
    try:
        hydrated = hydration.runtime
        engine = GameEngine()
        def selection_handler(command: GameCommand) -> GameResult:
            payload = command.payload
            if set(payload) != {"campaign_id", "player_character_id", "event_id", "occurred_at"} or payload["campaign_id"] != definition.campaign_id:
                return GameResult.success(command.command_id, {"outcome": "invalid_selection"})
            selected_id = payload["player_character_id"]
            try:
                validate_trimmed_identifier(selected_id, "Selected player character ID")
                participant = definition.participant(selected_id)
            except (KeyError, TypeError, ValueError):
                return GameResult.success(command.command_id, {"outcome": "invalid_selection"})
            if selected_id not in definition.current_scene.participant_ids or selected_id not in definition.selectable_player_character_ids or participant.kind is not ParticipantKind.PLAYER_CHARACTER or not participant.selectable_by_player:
                return GameResult.success(command.command_id, {"outcome": "invalid_selection"})
            if hydrated.state_holder.snapshot.data["selected_player_character_id"] == selected_id:
                return GameResult.success(command.command_id, {"outcome": "already_selected"})
            event = GameEvent(event_type=PLAYER_CHARACTER_SELECTED_EVENT, schema_version=1, payload={"campaign_id": definition.campaign_id, "player_character_id": selected_id}, provenance=command.provenance, actor_id=selected_id, originating_command_id=command.command_id, event_id=payload["event_id"], occurred_at=datetime.fromisoformat(payload["occurred_at"]))
            return GameResult.success(command.command_id, {"outcome": "selected"}, (event,))
        engine.register_handler(SELECT_PLAYER_CHARACTER_COMMAND, selection_handler)
        policy = AutomationPolicy({
            SELECT_PLAYER_CHARACTER_COMMAND: CapabilityAutomationRule(initiator_modes={CommandSource.HUMAN: AutomationMode.AUTOMATIC}),
            "combat.resolve_controlled_round": CapabilityAutomationRule(initiator_modes={CommandSource.HUMAN: AutomationMode.AUTOMATIC}),
        })
        pipeline = AuditedCommandPipeline(PolicyGatedCommandDispatcher(policy, engine), CommandAuditJournal(), hydrated.event_journal, projector, hydrated.state_holder, durable_journal_binding=hydrated.durable_binding)
        runtime = CampaignRuntime(definition, campaign, tuple(characters), pipeline, hydrated.state_holder, hydrated.event_journal, engine)
    except Exception:
        logger.exception("Controlled campaign runtime composition failed safely")
        return CampaignRuntimeLoadResult(CampaignRuntimeLoadStatus.INITIALIZATION_FAILURE, definition.campaign_id, definition.journal_id, hydration.tail_sequence, "runtime_composition_failed")
    return CampaignRuntimeLoadResult(CampaignRuntimeLoadStatus.SUCCESS, definition.campaign_id, definition.journal_id, hydration.tail_sequence, runtime=runtime)
