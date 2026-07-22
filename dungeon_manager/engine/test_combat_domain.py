from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from dungeon_manager.campaign_runtime import NEKRIA_ID, initialize_controlled_fixture, load_controlled_campaign_runtime
from dungeon_manager.combat_runtime import CombatCompositionStatus, compose_controlled_combat_domain
from dungeon_manager.storage.json_storage import JSONStorage

from .combat_domain import (
    AttackDefinition,
    COMBAT_DEFINITION_SCHEMA_VERSION,
    CombatantDefinition,
    CombatantRole,
    ControlledCombatDefinition,
    DamageDiceSpecification,
    GOBLIN_PARTICIPANT_ID,
    RAPIER_ATTACK_ID,
    controlled_combat_definition,
    initial_combat_seed,
)
from .event_journal_store import EventJournalStore


OCCURRED_AT = datetime(2026, 7, 22, 15, 0, tzinfo=timezone.utc)


def valid_definition():
    return controlled_combat_definition()


def test_controlled_definition_exposes_exact_immutable_combatant_and_rapier_data():
    definition = valid_definition()
    nekria = definition.combatant(NEKRIA_ID)
    goblin = definition.combatant(GOBLIN_PARTICIPANT_ID)
    rapier = definition.attack(RAPIER_ATTACK_ID)

    assert definition.campaign_id == "vertical-slice-v1"
    assert definition.scene_id == "controlled-goblin-encounter"
    assert nekria.role is CombatantRole.PLAYER and (nekria.armor_class, nekria.starting_hit_points, nekria.initiative_modifier) == (14, 10, 3)
    assert goblin.role is CombatantRole.HOSTILE and (goblin.armor_class, goblin.starting_hit_points, goblin.initiative_modifier) == (15, 7, 2)
    assert (rapier.owner_participant_id, rapier.attack_bonus, rapier.damage.to_dict()) == (NEKRIA_ID, 5, {"damage_type_id": "piercing", "dice_count": 1, "modifier": 3, "sides": 8})
    with pytest.raises(FrozenInstanceError):
        nekria.armor_class = 1
    serialized = definition.to_dict()
    serialized["combatants"][0]["armor_class"] = 1
    assert definition.combatant(NEKRIA_ID).armor_class == 14
    assert valid_definition() == definition


@pytest.mark.parametrize(
    "factory",
    [
        lambda: DamageDiceSpecification(True, 8, 3, "piercing"),
        lambda: DamageDiceSpecification(1, 1, 3, "piercing"),
        lambda: DamageDiceSpecification(1, 8, True, "piercing"),
        lambda: AttackDefinition(" ", NEKRIA_ID, 5, DamageDiceSpecification(1, 8, 3, "piercing")),
        lambda: AttackDefinition("bad", NEKRIA_ID, 21, DamageDiceSpecification(1, 8, 3, "piercing")),
        lambda: CombatantDefinition(" ", CombatantRole.PLAYER, 14, 10, 10, 3),
        lambda: CombatantDefinition(NEKRIA_ID, CombatantRole.PLAYER, 0, 10, 10, 3),
        lambda: CombatantDefinition(NEKRIA_ID, CombatantRole.PLAYER, 14, 0, 0, 3),
        lambda: CombatantDefinition(NEKRIA_ID, CombatantRole.PLAYER, 14, 10, 10, True),
    ],
)
def test_combat_member_validation_rejects_invalid_ids_numbers_and_booleans(factory):
    with pytest.raises(ValueError):
        factory()


def test_definition_rejects_duplicate_missing_or_invalid_references_and_schema():
    definition = valid_definition()
    with pytest.raises(ValueError):
        ControlledCombatDefinition(COMBAT_DEFINITION_SCHEMA_VERSION, definition.campaign_id, definition.scene_id, (definition.combatants[0], definition.combatants[0]), definition.attacks)
    with pytest.raises(ValueError):
        ControlledCombatDefinition(COMBAT_DEFINITION_SCHEMA_VERSION, definition.campaign_id, definition.scene_id, definition.combatants, (definition.attacks[0], definition.attacks[0]))
    broken_owner = AttackDefinition("orphan", "missing", 1, DamageDiceSpecification(1, 8, 0, "piercing"))
    with pytest.raises(ValueError):
        ControlledCombatDefinition(COMBAT_DEFINITION_SCHEMA_VERSION, definition.campaign_id, definition.scene_id, definition.combatants, (broken_owner,))
    with pytest.raises(ValueError):
        ControlledCombatDefinition(2, definition.campaign_id, definition.scene_id, definition.combatants, definition.attacks)


