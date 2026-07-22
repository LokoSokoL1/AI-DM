from datetime import datetime, timezone

import pytest

from dungeon_manager.campaign_runtime import NEKRIA_ID, initialize_controlled_fixture, load_controlled_campaign_runtime
from dungeon_manager.combat_runtime import compose_controlled_combat_domain
from dungeon_manager.controlled_round_runtime import ControlledRoundRuntime, ControlledRoundRuntimeStatus
from dungeon_manager.storage.json_storage import JSONStorage

from ._json import thaw_json_value
from .combat_domain import controlled_combat_definition
from .controlled_round import initiative_order, resolve_controlled_round, validate_controlled_round_payload
from .dice import DiceRoll, DiceRollMode, DiceRollProvenance, DiceRollRequest, SequenceFaceSource
from .event_journal_store import EventJournalStore


TIME = datetime(2026, 7, 22, 16, 0, tzinfo=timezone.utc)


def values(**updates):
    result = {
        "command_id": "round-command-001",
        "event_id": "round-event-001",
        "occurred_at": TIME,
        "mode": DiceRollMode.MANUAL,
        "roll_ids": {"nekria_initiative": "nekria-init-001", "goblin_initiative": "goblin-init-001", "attack": "attack-001", "damage": "damage-001"},
        "manual_faces": {"nekria_initiative": None, "goblin_initiative": None, "attack": None, "damage": None},
        "automatic_source": None,
    }
    result.update(updates)
    return result


def round_runtime(tmp_path):
    storage = JSONStorage(tmp_path / "fixture")
    store = EventJournalStore(tmp_path / "events.sqlite")
    assert initialize_controlled_fixture(storage, store).status.value == "success"
    runtime = load_controlled_campaign_runtime(storage, store).runtime
    runtime.select_player_character(NEKRIA_ID, command_id="select-nekria-round", event_id="selected-nekria-round", occurred_at=TIME)
    composition = compose_controlled_combat_domain(runtime)
    assert composition.status.value == "success"
    return ControlledRoundRuntime(runtime, composition.domain), runtime, store, storage


def resolve(controlled, arguments):
    return controlled.resolve(**arguments)


def test_manual_stages_are_ordered_eventless_and_never_consume_randomness(tmp_path):
    controlled, runtime, store, _ = round_runtime(tmp_path)
    before = store.load().entries
    source = SequenceFaceSource([20, 20, 20, 8])

    first = resolve(controlled, values(automatic_source=source))
    second = resolve(controlled, values(command_id="round-command-002", manual_faces={"nekria_initiative": 10, "goblin_initiative": None, "attack": None, "damage": None}, automatic_source=source))
    third = resolve(controlled, values(command_id="round-command-003", manual_faces={"nekria_initiative": 10, "goblin_initiative": 5, "attack": None, "damage": None}, automatic_source=source))
    fourth = resolve(controlled, values(command_id="round-command-004", manual_faces={"nekria_initiative": 10, "goblin_initiative": 5, "attack": 10, "damage": None}, automatic_source=source))

    assert [item.status for item in (first, second, third, fourth)] == [ControlledRoundRuntimeStatus.INITIATIVE_INPUT_REQUIRED, ControlledRoundRuntimeStatus.INITIATIVE_INPUT_REQUIRED, ControlledRoundRuntimeStatus.ATTACK_INPUT_REQUIRED, ControlledRoundRuntimeStatus.DAMAGE_INPUT_REQUIRED]
    assert first.details["roll_id"] == "nekria-init-001"
    assert second.details["roll_id"] == "goblin-init-001"
    assert third.details["roll_id"] == "attack-001"
    assert fourth.details["roll_id"] == "damage-001"
    assert source.calls == []
    assert store.load().entries == before
    assert "controlled_combat" not in runtime.state_holder.snapshot.data


