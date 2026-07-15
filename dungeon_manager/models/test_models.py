from dataclasses import asdict
from pathlib import Path
from tempfile import TemporaryDirectory

from dungeon_manager.storage.json_storage import JSONStorage

from .campaign import Campaign
from .character import Character
from .item import Item


def _exercise_models(storage):
    sword = Item(
        name="Nightfang",
        item_type="Longsword",
        magical=True,
        rarity="Rare",
        properties=[
            "Deals additional cold damage",
            "Whispers near undead",
        ],
    )

    character = Character(
        name="Nekria",
        race="Unknown",
        character_class="Rogue",
    )
    character.add_item(sword.name)
    character.add_note("Searching for the truth about her past.")

    campaign = Campaign(name="The Lost Mine Adventure")
    campaign.add_character(character.name)
    campaign.add_note("Ancient ruins discovered.")

    stored_models = [
        ("items", "nightfang", sword),
        ("characters", "nekria", character),
        ("campaigns", "lost mine adventure", campaign),
    ]

    for category, name, model in stored_models:
        expected = asdict(model)
        storage.save(category, name, expected)
        assert storage.load(category, name) == expected

    return [
        storage.base_path / category / f"{name}.json"
        for category, name, _ in stored_models
    ]


def test_models_use_temporary_storage(tmp_path):
    storage = JSONStorage(tmp_path)

    stored_paths = _exercise_models(storage)

    assert storage.base_path == tmp_path
    assert all(path.is_file() for path in stored_paths)
    assert all(path.parent.parent == tmp_path for path in stored_paths)


def main():
    with TemporaryDirectory(prefix="dungeon-manager-models-") as temp_dir:
        temp_path = Path(temp_dir)
        stored_paths = _exercise_models(JSONStorage(temp_path))
        assert all(path.is_file() for path in stored_paths)

    assert not temp_path.exists()


if __name__ == "__main__":
    main()
