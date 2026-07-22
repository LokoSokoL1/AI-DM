"""Immutable, storage-free combat definitions for the one controlled fixture.

This module describes static combat data and its deterministic unstarted seed.
It neither starts combat nor resolves dice, attacks, damage, or events.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any

from ._json import validate_trimmed_identifier
from .dice import MAX_DICE_COUNT, MAX_DIE_SIDES, MAX_MODIFIER, MIN_DICE_COUNT, MIN_DIE_SIDES, MIN_MODIFIER


COMBAT_DEFINITION_SCHEMA_VERSION = 1
COMBAT_CAMPAIGN_ID = "vertical-slice-v1"
COMBAT_SCENE_ID = "controlled-goblin-encounter"
NEKRIA_PARTICIPANT_ID = "nekria"
GOBLIN_PARTICIPANT_ID = "goblin-1"
RAPIER_ATTACK_ID = "nekria-rapier"

MIN_ARMOR_CLASS = 1
MAX_ARMOR_CLASS = 30
MIN_HIT_POINTS = 1
MAX_HIT_POINTS = 500
MIN_COMBAT_MODIFIER = -20
MAX_COMBAT_MODIFIER = 20


def _bounded_integer(value: Any, label: str, minimum: int, maximum: int) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum or value > maximum:
        raise ValueError(f"{label} is outside the supported range.")


class CombatantRole(str, Enum):
    PLAYER = "player"
    HOSTILE = "hostile"


@dataclass(frozen=True)
class DamageDiceSpecification:
    dice_count: int
    sides: int
    modifier: int
    damage_type_id: str

    def __post_init__(self) -> None:
        _bounded_integer(self.dice_count, "Damage dice count", MIN_DICE_COUNT, MAX_DICE_COUNT)
        _bounded_integer(self.sides, "Damage die sides", MIN_DIE_SIDES, MAX_DIE_SIDES)
        _bounded_integer(self.modifier, "Damage modifier", MIN_MODIFIER, MAX_MODIFIER)
        validate_trimmed_identifier(self.damage_type_id, "Damage type ID")

    def to_dict(self) -> dict[str, Any]:
        return {"damage_type_id": self.damage_type_id, "dice_count": self.dice_count, "modifier": self.modifier, "sides": self.sides}


@dataclass(frozen=True)
class AttackDefinition:
    attack_id: str
    owner_participant_id: str
    attack_bonus: int
    damage: DamageDiceSpecification

    def __post_init__(self) -> None:
        validate_trimmed_identifier(self.attack_id, "Attack ID")
        validate_trimmed_identifier(self.owner_participant_id, "Attack owner participant ID")
        _bounded_integer(self.attack_bonus, "Attack bonus", MIN_COMBAT_MODIFIER, MAX_COMBAT_MODIFIER)
        if not isinstance(self.damage, DamageDiceSpecification):
            raise ValueError("Attack damage must be a typed damage dice specification.")

    def to_dict(self) -> dict[str, Any]:
        return {"attack_bonus": self.attack_bonus, "attack_id": self.attack_id, "damage": self.damage.to_dict(), "owner_participant_id": self.owner_participant_id}


@dataclass(frozen=True)
class CombatantDefinition:
    participant_id: str
    role: CombatantRole
    armor_class: int
    maximum_hit_points: int
    starting_hit_points: int
    initiative_modifier: int
    attack_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_trimmed_identifier(self.participant_id, "Combatant participant ID")
        if not isinstance(self.role, CombatantRole):
            raise ValueError("Combatant role must be typed.")
        _bounded_integer(self.armor_class, "Armor class", MIN_ARMOR_CLASS, MAX_ARMOR_CLASS)
        _bounded_integer(self.maximum_hit_points, "Maximum hit points", MIN_HIT_POINTS, MAX_HIT_POINTS)
        _bounded_integer(self.starting_hit_points, "Starting hit points", MIN_HIT_POINTS, self.maximum_hit_points)
        _bounded_integer(self.initiative_modifier, "Initiative modifier", MIN_COMBAT_MODIFIER, MAX_COMBAT_MODIFIER)
        if not isinstance(self.attack_ids, tuple) or len(set(self.attack_ids)) != len(self.attack_ids):
            raise ValueError("Combatant attack references must be a unique immutable collection.")
        for attack_id in self.attack_ids:
            validate_trimmed_identifier(attack_id, "Combatant attack ID")

    def to_dict(self) -> dict[str, Any]:
        return {"armor_class": self.armor_class, "attack_ids": list(self.attack_ids), "initiative_modifier": self.initiative_modifier, "maximum_hit_points": self.maximum_hit_points, "participant_id": self.participant_id, "role": self.role.value, "starting_hit_points": self.starting_hit_points}


@dataclass(frozen=True)
class ControlledCombatDefinition:
    schema_version: int
    campaign_id: str
    scene_id: str
    combatants: tuple[CombatantDefinition, ...]
    attacks: tuple[AttackDefinition, ...]

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if not isinstance(self.schema_version, int) or isinstance(self.schema_version, bool) or self.schema_version != COMBAT_DEFINITION_SCHEMA_VERSION:
            raise ValueError("Combat definition schema version is unsupported.")
        validate_trimmed_identifier(self.campaign_id, "Combat campaign ID")
        validate_trimmed_identifier(self.scene_id, "Combat scene ID")
        if not isinstance(self.combatants, tuple) or not isinstance(self.attacks, tuple) or not self.combatants:
            raise ValueError("Combat definition collections are invalid.")
        if any(not isinstance(item, CombatantDefinition) for item in self.combatants) or any(not isinstance(item, AttackDefinition) for item in self.attacks):
            raise ValueError("Combat definition members must be typed.")
        participant_ids = [item.participant_id for item in self.combatants]
        attack_ids = [item.attack_id for item in self.attacks]
        if len(set(participant_ids)) != len(participant_ids) or len(set(attack_ids)) != len(attack_ids):
            raise ValueError("Combat definition identities must be unique.")
        participants = {item.participant_id: item for item in self.combatants}
        attacks = {item.attack_id: item for item in self.attacks}
        for combatant in self.combatants:
            for attack_id in combatant.attack_ids:
                attack = attacks.get(attack_id)
                if attack is None or attack.owner_participant_id != combatant.participant_id:
                    raise ValueError("Combatant attack references are invalid.")
        for attack in self.attacks:
            if attack.owner_participant_id not in participants:
                raise ValueError("Attack owner is absent from the encounter.")

    def combatant(self, participant_id: str) -> CombatantDefinition:
        for item in self.combatants:
            if item.participant_id == participant_id:
                return item
        raise KeyError(participant_id)

    def attack(self, attack_id: str) -> AttackDefinition:
        for item in self.attacks:
            if item.attack_id == attack_id:
                return item
        raise KeyError(attack_id)

    def to_dict(self) -> dict[str, Any]:
        return {"attacks": [item.to_dict() for item in self.attacks], "campaign_id": self.campaign_id, "combatants": [item.to_dict() for item in self.combatants], "scene_id": self.scene_id, "schema_version": self.schema_version}


@dataclass(frozen=True)
class InitialCombatSeed:
    campaign_id: str
    scene_id: str
    participant_hit_points: tuple[tuple[str, int], ...]
    initiative_order: tuple[str, ...] = ()
    active_participant_id: None = None
    round_number: int = 0
    last_attack_id: None = None
    last_damage: None = None
    defeated_participant_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        validate_trimmed_identifier(self.campaign_id, "Combat seed campaign ID")
        validate_trimmed_identifier(self.scene_id, "Combat seed scene ID")
        if not isinstance(self.participant_hit_points, tuple) or not self.participant_hit_points:
            raise ValueError("Combat seed hit points must be a non-empty immutable collection.")
        participant_ids = []
        for participant_id, hit_points in self.participant_hit_points:
            validate_trimmed_identifier(participant_id, "Combat seed participant ID")
            _bounded_integer(hit_points, "Combat seed hit points", MIN_HIT_POINTS, MAX_HIT_POINTS)
            participant_ids.append(participant_id)
        if len(set(participant_ids)) != len(participant_ids) or self.initiative_order != () or self.active_participant_id is not None or self.round_number != 0 or self.last_attack_id is not None or self.last_damage is not None or self.defeated_participant_ids != ():
            raise ValueError("Initial combat seed must be explicitly unstarted.")

    def to_dict(self) -> dict[str, Any]:
        return {"active_participant_id": None, "campaign_id": self.campaign_id, "defeated_participant_ids": [], "initiative_order": [], "last_attack_id": None, "last_damage": None, "participant_hit_points": [{"hit_points": hp, "participant_id": participant_id} for participant_id, hp in self.participant_hit_points], "round_number": 0, "scene_id": self.scene_id}


def initial_combat_seed(definition: ControlledCombatDefinition) -> InitialCombatSeed:
    if not isinstance(definition, ControlledCombatDefinition):
        raise ValueError("Initial combat seed requires a combat definition.")
    definition.validate()
    return InitialCombatSeed(definition.campaign_id, definition.scene_id, tuple((item.participant_id, item.starting_hit_points) for item in definition.combatants))


def controlled_combat_definition() -> ControlledCombatDefinition:
    rapier = AttackDefinition(RAPIER_ATTACK_ID, NEKRIA_PARTICIPANT_ID, 5, DamageDiceSpecification(1, 8, 3, "piercing"))
    return ControlledCombatDefinition(
        COMBAT_DEFINITION_SCHEMA_VERSION,
        COMBAT_CAMPAIGN_ID,
        COMBAT_SCENE_ID,
        (
            CombatantDefinition(NEKRIA_PARTICIPANT_ID, CombatantRole.PLAYER, 14, 10, 10, 3, (RAPIER_ATTACK_ID,)),
            CombatantDefinition(GOBLIN_PARTICIPANT_ID, CombatantRole.HOSTILE, 15, 7, 7, 2, ()),
        ),
        (rapier,),
    )
