from pathlib import Path
from tempfile import TemporaryDirectory

from .json_storage import JSONStorage


def _exercise_storage(storage):
    character = {
        "name": "Nekria",
        "class": "Rogue",
        "level": 1,
        "notes": ["Searching for her past"],
    }

    storage.save("characters", "nekria", character)

    assert storage.load("characters", "nekria") == character

    stored_path = storage.base_path / "characters" / "nekria.json"
    assert stored_path.is_file()
    return stored_path


def test_storage_uses_temporary_directory(tmp_path):
    storage = JSONStorage(tmp_path)

    stored_path = _exercise_storage(storage)

    assert storage.base_path == tmp_path
    assert stored_path.parent.parent == tmp_path


def main():
    with TemporaryDirectory(prefix="dungeon-manager-storage-") as temp_dir:
        temp_path = Path(temp_dir)
        stored_path = _exercise_storage(JSONStorage(temp_path))
        assert stored_path.parent.parent == temp_path

    assert not temp_path.exists()


if __name__ == "__main__":
    main()