def test_manual_nekria_first_miss_publishes_one_complete_round_and_advances_to_goblin(tmp_path):
    controlled, runtime, store, _ = round_runtime(tmp_path)
    arguments = values(manual_faces={"nekria_initiative": 12, "goblin_initiative": 4, "attack": 9, "damage": None})

    result = resolve(controlled, arguments)

    assert result.status is ControlledRoundRuntimeStatus.SUCCESS
    assert store.load().tail_sequence == runtime.event_journal.tail_sequence == runtime.state_holder.snapshot.last_sequence == 2
    event = store.load().entries[-1].event
    payload = event.payload
    assert event.event_id == "round-event-001" and event.originating_command_id == "round-command-001" and event.occurred_at == TIME
    assert payload["initiative"]["order"] == ("nekria", "goblin-1")
    assert payload["attack"]["hit"] is False and payload["attack"]["damage_roll"] is None
    assert payload["goblin"] == {"applied_damage": 0, "defeated": False, "previous_hit_points": 7, "resulting_hit_points": 7, "rolled_damage": 0}
    assert payload["final"] == {"active_participant_id": "goblin-1", "encounter_status": "active", "round_number": 1}
    assert runtime.state_holder.snapshot.data["controlled_combat"] == payload


def test_automatic_goblin_first_hit_consumes_faces_in_stage_order_and_wraps_round(tmp_path):
    controlled, runtime, store, _ = round_runtime(tmp_path)
    source = SequenceFaceSource([3, 18, 10, 2])
    result = resolve(controlled, values(mode=DiceRollMode.AUTOMATIC, automatic_source=source))

    assert result.status is ControlledRoundRuntimeStatus.SUCCESS
    assert source.calls == [(1, 20), (1, 20), (1, 20), (1, 8)]
    payload = store.load().entries[-1].event.payload
    assert payload["initiative"]["order"] == ("goblin-1", "nekria")
    assert payload["no_action"] == {"occurred": True, "reason_code": "controlled_slice_no_goblin_behavior"}
    assert payload["attack"]["hit"] is True
    assert payload["goblin"]["resulting_hit_points"] == 2
    assert payload["final"] == {"active_participant_id": "goblin-1", "encounter_status": "active", "round_number": 2}
    assert runtime.state_holder.snapshot.data["controlled_combat"]["final"]["round_number"] == 2


def test_equal_initiative_total_uses_modifier_and_synthetic_equal_modifier_uses_stable_id():
    def entry(participant_id, modifier, natural):
        request = DiceRollRequest(participant_id + "-roll", 1, 20, modifier)
        roll = DiceRoll(request, DiceRollMode.MANUAL, DiceRollProvenance.HUMAN_MANUAL, (natural,), natural, natural + modifier)
        from .controlled_round import InitiativeEntry
        return InitiativeEntry(participant_id, modifier, roll)

    assert initiative_order((entry("nekria", 3, 7), entry("goblin-1", 2, 8))) == ("nekria", "goblin-1")
    assert initiative_order((entry("nekria", 2, 8), entry("goblin-1", 2, 8))) == ("goblin-1", "nekria")


def test_persisted_roll_provenance_and_turn_semantics_are_validated_without_rerolling():
    resolution = resolve_controlled_round(
        controlled_combat_definition(),
        mode=DiceRollMode.MANUAL,
        roll_ids=values()["roll_ids"],
        manual_faces={"nekria_initiative": 12, "goblin_initiative": 4, "attack": 9, "damage": None},
        automatic_source=None,
    )
    payload = thaw_json_value(resolution.payload)
    assert validate_controlled_round_payload(payload) == payload
    payload["attack"]["attack_roll"]["provenance"] = "engine_automatic"
    with pytest.raises(ValueError, match="persisted dice roll"):
        validate_controlled_round_payload(payload)


