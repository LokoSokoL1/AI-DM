from dataclasses import dataclass, field
from typing import List


@dataclass
class Character:
    """
    Represents a player character or NPC.
    """

    name: str
    race: str = ""
    character_class: str = ""

    level: int = 1

    description: str = ""

    inventory: List[str] = field(default_factory=list)

    notes: List[str] = field(default_factory=list)

    def add_item(self, item_name: str):
        self.inventory.append(item_name)

    def add_note(self, note: str):
        self.notes.append(note)