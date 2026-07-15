from dungeon_manager.managers.character_manager import CharacterManager
from dungeon_manager.tools.tool_base import BaseTool
from dungeon_manager.tools.tool_spec import ToolSpec


_CREATE_CHARACTER_SPEC = ToolSpec(
    name="create_character",
    description="Create and persist a new player character.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name of the character to create.",
                "examples": ["Arven"],
            },
            "race": {
                "type": "string",
                "description": "Race or ancestry of the character.",
                "default": "",
                "examples": ["Human"],
            },
            "character_class": {
                "type": "string",
                "description": "Class of the character.",
                "default": "",
                "examples": ["Fighter"],
            },
        },
        "required": ["name"],
        "additionalProperties": False,
    },
)

_LOAD_CHARACTER_SPEC = ToolSpec(
    name="load_character",
    description="Load a previously stored character by name.",
    input_schema={
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Name of the character to load.",
                "examples": ["Arven"],
            },
        },
        "required": ["name"],
        "additionalProperties": False,
    },
)


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

    def get_tool_specs(self):
        return (
            _CREATE_CHARACTER_SPEC,
            _LOAD_CHARACTER_SPEC,
        )

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