def test_lethal_attack_completes_encounter_without_next_turn_and_second_attempt_is_eventless(tmp_path):
    controlled, runtime, store, _ = round_runtime(tmp_path)
    arguments = values(manual_faces={"nekria_initiative": 20, "goblin_initiative": 1, "attack": 20, "damage": 8})

    resolved = resolve(controlled, arguments)
    repeated = resolve(controlled, values(command_id="round-command-002", event_id="round-event-002", manual_faces=arguments["manual_faces"]))

    assert resolved.status is ControlledRoundRuntimeStatus.SUCCESS
    payload = store.load().entries[-1].event.payload
    assert payload["goblin"]["resulting_hit_points"] == 0 and payload["goblin"]["defeated"] is True
    assert payload["final"] == {"active_participant_id": None, "encounter_status": "completed", "round_number": 1}
    assert repeated.status is ControlledRoundRuntimeStatus.ALREADY_RESOLVED
    assert store.load().tail_sequence == 2
    assert runtime.state_holder.snapshot.data["controlled_combat"]["goblin"]["defeated"] is True


def test_dice_failure_or_invalid_face_never_publishes_and_later_valid_submission_succeeds(tmp_path):
    controlled, runtime, store, _ = round_runtime(tmp_path)
    invalid = resolve(controlled, values(manual_faces={"nekria_initiative": 0, "goblin_initiative": None, "attack": None, "damage": None}))
    source_failure = resolve(controlled, values(command_id="round-command-002", mode=DiceRollMode.AUTOMATIC, automatic_source=SequenceFaceSource([10])))

    assert invalid.status is ControlledRoundRuntimeStatus.INVALID_INPUT
    assert source_failure.status is ControlledRoundRuntimeStatus.DICE_FAILURE
    assert store.load().tail_sequence == 1
    assert "controlled_combat" not in runtime.state_holder.snapshot.data
    valid = resolve(controlled, values(command_id="round-command-003", event_id="round-event-003", manual_faces={"nekria_initiative": 12, "goblin_initiative": 4, "attack": 9, "damage": None}))
    assert valid.status is ControlledRoundRuntimeStatus.SUCCESS


def test_restart_hydrates_exact_round_without_reroll_or_append_and_rejects_new_round(tmp_path):
    controlled, runtime, store, storage = round_runtime(tmp_path)
    resolve(controlled, values(manual_faces={"nekria_initiative": 12, "goblin_initiative": 4, "attack": 10, "damage": 4}))
    before = store.load().entries

    fresh_runtime = load_controlled_campaign_runtime(JSONStorage(storage.base_path), EventJournalStore(store.path)).runtime
    fresh_domain = compose_controlled_combat_domain(fresh_runtime).domain
    fresh_controlled = ControlledRoundRuntime(fresh_runtime, fresh_domain)
    repeated = resolve(fresh_controlled, values(command_id="restart-round-command", event_id="restart-round-event", manual_faces={"nekria_initiative": 12, "goblin_initiative": 4, "attack": 10, "damage": 4}))

    assert fresh_runtime.event_journal.entries == before
    assert fresh_runtime.state_holder.snapshot.data["controlled_combat"] == runtime.state_holder.snapshot.data["controlled_combat"]
    assert repeated.status is ControlledRoundRuntimeStatus.ALREADY_RESOLVED
    assert EventJournalStore(store.path).load().entries == before


def test_goblin_first_defeating_attack_retains_round_one_and_has_no_next_turn(tmp_path):
    controlled, _, store, _ = round_runtime(tmp_path)
    resolved = resolve(controlled, values(manual_faces={"nekria_initiative": 1, "goblin_initiative": 20, "attack": 20, "damage": 8}))

    assert resolved.status is ControlledRoundRuntimeStatus.SUCCESS
    payload = store.load().entries[-1].event.payload
    assert payload["initiative"]["order"] == ("goblin-1", "nekria")
    assert payload["goblin"]["defeated"] is True
    assert payload["final"] == {"active_participant_id": None, "encounter_status": "completed", "round_number": 1}
