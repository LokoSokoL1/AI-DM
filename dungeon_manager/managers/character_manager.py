from dungeon_manager.models.character import Character
from dungeon_manager.storage.json_storage import JSONStorage


class CharacterManager:
    """
    Handles character creation and storage.
    """

    def __init__(self, storage=None):
        self.storage = storage if storage is not None else JSONStorage()

    def create_character(
        self,
        name: str,
        race: str = "",
        character_class: str = ""
    ):

        character = Character(
            name=name,
            race=race,
            character_class=character_class
        )

        self.save_character(character)

        return character

    def save_character(self, character: Character):

        data = {
            "name": character.name,
            "race": character.race,
            "character_class": character.character_class,
            "level": character.level,
            "description": character.description,
            "inventory": character.inventory,
            "notes": character.notes
        }

        self.storage.save(
            "characters",
            character.name.lower(),
            data
        )

    def load_character(self, name: str):

        data = self.storage.load(
            "characters",
            name.lower()
        )

        if data is None:
            return None

        return Character(
            name=data["name"],
            race=data["race"],
            character_class=data["character_class"],
            level=data["level"],
            description=data["description"],
            inventory=data["inventory"],
            notes=data["notes"]
        )
