from dataclasses import dataclass, field
from typing import List


@dataclass
class Item:
    """
    Represents an item in Dungeon Manager.
    """

    name: str
    item_type: str
    description: str = ""

    magical: bool = False
    rarity: str = "Common"

    properties: List[str] = field(default_factory=list)

    def add_property(self, property_text: str):
        self.properties.append(property_text)