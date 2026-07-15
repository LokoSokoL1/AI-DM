from dungeon_manager.managers.character_manager import CharacterManager
from dungeon_manager.tools.tool_base import BaseTool


class CharacterTools(BaseTool):
    """
    Tools available for AI character management.
    """

    def __init__(self, manager=None):
        self.manager = manager if manager is not None else CharacterManager()

    def get_tools(self):
        return {
            "create_character": self.create_character,
            "load_character": self.load_character
        }

    def create_character(
        self,
        name: str,
        race: str = "",
        character_class: str = ""
    ):
        """
        Creates and saves a character.
        """

        character = self.manager.create_character(
            name,
            race,
            character_class
        )

        return {
            "success": True,
            "message": f"Created character {character.name}",
            "character": {
                "name": character.name,
                "race": character.race,
                "class": character.character_class
            }
        }

    def load_character(self, name: str):
        """
        Loads an existing character.
        """

        character = self.manager.load_character(name)

        if character is None:
            return {
                "success": False,
                "message": "Character not found"
            }

        return {
            "success": True,
            "character": {
                "name": character.name,
                "race": character.race,
                "class": character.character_class,
                "level": character.level
            }
        }
