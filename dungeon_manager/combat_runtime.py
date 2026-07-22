"""All-or-nothing validation of the controlled combat domain against a runtime."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from dungeon_manager.campaign_runtime import CampaignRuntime, GOBLIN_ID, NEKRIA_ID
from dungeon_manager.engine.combat_domain import ControlledCombatDefinition, InitialCombatSeed, RAPIER_ATTACK_ID, controlled_combat_definition, initial_combat_seed


logger = logging.getLogger("DungeonManager")


class CombatCompositionStatus(str, Enum):
    SUCCESS = "success"
    INVALID_INPUT = "invalid_input"
    INVALID_DEFINITION = "invalid_definition"
    REFERENCE_ERROR = "reference_error"
    CAMPAIGN_MISMATCH = "campaign_mismatch"
    SCENE_MISMATCH = "scene_mismatch"
    PLAYER_NOT_SELECTED = "player_not_selected"
    SELECTED_CHARACTER_MISMATCH = "selected_character_mismatch"


@dataclass(frozen=True)
class ControlledCombatDomain:
    definition: ControlledCombatDefinition
    seed: InitialCombatSeed

    def __post_init__(self) -> None:
        if not isinstance(self.definition, ControlledCombatDefinition) or not isinstance(self.seed, InitialCombatSeed):
            raise ValueError("Controlled combat domain requires complete typed data.")


@dataclass(frozen=True)
class CombatCompositionResult:
    status: CombatCompositionStatus
    campaign_id: Optional[str] = None
    scene_id: Optional[str] = None
    reason_code: Optional[str] = None
    domain: Optional[ControlledCombatDomain] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, CombatCompositionStatus):
            raise ValueError("Combat composition status must be typed.")
        if self.status is CombatCompositionStatus.SUCCESS:
            if not isinstance(self.domain, ControlledCombatDomain) or self.reason_code is not None:
                raise ValueError("Successful combat composition requires a complete domain.")
        elif self.domain is not None:
            raise ValueError("Failed combat composition cannot expose partial combat data.")

    def to_dict(self) -> dict[str, Any]:
        return {"campaign_id": self.campaign_id, "reason_code": self.reason_code, "scene_id": self.scene_id, "status": self.status.value}


def _failure(status: CombatCompositionStatus, runtime: Optional[CampaignRuntime], reason_code: str) -> CombatCompositionResult:
    return CombatCompositionResult(status, None if runtime is None else runtime.definition.campaign_id, None if runtime is None else runtime.current_scene_id, reason_code)


def compose_controlled_combat_domain(runtime: Any, definition: Optional[ControlledCombatDefinition] = None) -> CombatCompositionResult:
    """Expose static controlled combat data only after exact runtime validation."""
    if not isinstance(runtime, CampaignRuntime):
        return _failure(CombatCompositionStatus.INVALID_INPUT, None, "invalid_runtime")
    if definition is None:
        definition = controlled_combat_definition()
    if not isinstance(definition, ControlledCombatDefinition):
        return _failure(CombatCompositionStatus.INVALID_INPUT, runtime, "invalid_definition_input")
    try:
        definition.validate()
    except (TypeError, ValueError):
        return _failure(CombatCompositionStatus.INVALID_DEFINITION, runtime, "invalid_definition")
    if definition.campaign_id != runtime.definition.campaign_id:
        return _failure(CombatCompositionStatus.CAMPAIGN_MISMATCH, runtime, "campaign_id_mismatch")
    if definition.scene_id != runtime.current_scene_id:
        return _failure(CombatCompositionStatus.SCENE_MISMATCH, runtime, "scene_id_mismatch")
    if runtime.selected_player_character_id is None:
        return _failure(CombatCompositionStatus.PLAYER_NOT_SELECTED, runtime, "player_not_selected")
    if runtime.selected_player_character_id != NEKRIA_ID:
        return _failure(CombatCompositionStatus.SELECTED_CHARACTER_MISMATCH, runtime, "selected_character_mismatch")
    try:
        if set(runtime.participant_ids) != {NEKRIA_ID, GOBLIN_ID} or {item.participant_id for item in definition.combatants} != {NEKRIA_ID, GOBLIN_ID}:
            return _failure(CombatCompositionStatus.REFERENCE_ERROR, runtime, "encounter_participants_mismatch")
        nekria = runtime.definition.participant(NEKRIA_ID)
        goblin = runtime.definition.participant(GOBLIN_ID)
        if not nekria.selectable_by_player or goblin.selectable_by_player or nekria.kind.value != "player_character" or goblin.kind.value != "npc":
            return _failure(CombatCompositionStatus.REFERENCE_ERROR, runtime, "runtime_participant_roles_invalid")
        if RAPIER_ATTACK_ID not in definition.combatant(NEKRIA_ID).attack_ids or definition.attack(RAPIER_ATTACK_ID).owner_participant_id != NEKRIA_ID:
            return _failure(CombatCompositionStatus.REFERENCE_ERROR, runtime, "rapier_reference_invalid")
        characters = {item.participant_id: item.character for item in runtime.characters}
        if set(characters) != {NEKRIA_ID, GOBLIN_ID} or "Rapier" not in characters[NEKRIA_ID].inventory:
            return _failure(CombatCompositionStatus.REFERENCE_ERROR, runtime, "static_character_reference_invalid")
        seed = initial_combat_seed(definition)
        return CombatCompositionResult(CombatCompositionStatus.SUCCESS, runtime.definition.campaign_id, runtime.current_scene_id, domain=ControlledCombatDomain(definition, seed))
    except Exception:
        logger.exception("Controlled combat composition failed safely")
        return _failure(CombatCompositionStatus.REFERENCE_ERROR, runtime, "runtime_reference_invalid")
