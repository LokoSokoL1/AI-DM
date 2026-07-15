from pathlib import Path
from tempfile import TemporaryDirectory

from dungeon_manager.storage.json_storage import JSONStorage

from .campaign_manager import CampaignManager


def _exercise_manager(manager):
    campaign = manager.create_campaign(
        "Lost Mine Adventure",
        "A group searches for the lost mine of Phandelver.",
    )
    campaign.add_character("Nekria")
    campaign.add_note("The party discovered mysterious ruins.")
    manager.save_campaign(campaign)

    loaded = manager.load_campaign("Lost Mine Adventure")

    assert loaded == campaign
    stored_path = (
        manager.storage.base_path
        / "campaigns"
        / "lost mine adventure.json"
    )
    assert stored_path.is_file()
    return stored_path


def test_manager_uses_injected_temporary_storage(tmp_path):
    storage = JSONStorage(tmp_path)
    manager = CampaignManager(storage)

    stored_path = _exercise_manager(manager)

    assert manager.storage is storage
    assert stored_path.parent.parent == tmp_path


def main():
    with TemporaryDirectory(prefix="dungeon-manager-manager-") as temp_dir:
        temp_path = Path(temp_dir)
        manager = CampaignManager(JSONStorage(temp_path))
        stored_path = _exercise_manager(manager)
        assert stored_path.parent.parent == temp_path

    assert not temp_path.exists()


if __name__ == "__main__":
    main()
