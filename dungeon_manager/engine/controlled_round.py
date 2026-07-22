"""Pure controlled-round adjudication and projection for the vertical slice."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from ._json import freeze_json_value, thaw_json_value, validate_trimmed_identifier
from .combat_domain import (
    COMBAT_CAMPAIGN_ID, COMBAT_SCENE_ID, GOBLIN_PARTICIPANT_ID,
    NEKRIA_PARTICIPANT_ID, RAPIER_ATTACK_ID, ControlledCombatDefinition,
)
from .dice import (
    AutomaticFaceSource, DiceResolutionStatus, DiceRoll, DiceRollMode,
    DiceRollProvenance, DiceRollRequest, resolve_dice_roll,
)
from .game_event import GameEvent


CONTROLLED_ROUND_COMMAND = "combat.resolve_controlled_round"
CONTROLLED_ROUND_EVENT = "combat.controlled_round_resolved"
CONTROLLED_ROUND_SCHEMA_VERSION = 1
NO_GOBLIN_BEHAVIOR_REASON = "controlled_slice_no_goblin_behavior"


class ControlledRoundStatus(str, Enum):
    RESOLVED = "resolved"
    NEKRIA_INITIATIVE_INPUT_REQUIRED = "nekria_initiative_input_required"
    GOBLIN_INITIATIVE_INPUT_REQUIRED = "goblin_initiative_input_required"
    ATTACK_INPUT_REQUIRED = "attack_input_required"
    DAMAGE_INPUT_REQUIRED = "damage_input_required"
    INVALID_INPUT = "invalid_input"
    INVALID_MODE = "invalid_mode"
    DICE_FAILURE = "dice_failure"


@dataclass(frozen=True)
class InitiativeEntry:
    participant_id: str
    modifier: int
    roll: DiceRoll

    @property
    def total(self) -> int:
        return self.roll.total

    def to_dict(self) -> dict[str, Any]:
        return {"modifier": self.modifier, "participant_id": self.participant_id, "roll": self.roll.to_dict(), "total": self.total}


@dataclass(frozen=True)
class ControlledRoundResolution:
    status: ControlledRoundStatus
    roll_id: Optional[str] = None
    dice_count: Optional[int] = None
    sides: Optional[int] = None
    modifier: Optional[int] = None
    payload: Optional[Mapping[str, Any]] = None
    reason_code: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, ControlledRoundStatus):
            raise ValueError("Controlled round status must be typed.")
        if self.status is ControlledRoundStatus.RESOLVED:
            if not isinstance(self.payload, Mapping) or any(value is not None for value in (self.roll_id, self.dice_count, self.sides, self.modifier, self.reason_code)):
                raise ValueError("Resolved controlled round requires only payload.")
            object.__setattr__(self, "payload", freeze_json_value(self.payload, "Controlled round payload"))
        else:
            if self.payload is not None:
                raise ValueError("Incomplete controlled round cannot expose payload.")
            if self.status in {
                ControlledRoundStatus.NEKRIA_INITIATIVE_INPUT_REQUIRED,
                ControlledRoundStatus.GOBLIN_INITIATIVE_INPUT_REQUIRED,
                ControlledRoundStatus.ATTACK_INPUT_REQUIRED,
                ControlledRoundStatus.DAMAGE_INPUT_REQUIRED,
            }:
                validate_trimmed_identifier(self.roll_id, "Required roll ID")
                if not all(isinstance(value, int) and not isinstance(value, bool) for value in (self.dice_count, self.sides, self.modifier)):
                    raise ValueError("Required dice metadata must be integers.")
            else:
                validate_trimmed_identifier(self.reason_code, "Controlled round reason code")

    def to_dict(self) -> dict[str, Any]:
        return {"dice_count": self.dice_count, "modifier": self.modifier, "reason_code": self.reason_code, "roll_id": self.roll_id, "sides": self.sides, "status": self.status.value}


def initiative_order(entries: tuple[InitiativeEntry, ...]) -> tuple[str, ...]:
    """Apply the frozen total, modifier, stable-ID ordering rule."""
    if len(entries) != 2 or {entry.participant_id for entry in entries} != {NEKRIA_PARTICIPANT_ID, GOBLIN_PARTICIPANT_ID}:
        raise ValueError("Controlled initiative entries are invalid.")
    return tuple(entry.participant_id for entry in sorted(entries, key=lambda item: (-item.total, -item.modifier, item.participant_id)))


def _required(status: ControlledRoundStatus, request: DiceRollRequest) -> ControlledRoundResolution:
    return ControlledRoundResolution(status, request.roll_id, request.dice_count, request.sides, request.modifier)


def _manual_face(manual_faces: Mapping[str, Any], stage: str) -> Any:
    return manual_faces.get(stage)


def _roll(request: DiceRollRequest, mode: DiceRollMode, manual_faces: Mapping[str, Any], stage: str, source: Optional[AutomaticFaceSource]):
    face = _manual_face(manual_faces, stage)
    return resolve_dice_roll(request, mode, manual_faces=(None if face is None else [face]) if mode is DiceRollMode.MANUAL else None, automatic_source=source)


def resolve_controlled_round(definition: ControlledCombatDefinition, *, mode: Any, roll_ids: Mapping[str, Any], manual_faces: Mapping[str, Any], automatic_source: Optional[AutomaticFaceSource]) -> ControlledRoundResolution:
    """Resolve every required stage in frozen order without publication."""
    if not isinstance(definition, ControlledCombatDefinition) or not isinstance(mode, DiceRollMode) or not isinstance(roll_ids, Mapping) or not isinstance(manual_faces, Mapping):
        return ControlledRoundResolution(ControlledRoundStatus.INVALID_INPUT, reason_code="invalid_round_request")
    expected_ids = {"nekria_initiative", "goblin_initiative", "attack", "damage"}
    if set(roll_ids) != expected_ids or set(manual_faces) != expected_ids:
        return ControlledRoundResolution(ControlledRoundStatus.INVALID_INPUT, reason_code="invalid_round_fields")
    try:
        nekria = definition.combatant(NEKRIA_PARTICIPANT_ID)
        goblin = definition.combatant(GOBLIN_PARTICIPANT_ID)
        attack = definition.attack(RAPIER_ATTACK_ID)
        requests = {
            "nekria_initiative": DiceRollRequest(roll_ids["nekria_initiative"], 1, 20, nekria.initiative_modifier),
            "goblin_initiative": DiceRollRequest(roll_ids["goblin_initiative"], 1, 20, goblin.initiative_modifier),
            "attack": DiceRollRequest(roll_ids["attack"], 1, 20, attack.attack_bonus),
            "damage": DiceRollRequest(roll_ids["damage"], attack.damage.dice_count, attack.damage.sides, attack.damage.modifier),
        }
    except (KeyError, TypeError, ValueError):
        return ControlledRoundResolution(ControlledRoundStatus.INVALID_INPUT, reason_code="invalid_roll_ids")
    stages = (("nekria_initiative", ControlledRoundStatus.NEKRIA_INITIATIVE_INPUT_REQUIRED), ("goblin_initiative", ControlledRoundStatus.GOBLIN_INITIATIVE_INPUT_REQUIRED), ("attack", ControlledRoundStatus.ATTACK_INPUT_REQUIRED))
    rolls: dict[str, DiceRoll] = {}
    for stage, required_status in stages:
        result = _roll(requests[stage], mode, manual_faces, stage, automatic_source)
        if result.status is DiceResolutionStatus.INPUT_REQUIRED:
            return _required(required_status, requests[stage])
        if result.status is not DiceResolutionStatus.SUCCESS:
            status = ControlledRoundStatus.INVALID_MODE if result.status is DiceResolutionStatus.INVALID_MODE else (ControlledRoundStatus.DICE_FAILURE if result.status is DiceResolutionStatus.RANDOMNESS_FAILURE else ControlledRoundStatus.INVALID_INPUT)
            return ControlledRoundResolution(status, reason_code=result.reason_code or "dice_failure")
        rolls[stage] = result.roll
    initiatives = (
        InitiativeEntry(NEKRIA_PARTICIPANT_ID, nekria.initiative_modifier, rolls["nekria_initiative"]),
        InitiativeEntry(GOBLIN_PARTICIPANT_ID, goblin.initiative_modifier, rolls["goblin_initiative"]),
    )
    order = initiative_order(initiatives)
    initial_active = order[0]
    goblin_no_action = initial_active == GOBLIN_PARTICIPANT_ID
    attack_roll = rolls["attack"]
    hit = attack_roll.total >= goblin.armor_class
    damage_roll = None
    if hit:
        damage_result = _roll(requests["damage"], mode, manual_faces, "damage", automatic_source)
        if damage_result.status is DiceResolutionStatus.INPUT_REQUIRED:
            return _required(ControlledRoundStatus.DAMAGE_INPUT_REQUIRED, requests["damage"])
        if damage_result.status is not DiceResolutionStatus.SUCCESS:
            status = ControlledRoundStatus.INVALID_MODE if damage_result.status is DiceResolutionStatus.INVALID_MODE else (ControlledRoundStatus.DICE_FAILURE if damage_result.status is DiceResolutionStatus.RANDOMNESS_FAILURE else ControlledRoundStatus.INVALID_INPUT)
            return ControlledRoundResolution(status, reason_code=damage_result.reason_code or "dice_failure")
        damage_roll = damage_result.roll
    rolled_damage = 0 if damage_roll is None else damage_roll.total
    previous_hp = goblin.starting_hit_points
    resulting_hp = max(0, previous_hp - rolled_damage)
    applied_damage = previous_hp - resulting_hp
    defeated = resulting_hp == 0
    nekria_index = order.index(NEKRIA_PARTICIPANT_ID)
    if defeated:
        final_active, final_round, encounter_status = None, 1, "completed"
    else:
        next_index = (nekria_index + 1) % len(order)
        final_active = order[next_index]
        final_round = 2 if next_index == 0 else 1
        encounter_status = "active"
    payload = {
        "attack": {"attack_id": RAPIER_ATTACK_ID, "attack_roll": attack_roll.to_dict(), "attacker_id": NEKRIA_PARTICIPANT_ID, "damage_roll": None if damage_roll is None else damage_roll.to_dict(), "hit": hit, "target_ac": goblin.armor_class, "target_id": GOBLIN_PARTICIPANT_ID},
        "campaign_id": definition.campaign_id,
        "encounter_id": definition.scene_id,
        "final": {"active_participant_id": final_active, "encounter_status": encounter_status, "round_number": final_round},
        "goblin": {"applied_damage": applied_damage, "defeated": defeated, "previous_hit_points": previous_hp, "resulting_hit_points": resulting_hp, "rolled_damage": rolled_damage},
        "initiative": {"entries": [item.to_dict() for item in initiatives], "initial_active_participant_id": initial_active, "initial_round_number": 1, "order": list(order)},
        "mode": mode.value,
        "no_action": {"occurred": goblin_no_action, "reason_code": NO_GOBLIN_BEHAVIOR_REASON if goblin_no_action else None},
        "scene_id": definition.scene_id,
        "turn": {"nekria_round_number": 1, "nekria_turn_reached": True},
    }
    return ControlledRoundResolution(ControlledRoundStatus.RESOLVED, payload=payload)


def _validated_roll(
    value: Any,
    *,
    sides: int,
    modifier: int,
    mode: DiceRollMode,
) -> dict[str, Any]:
    """Validate one persisted single-die result without rerolling it."""
    if not isinstance(value, Mapping) or set(value) != {
        "dice_count", "mode", "modifier", "natural_faces", "provenance",
        "roll_id", "sides", "subtotal", "total",
    }:
        raise ValueError("Controlled persisted dice roll is invalid.")
    try:
        request = DiceRollRequest(value["roll_id"], value["dice_count"], value["sides"], value["modifier"])
        persisted_mode = DiceRollMode(value["mode"])
        provenance = DiceRollProvenance(value["provenance"])
    except (TypeError, ValueError):
        raise ValueError("Controlled persisted dice roll is invalid.") from None
    if request.dice_count != 1 or request.sides != sides or request.modifier != modifier or persisted_mode is not mode:
        raise ValueError("Controlled persisted dice roll is invalid.")
    faces = value["natural_faces"]
    if not isinstance(faces, Sequence) or isinstance(faces, (str, bytes)):
        raise ValueError("Controlled persisted dice roll is invalid.")
    try:
        DiceRoll(request, persisted_mode, provenance, tuple(faces), value["subtotal"], value["total"])
    except (TypeError, ValueError):
        raise ValueError("Controlled persisted dice roll is invalid.") from None
    return thaw_json_value(value)


def validate_controlled_round_payload(payload: Any) -> dict[str, Any]:
    """Reject malformed or semantically impossible persisted round facts."""
    if not isinstance(payload, Mapping) or set(payload) != {"attack", "campaign_id", "encounter_id", "final", "goblin", "initiative", "mode", "no_action", "scene_id", "turn"}:
        raise ValueError("Controlled round payload fields are invalid.")
    if payload["campaign_id"] != COMBAT_CAMPAIGN_ID or payload["scene_id"] != COMBAT_SCENE_ID or payload["encounter_id"] != COMBAT_SCENE_ID:
        raise ValueError("Controlled round identity is invalid.")
    try:
        mode = DiceRollMode(payload["mode"])
    except (TypeError, ValueError):
        raise ValueError("Controlled round mode is invalid.")
    initiative = payload["initiative"]
    attack = payload["attack"]
    goblin = payload["goblin"]
    final = payload["final"]
    no_action = payload["no_action"]
    if not all(isinstance(value, Mapping) for value in (initiative, attack, goblin, final, no_action)):
        raise ValueError("Controlled round structures are invalid.")
    if attack.get("attacker_id") != NEKRIA_PARTICIPANT_ID or attack.get("target_id") != GOBLIN_PARTICIPANT_ID or attack.get("attack_id") != RAPIER_ATTACK_ID or attack.get("target_ac") != 15:
        raise ValueError("Controlled round attack references are invalid.")
    entries = initiative.get("entries")
    order = initiative.get("order")
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)) or len(entries) != 2 or not isinstance(order, Sequence) or isinstance(order, (str, bytes)) or set(order) != {NEKRIA_PARTICIPANT_ID, GOBLIN_PARTICIPANT_ID}:
        raise ValueError("Controlled initiative is invalid.")
    normalized = []
    for entry, expected_id, expected_mod in zip(entries, (NEKRIA_PARTICIPANT_ID, GOBLIN_PARTICIPANT_ID), (3, 2)):
        if not isinstance(entry, Mapping) or set(entry) != {"modifier", "participant_id", "roll", "total"} or entry.get("participant_id") != expected_id or entry.get("modifier") != expected_mod:
            raise ValueError("Controlled initiative entry is invalid.")
        roll = _validated_roll(entry["roll"], sides=20, modifier=expected_mod, mode=mode)
        if entry.get("total") != roll["total"]:
            raise ValueError("Controlled initiative roll is invalid.")
        normalized.append((entry["participant_id"], entry["modifier"], entry["total"]))
    expected_order = tuple(item[0] for item in sorted(normalized, key=lambda item: (-item[2], -item[1], item[0])))
    if tuple(order) != expected_order or initiative.get("initial_active_participant_id") != order[0] or initiative.get("initial_round_number") != 1:
        raise ValueError("Controlled initiative order is invalid.")
    goblin_first = order[0] == GOBLIN_PARTICIPANT_ID
    if set(no_action) != {"occurred", "reason_code"} or no_action.get("occurred") is not goblin_first or no_action.get("reason_code") != (NO_GOBLIN_BEHAVIOR_REASON if goblin_first else None):
        raise ValueError("Controlled no-action advancement is invalid.")
    if set(attack) != {"attack_id", "attack_roll", "attacker_id", "damage_roll", "hit", "target_ac", "target_id"}:
        raise ValueError("Controlled round attack structure is invalid.")
    attack_roll = _validated_roll(attack.get("attack_roll"), sides=20, modifier=5, mode=mode)
    if not isinstance(attack.get("hit"), bool):
        raise ValueError("Controlled attack roll is invalid.")
    if attack.get("hit") is not (attack_roll["total"] >= 15):
        raise ValueError("Controlled hit result is invalid.")
    damage_roll = attack.get("damage_roll")
    if not attack["hit"] and damage_roll is not None:
        raise ValueError("Misses cannot contain damage rolls.")
    rolled_damage = goblin.get("rolled_damage")
    if attack["hit"]:
        damage_roll = _validated_roll(damage_roll, sides=8, modifier=3, mode=mode)
        if rolled_damage != damage_roll["total"]:
            raise ValueError("Controlled damage roll is invalid.")
    elif rolled_damage != 0:
        raise ValueError("Miss damage is invalid.")
    if set(goblin) != {"applied_damage", "defeated", "previous_hit_points", "resulting_hit_points", "rolled_damage"} or any(not isinstance(goblin[key], int) or isinstance(goblin[key], bool) for key in ("applied_damage", "previous_hit_points", "resulting_hit_points", "rolled_damage")) or not isinstance(goblin.get("defeated"), bool) or goblin.get("previous_hit_points") != 7 or goblin.get("resulting_hit_points") != max(0, 7 - rolled_damage) or goblin.get("applied_damage") != 7 - goblin["resulting_hit_points"] or goblin.get("defeated") is not (goblin["resulting_hit_points"] == 0):
        raise ValueError("Controlled hit point transition is invalid.")
    defeated = goblin["defeated"]
    expected_active = None if defeated else GOBLIN_PARTICIPANT_ID
    expected_round = 1 if defeated or tuple(order) == (NEKRIA_PARTICIPANT_ID, GOBLIN_PARTICIPANT_ID) else 2
    turn = payload["turn"]
    if not isinstance(turn, Mapping) or set(turn) != {"nekria_round_number", "nekria_turn_reached"} or turn.get("nekria_round_number") != 1 or turn.get("nekria_turn_reached") is not True:
        raise ValueError("Controlled Nekria turn state is invalid.")
    if set(final) != {"active_participant_id", "encounter_status", "round_number"} or not isinstance(final.get("round_number"), int) or isinstance(final.get("round_number"), bool) or final.get("active_participant_id") != expected_active or final.get("round_number") != expected_round or final.get("encounter_status") != ("completed" if defeated else "active"):
        raise ValueError("Controlled final turn state is invalid.")
    return thaw_json_value(payload)


def reduce_controlled_round(state_data: Mapping[str, Any], event: GameEvent) -> Mapping[str, Any]:
    if event.event_type != CONTROLLED_ROUND_EVENT or event.schema_version != CONTROLLED_ROUND_SCHEMA_VERSION:
        raise ValueError("Controlled round event type is invalid.")
    payload = validate_controlled_round_payload(event.payload)
    if state_data.get("campaign_id") != payload["campaign_id"] or state_data.get("current_scene_id") != payload["scene_id"] or state_data.get("selected_player_character_id") != NEKRIA_PARTICIPANT_ID or "controlled_combat" in state_data:
        raise ValueError("Controlled round projection state is invalid.")
    updated = thaw_json_value(state_data)
    updated["controlled_combat"] = payload
    return updated
