import json
from pathlib import Path


class JSONStorage:
    """
    Handles saving and loading JSON data.
    """

    def __init__(self, base_path="data"):
        self.base_path = Path(base_path)

    def save(self, category: str, name: str, data: dict):
        """
        Save data into a category folder.
        """

        folder = self.base_path / category
        folder.mkdir(parents=True, exist_ok=True)

        file_path = folder / f"{name}.json"

        with open(file_path, "w", encoding="utf-8") as file:
            json.dump(
                data,
                file,
                indent=4,
                ensure_ascii=False
            )

    def load(self, category: str, name: str):
        """
        Load data from a category folder.
        """

        file_path = (
            self.base_path /
            category /
            f"{name}.json"
        )

        if not file_path.exists():
            return None

        with open(file_path, "r", encoding="utf-8") as file:
            return json.load(file)