from pathlib import Path
from tempfile import TemporaryDirectory

from dungeon_manager.managers.character_manager import CharacterManager
from dungeon_manager.storage.json_storage import JSONStorage

from .character_tools import CharacterTools
from .registry import ToolRegistry


def _exercise_registry(registry):
    created = registry.execute(
        "create_character",
        name="Mira",
        race="Human",
        character_class="Cleric",
    )
    loaded = registry.execute("load_character", name="Mira")

    assert created == {
        "success": True,
        "message": "Created character Mira",
        "character": {
            "name": "Mira",
            "race": "Human",
            "class": "Cleric",
        },
    }
    assert loaded == {
        "success": True,
        "character": {
            "name": "Mira",
            "race": "Human",
            "class": "Cleric",
            "level": 1,
        },
    }

    stored_path = (
        registry.character_tools.manager.storage.base_path
        / "characters"
        / "mira.json"
    )
    assert stored_path.is_file()
    return stored_path


def test_registry_uses_injected_temporary_storage(tmp_path):
    storage = JSONStorage(tmp_path)
    manager = CharacterManager(storage)
    character_tools = CharacterTools(manager)
    registry = ToolRegistry(character_tools)

    stored_path = _exercise_registry(registry)

    assert registry.character_tools is character_tools
    assert character_tools.manager is manager
    assert manager.storage is storage
    assert stored_path.parent.parent == tmp_path


def main():
    with TemporaryDirectory(prefix="dungeon-manager-registry-") as temp_dir:
        temp_path = Path(temp_dir)
        manager = CharacterManager(JSONStorage(temp_path))
        registry = ToolRegistry(CharacterTools(manager))
        stored_path = _exercise_registry(registry)
        assert stored_path.parent.parent == temp_path

    assert not temp_path.exists()


if __name__ == "__main__":
    main()
