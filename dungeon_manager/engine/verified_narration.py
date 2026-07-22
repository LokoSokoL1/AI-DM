"""Immutable narration facts derived from one verified controlled-round event."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from ._json import thaw_json_value, validate_optional_identifier, validate_trimmed_identifier
from .controlled_round import (
    CONTROLLED_ROUND_EVENT,
    CONTROLLED_ROUND_SCHEMA_VERSION,
    validate_controlled_round_payload,
)
from .dice import DiceRollMode, DiceRollProvenance
from .journals import GameEventJournalEntry
from .world_state import WorldState


@dataclass(frozen=True)
class NarrationRollFact:
    """The minimum immutable facts needed to describe one recorded roll."""

    natural_face: int
    modifier: int
    total: int
    provenance: DiceRollProvenance

    def __post_init__(self) -> None:
        for value, label in (
            (self.natural_face, "Narration natural face"),
            (self.modifier, "Narration modifier"),
            (self.total, "Narration total"),
        ):
            if not isinstance(value, int) or isinstance(value, bool):
                raise ValueError(f"{label} must be an integer.")
        if self.natural_face < 1 or self.total != self.natural_face + self.modifier:
            raise ValueError("Narration roll facts are inconsistent.")
        if not isinstance(self.provenance, DiceRollProvenance):
            raise ValueError("Narration roll provenance must be typed.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "modifier": self.modifier,
            "natural_face": self.natural_face,
            "provenance": self.provenance.value,
            "total": self.total,
        }


@dataclass(frozen=True)
class VerifiedNarrationPacket:
    """Provider-neutral presentation facts bound to one journal entry."""

    source_event_id: str
    source_event_sequence: int
    campaign_id: str
    scene_id: str
    encounter_id: str
    attacker_id: str
    target_id: str
    attack_id: str
    dice_mode: DiceRollMode
    nekria_initiative: NarrationRollFact
    goblin_initiative: NarrationRollFact
    initiative_order: tuple[str, str]
    goblin_no_action_occurred: bool
    goblin_no_action_reason: Optional[str]
    attack: NarrationRollFact
    target_armor_class: int
    hit: bool
    damage: Optional[NarrationRollFact]
    goblin_hit_points_before: int
    goblin_hit_points_after: int
    goblin_applied_damage: int
    goblin_defeated: bool
    final_round_number: int
    final_active_participant_id: Optional[str]
    encounter_completed: bool

    def __post_init__(self) -> None:
        for value, label in (
            (self.source_event_id, "Narration source event ID"),
            (self.campaign_id, "Narration campaign ID"),
            (self.scene_id, "Narration scene ID"),
            (self.encounter_id, "Narration encounter ID"),
            (self.attacker_id, "Narration attacker ID"),
            (self.target_id, "Narration target ID"),
            (self.attack_id, "Narration attack ID"),
        ):
            validate_trimmed_identifier(value, label)
        validate_optional_identifier(
            self.final_active_participant_id,
            "Narration final active participant ID",
        )
        if (
            not isinstance(self.source_event_sequence, int)
            or isinstance(self.source_event_sequence, bool)
            or self.source_event_sequence < 1
        ):
            raise ValueError("Narration source event sequence must be positive.")
        if not isinstance(self.dice_mode, DiceRollMode):
            raise ValueError("Narration dice mode must be typed.")
        for roll in (self.nekria_initiative, self.goblin_initiative, self.attack):
            if not isinstance(roll, NarrationRollFact):
                raise ValueError("Narration packet rolls must be typed.")
        if self.damage is not None and not isinstance(self.damage, NarrationRollFact):
            raise ValueError("Narration damage must be typed when present.")
        if (
            not isinstance(self.initiative_order, tuple)
            or len(self.initiative_order) != 2
            or set(self.initiative_order) != {"nekria", "goblin-1"}
        ):
            raise ValueError("Narration initiative order is invalid.")
        if not isinstance(self.goblin_no_action_occurred, bool):
            raise ValueError("Narration no-action fact must be boolean.")
        if self.goblin_no_action_occurred:
            validate_trimmed_identifier(
                self.goblin_no_action_reason,
                "Narration no-action reason",
            )
        elif self.goblin_no_action_reason is not None:
            raise ValueError("Narration no-action reason is not applicable.")
        for value, label, minimum in (
            (self.target_armor_class, "Narration target armor class", 1),
            (self.goblin_hit_points_before, "Narration previous hit points", 1),
            (self.goblin_hit_points_after, "Narration resulting hit points", 0),
            (self.goblin_applied_damage, "Narration applied damage", 0),
            (self.final_round_number, "Narration final round", 1),
        ):
            if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
                raise ValueError(f"{label} is invalid.")
        if not all(isinstance(value, bool) for value in (self.hit, self.goblin_defeated, self.encounter_completed)):
            raise ValueError("Narration outcome flags must be boolean.")
        if self.hit != (self.attack.total >= self.target_armor_class):
            raise ValueError("Narration hit facts are inconsistent.")
        if self.hit != (self.damage is not None):
            raise ValueError("Narration damage applicability is inconsistent.")
        if (
            self.goblin_hit_points_after > self.goblin_hit_points_before
            or self.goblin_applied_damage
            != self.goblin_hit_points_before - self.goblin_hit_points_after
            or (self.damage is None and self.goblin_applied_damage != 0)
            or (
                self.damage is not None
                and self.damage.total < self.goblin_applied_damage
            )
        ):
            raise ValueError("Narration damage facts are inconsistent.")
        if self.goblin_defeated != (self.goblin_hit_points_after == 0):
            raise ValueError("Narration defeat facts are inconsistent.")
        if self.encounter_completed != self.goblin_defeated:
            raise ValueError("Narration encounter completion is inconsistent.")

    def to_dict(self) -> dict[str, Any]:
        return {
            "attack": self.attack.to_dict(),
            "attack_id": self.attack_id,
            "attacker_id": self.attacker_id,
            "campaign_id": self.campaign_id,
            "damage": None if self.damage is None else self.damage.to_dict(),
            "dice_mode": self.dice_mode.value,
            "encounter_completed": self.encounter_completed,
            "encounter_id": self.encounter_id,
            "final_active_participant_id": self.final_active_participant_id,
            "final_round_number": self.final_round_number,
            "goblin_defeated": self.goblin_defeated,
            "goblin_applied_damage": self.goblin_applied_damage,
            "goblin_hit_points_after": self.goblin_hit_points_after,
            "goblin_hit_points_before": self.goblin_hit_points_before,
            "goblin_initiative": self.goblin_initiative.to_dict(),
            "goblin_no_action_occurred": self.goblin_no_action_occurred,
            "goblin_no_action_reason": self.goblin_no_action_reason,
            "hit": self.hit,
            "initiative_order": list(self.initiative_order),
            "nekria_initiative": self.nekria_initiative.to_dict(),
            "scene_id": self.scene_id,
            "source_event_id": self.source_event_id,
            "source_event_sequence": self.source_event_sequence,
            "target_armor_class": self.target_armor_class,
            "target_id": self.target_id,
        }


class NarrationPacketBuildStatus(str, Enum):
    SUCCESS = "success"
    INVALID_INPUT = "invalid_input"
    INVALID_EVENT = "invalid_event"
    SOURCE_MISMATCH = "source_mismatch"


@dataclass(frozen=True)
class NarrationPacketBuildResult:
    status: NarrationPacketBuildStatus
    packet: Optional[VerifiedNarrationPacket] = None
    source_event_id: Optional[str] = None
    source_event_sequence: Optional[int] = None
    reason_code: Optional[str] = None

    def __post_init__(self) -> None:
        if not isinstance(self.status, NarrationPacketBuildStatus):
            raise ValueError("Narration packet status must be typed.")
        if self.source_event_id is not None:
            validate_trimmed_identifier(self.source_event_id, "Narration packet source event ID")
        if self.source_event_sequence is not None and (
            not isinstance(self.source_event_sequence, int)
            or isinstance(self.source_event_sequence, bool)
            or self.source_event_sequence < 1
        ):
            raise ValueError("Narration packet source event sequence must be positive.")
        if self.status is NarrationPacketBuildStatus.SUCCESS:
            if (
                not isinstance(self.packet, VerifiedNarrationPacket)
                or self.source_event_id != self.packet.source_event_id
                or self.source_event_sequence != self.packet.source_event_sequence
                or self.reason_code is not None
            ):
                raise ValueError("Successful narration packet construction is invalid.")
        else:
            if self.packet is not None:
                raise ValueError("Failed narration packet construction cannot expose a packet.")
            validate_trimmed_identifier(self.reason_code, "Narration packet reason code")

    def to_dict(self) -> dict[str, Any]:
        return {
            "reason_code": self.reason_code,
            "source_event_id": self.source_event_id,
            "source_event_sequence": self.source_event_sequence,
            "status": self.status.value,
        }


def _failure(
    status: NarrationPacketBuildStatus,
    reason_code: str,
    entry: Optional[GameEventJournalEntry] = None,
) -> NarrationPacketBuildResult:
    return NarrationPacketBuildResult(
        status,
        source_event_id=None if entry is None else entry.event.event_id,
        source_event_sequence=None if entry is None else entry.sequence,
        reason_code=reason_code,
    )


def _roll_fact(value: Mapping[str, Any]) -> NarrationRollFact:
    faces = value["natural_faces"]
    if not isinstance(faces, Sequence) or isinstance(faces, (str, bytes)) or len(faces) != 1:
        raise ValueError("Narration source roll is invalid.")
    return NarrationRollFact(
        natural_face=faces[0],
        modifier=value["modifier"],
        total=value["total"],
        provenance=DiceRollProvenance(value["provenance"]),
    )


def build_verified_narration_packet(
    entry: Any,
    projected_state: Any,
) -> NarrationPacketBuildResult:
    """Build only from one validated event and its exact synchronized projection."""

    if not isinstance(entry, GameEventJournalEntry) or not isinstance(projected_state, WorldState):
        return _failure(NarrationPacketBuildStatus.INVALID_INPUT, "invalid_narration_source")
    event = entry.event
    if event.event_type != CONTROLLED_ROUND_EVENT or event.schema_version != CONTROLLED_ROUND_SCHEMA_VERSION:
        return _failure(NarrationPacketBuildStatus.INVALID_EVENT, "unsupported_source_event", entry)
    try:
        event.validate()
        payload = validate_controlled_round_payload(event.payload)
        projected_state.validate()
    except (TypeError, ValueError):
        return _failure(NarrationPacketBuildStatus.INVALID_EVENT, "invalid_source_event", entry)
    state_data = projected_state.data
    projected_combat = state_data.get("controlled_combat")
    if (
        projected_state.last_sequence != entry.sequence
        or state_data.get("campaign_id") != payload["campaign_id"]
        or state_data.get("current_scene_id") != payload["scene_id"]
        or state_data.get("selected_player_character_id") != "nekria"
        or not isinstance(projected_combat, Mapping)
        or thaw_json_value(projected_combat) != payload
    ):
        return _failure(NarrationPacketBuildStatus.SOURCE_MISMATCH, "event_projection_mismatch", entry)
    try:
        initiative_entries = payload["initiative"]["entries"]
        damage_roll = payload["attack"]["damage_roll"]
        packet = VerifiedNarrationPacket(
            source_event_id=event.event_id,
            source_event_sequence=entry.sequence,
            campaign_id=payload["campaign_id"],
            scene_id=payload["scene_id"],
            encounter_id=payload["encounter_id"],
            attacker_id=payload["attack"]["attacker_id"],
            target_id=payload["attack"]["target_id"],
            attack_id=payload["attack"]["attack_id"],
            dice_mode=DiceRollMode(payload["mode"]),
            nekria_initiative=_roll_fact(initiative_entries[0]["roll"]),
            goblin_initiative=_roll_fact(initiative_entries[1]["roll"]),
            initiative_order=tuple(payload["initiative"]["order"]),
            goblin_no_action_occurred=payload["no_action"]["occurred"],
            goblin_no_action_reason=payload["no_action"]["reason_code"],
            attack=_roll_fact(payload["attack"]["attack_roll"]),
            target_armor_class=payload["attack"]["target_ac"],
            hit=payload["attack"]["hit"],
            damage=None if damage_roll is None else _roll_fact(damage_roll),
            goblin_hit_points_before=payload["goblin"]["previous_hit_points"],
            goblin_hit_points_after=payload["goblin"]["resulting_hit_points"],
            goblin_applied_damage=payload["goblin"]["applied_damage"],
            goblin_defeated=payload["goblin"]["defeated"],
            final_round_number=payload["final"]["round_number"],
            final_active_participant_id=payload["final"]["active_participant_id"],
            encounter_completed=payload["final"]["encounter_status"] == "completed",
        )
    except (KeyError, TypeError, ValueError):
        return _failure(NarrationPacketBuildStatus.INVALID_EVENT, "invalid_narration_facts", entry)
    return NarrationPacketBuildResult(
        NarrationPacketBuildStatus.SUCCESS,
        packet,
        packet.source_event_id,
        packet.source_event_sequence,
    )
