from pathlib import Path
from tempfile import TemporaryDirectory

from dungeon_manager.managers.character_manager import CharacterManager
from dungeon_manager.storage.json_storage import JSONStorage

from .character_tools import CharacterTools


def _exercise_tools(tools):
    created = tools.create_character("Lyra", "Elf", "Wizard")
    loaded = tools.load_character("Lyra")

    assert created == {
        "success": True,
        "message": "Created character Lyra",
        "character": {
            "name": "Lyra",
            "race": "Elf",
            "class": "Wizard",
        },
    }
    assert loaded == {
        "success": True,
        "character": {
            "name": "Lyra",
            "race": "Elf",
            "class": "Wizard",
            "level": 1,
        },
    }

    stored_path = (
        tools.manager.storage.base_path / "characters" / "lyra.json"
    )
    assert stored_path.is_file()
    return stored_path


def test_tools_use_injected_temporary_storage(tmp_path):
    storage = JSONStorage(tmp_path)
    manager = CharacterManager(storage)
    tools = CharacterTools(manager)

    stored_path = _exercise_tools(tools)

    assert tools.manager is manager
    assert manager.storage is storage
    assert stored_path.parent.parent == tmp_path


def main():
    with TemporaryDirectory(prefix="dungeon-manager-tools-") as temp_dir:
        temp_path = Path(temp_dir)
        manager = CharacterManager(JSONStorage(temp_path))
        stored_path = _exercise_tools(CharacterTools(manager))
        assert stored_path.parent.parent == temp_path

    assert not temp_path.exists()


if __name__ == "__main__":
    main()