def test_initial_seed_is_exact_deterministic_and_explicitly_unstarted():
    definition = valid_definition()
    first = initial_combat_seed(definition)
    second = initial_combat_seed(definition)

    assert first == second
    assert first.to_dict() == {
        "active_participant_id": None,
        "campaign_id": "vertical-slice-v1",
        "defeated_participant_ids": [],
        "initiative_order": [],
        "last_attack_id": None,
        "last_damage": None,
        "participant_hit_points": [{"hit_points": 10, "participant_id": NEKRIA_ID}, {"hit_points": 7, "participant_id": GOBLIN_PARTICIPANT_ID}],
        "round_number": 0,
        "scene_id": "controlled-goblin-encounter",
    }
    assert definition.to_dict() == valid_definition().to_dict()


def loaded_runtime(tmp_path, *, selected):
    storage = JSONStorage(tmp_path / "fixture")
    store = EventJournalStore(tmp_path / "events.sqlite")
    assert initialize_controlled_fixture(storage, store).status.value == "success"
    runtime = load_controlled_campaign_runtime(storage, store).runtime
    if selected:
        runtime.select_player_character(NEKRIA_ID, command_id="select-nekria-combat", event_id="select-nekria-combat-event", occurred_at=OCCURRED_AT)
    return runtime, store


def test_runtime_composition_requires_selected_nekria_then_exposes_complete_static_domain(tmp_path):
    runtime, store = loaded_runtime(tmp_path, selected=False)
    before = store.load().entries

    unselected = compose_controlled_combat_domain(runtime)
    assert unselected.status is CombatCompositionStatus.PLAYER_NOT_SELECTED
    runtime.select_player_character(NEKRIA_ID, command_id="select-nekria-combat", event_id="select-nekria-combat-event", occurred_at=OCCURRED_AT)
    composed = compose_controlled_combat_domain(runtime)

    assert composed.status is CombatCompositionStatus.SUCCESS
    assert composed.domain.definition == valid_definition()
    assert composed.domain.seed.participant_hit_points == ((NEKRIA_ID, 10), (GOBLIN_PARTICIPANT_ID, 7))
    assert store.load().entries != before
    assert store.load().tail_sequence == 1


@pytest.mark.parametrize(
    ("campaign_id", "scene_id", "expected"),
    [
        ("other-campaign", "controlled-goblin-encounter", CombatCompositionStatus.CAMPAIGN_MISMATCH),
        ("vertical-slice-v1", "other-scene", CombatCompositionStatus.SCENE_MISMATCH),
    ],
)
def test_runtime_composition_rejects_campaign_or_scene_mismatch_without_partial_domain(tmp_path, campaign_id, scene_id, expected):
    runtime, _ = loaded_runtime(tmp_path, selected=True)
    base = valid_definition()
    changed = ControlledCombatDefinition(base.schema_version, campaign_id, scene_id, base.combatants, base.attacks)

    result = compose_controlled_combat_domain(runtime, changed)

    assert result.status is expected
    assert result.domain is None


def test_runtime_composition_rejects_broken_rapier_reference_and_later_valid_attempt_succeeds(tmp_path):
    runtime, store = loaded_runtime(tmp_path, selected=True)
    base = valid_definition()
    nekria = base.combatant(NEKRIA_ID)
    broken_nekria = CombatantDefinition(nekria.participant_id, nekria.role, nekria.armor_class, nekria.maximum_hit_points, nekria.starting_hit_points, nekria.initiative_modifier, ())
    broken = ControlledCombatDefinition(base.schema_version, base.campaign_id, base.scene_id, (broken_nekria, base.combatant(GOBLIN_PARTICIPANT_ID)), base.attacks)
    before = store.load().entries

    failed = compose_controlled_combat_domain(runtime, broken)
    succeeded = compose_controlled_combat_domain(runtime)

    assert failed.status is CombatCompositionStatus.REFERENCE_ERROR
    assert failed.domain is None
    assert succeeded.status is CombatCompositionStatus.SUCCESS
    assert store.load().entries == before


def test_composition_result_serialization_is_safe_and_combat_domain_does_not_resolve_dice_or_publish(tmp_path):
    runtime, store = loaded_runtime(tmp_path, selected=True)
    before_entries = store.load().entries
    before_state = runtime.state_holder.snapshot

    result = compose_controlled_combat_domain(runtime)

    assert result.status is CombatCompositionStatus.SUCCESS
    assert result.to_dict() == {"campaign_id": "vertical-slice-v1", "reason_code": None, "scene_id": "controlled-goblin-encounter", "status": "success"}
    assert store.load().entries == before_entries
    assert runtime.state_holder.snapshot is before_state
