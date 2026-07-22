import json
from datetime import datetime, timezone

import pytest

from dungeon_manager.storage.json_storage import JSONStorage

from .event_journal_store import EventJournalStore, EventJournalStoreStatus
from dungeon_manager.campaign_runtime import (
    CAMPAIGN_ID,
    FIXTURE_MANIFEST_CATEGORY,
    FIXTURE_MANIFEST_NAME,
    GOBLIN_ID,
    JOURNAL_ID,
    NEKRIA_ID,
    CampaignRuntimeLoadStatus,
    FixtureSetupStatus,
    controlled_fixture_definition,
    initialize_controlled_fixture,
    load_controlled_campaign_runtime,
)


OCCURRED_AT = datetime(2026, 7, 22, 14, 30, 45, 123456, timezone.utc)


def fixture_paths(tmp_path):
    return JSONStorage(tmp_path / "fixture-data"), EventJournalStore(tmp_path / "events.sqlite")


def initialized(tmp_path):
    storage, store = fixture_paths(tmp_path)
    result = initialize_controlled_fixture(storage, store)
    assert result.status is FixtureSetupStatus.SUCCESS
    return storage, store


def test_explicit_fixture_setup_uses_stable_identities_and_empty_exact_journal(tmp_path):
    storage, store = fixture_paths(tmp_path)

    result = initialize_controlled_fixture(storage, store)
    definition = controlled_fixture_definition()

    assert result.status is FixtureSetupStatus.SUCCESS
    assert result.campaign_id == CAMPAIGN_ID
    assert result.journal_id == JOURNAL_ID
    assert definition.current_scene.participant_ids == (NEKRIA_ID, GOBLIN_ID)
    assert store.load().status is EventJournalStoreStatus.SUCCESS
    assert store.load().journal_id == JOURNAL_ID
    assert store.load().tail_sequence == 0
    assert storage.load("characters", NEKRIA_ID)["inventory"] == ["Rapier"]
    assert "definition" not in result.to_dict()
    assert str(tmp_path) not in json.dumps(result.to_dict())


def test_fixture_setup_rejects_existing_or_partial_targets(tmp_path):
    storage, store = initialized(tmp_path)

    assert initialize_controlled_fixture(storage, store).status is FixtureSetupStatus.ALREADY_EXISTS

    other_storage, other_store = fixture_paths(tmp_path / "partial")
    other_storage.save("characters", NEKRIA_ID, {"not": "a fixture"})
    assert initialize_controlled_fixture(other_storage, other_store).status is FixtureSetupStatus.ALREADY_EXISTS
    assert not other_store.path.exists()


def test_loading_requires_existing_complete_fixture_and_never_initializes_storage(tmp_path):
    storage, store = fixture_paths(tmp_path)

    missing_manifest = load_controlled_campaign_runtime(storage, store)

    assert missing_manifest.status is CampaignRuntimeLoadStatus.NOT_FOUND
    assert not store.path.exists()

    storage, store = initialized(tmp_path / "missing-journal")
    store.path.unlink()
    missing_journal = load_controlled_campaign_runtime(storage, store)
    assert missing_journal.status is CampaignRuntimeLoadStatus.NOT_FOUND
    assert not store.path.exists()


def test_loading_validates_manifest_references_versions_and_expected_identities(tmp_path):
    storage, store = initialized(tmp_path)
    raw = storage.load(FIXTURE_MANIFEST_CATEGORY, FIXTURE_MANIFEST_NAME)
    raw["schema_version"] = 99
    storage.save(FIXTURE_MANIFEST_CATEGORY, FIXTURE_MANIFEST_NAME, raw)
    assert load_controlled_campaign_runtime(storage, store).status is CampaignRuntimeLoadStatus.INVALID_DEFINITION

    storage, store = initialized(tmp_path / "identity")
    assert load_controlled_campaign_runtime(storage, store, expected_campaign_id="other").status is CampaignRuntimeLoadStatus.CAMPAIGN_ID_MISMATCH
    assert load_controlled_campaign_runtime(storage, store, expected_journal_id="other-events").status is CampaignRuntimeLoadStatus.JOURNAL_ID_MISMATCH


def test_empty_load_exposes_exact_explicit_precombat_state(tmp_path):
    storage, store = initialized(tmp_path)

    result = load_controlled_campaign_runtime(storage, store)

    assert result.status is CampaignRuntimeLoadStatus.SUCCESS
    runtime = result.runtime
    assert runtime.current_scene_id == "controlled-goblin-encounter"
    assert runtime.participant_ids == (NEKRIA_ID, GOBLIN_ID)
    assert runtime.selected_player_character_id is None
    assert runtime.event_journal.tail_sequence == 0
    assert runtime.state_holder.snapshot.to_dict() == {
        "data": {
            "campaign_id": CAMPAIGN_ID,
            "current_scene_id": "controlled-goblin-encounter",
            "encounter_state": "inactive",
            "journal_id": JOURNAL_ID,
            "scene_participant_ids": [NEKRIA_ID, GOBLIN_ID],
            "selectable_player_character_ids": [NEKRIA_ID],
            "selected_player_character_id": None,
        },
        "last_sequence": 0,
    }


def test_selection_is_durable_projected_idempotent_and_restart_safe(tmp_path):
    storage, store = initialized(tmp_path)
    runtime = load_controlled_campaign_runtime(storage, store).runtime

    selected = runtime.select_player_character(
        NEKRIA_ID,
        command_id="select-nekria-001",
        event_id="selected-nekria-event-001",
        occurred_at=OCCURRED_AT,
    )

    assert selected.published_event_entries[0].event.event_id == "selected-nekria-event-001"
    assert selected.published_event_entries[0].event.occurred_at == OCCURRED_AT
    assert selected.durable_publication.status.value == "committed_synchronized"
    assert runtime.event_journal.tail_sequence == 1
    assert runtime.state_holder.snapshot.last_sequence == 1
    assert runtime.selected_player_character_id == NEKRIA_ID
    durable_before = EventJournalStore(store.path).load().entries

    reopened = load_controlled_campaign_runtime(JSONStorage(storage.base_path), EventJournalStore(store.path))
    assert reopened.status is CampaignRuntimeLoadStatus.SUCCESS
    fresh = reopened.runtime
    assert fresh.selected_player_character_id == NEKRIA_ID
    assert fresh.event_journal.entries == durable_before
    repeated = fresh.select_player_character(
        NEKRIA_ID,
        command_id="select-nekria-002",
        event_id="selected-nekria-event-002",
        occurred_at=OCCURRED_AT,
    )
    assert repeated.published_event_entries == ()
    assert fresh.event_journal.tail_sequence == 1
    assert EventJournalStore(store.path).load().entries == durable_before


def test_invalid_goblin_or_missing_selection_is_eventless_and_recoverable(tmp_path):
    storage, store = initialized(tmp_path)
    runtime = load_controlled_campaign_runtime(storage, store).runtime

    rejected = runtime.select_player_character(GOBLIN_ID, command_id="select-goblin", event_id="goblin-event", occurred_at=OCCURRED_AT)
    missing = runtime.select_player_character("missing", command_id="select-missing", event_id="missing-event", occurred_at=OCCURRED_AT)

    assert rejected.published_event_entries == ()
    assert missing.published_event_entries == ()
    assert runtime.event_journal.tail_sequence == 0
    selected = runtime.select_player_character(NEKRIA_ID, command_id="select-nekria", event_id="nekria-event", occurred_at=OCCURRED_AT)
    assert len(selected.published_event_entries) == 1
    assert runtime.event_journal.tail_sequence == 1


@pytest.mark.parametrize("field", ["participants", "scenes", "selectable_player_character_ids"])
def test_malformed_manifest_does_not_expose_partial_runtime(tmp_path, field):
    storage, store = initialized(tmp_path)
    raw = storage.load(FIXTURE_MANIFEST_CATEGORY, FIXTURE_MANIFEST_NAME)
    raw[field] = []
    storage.save(FIXTURE_MANIFEST_CATEGORY, FIXTURE_MANIFEST_NAME, raw)

    result = load_controlled_campaign_runtime(storage, store)

    assert result.status is CampaignRuntimeLoadStatus.INVALID_DEFINITION
    assert result.runtime is None
    serialized = json.dumps(result.to_dict())
    assert str(tmp_path) not in serialized
    assert "Nekria" not in serialized
