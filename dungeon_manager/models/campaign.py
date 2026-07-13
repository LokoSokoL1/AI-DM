from dataclasses import dataclass, field
from typing import List


@dataclass
class Campaign:
    """
    Represents a tabletop campaign.
    """

    name: str

    description: str = ""

    characters: List[str] = field(default_factory=list)

    locations: List[str] = field(default_factory=list)

    notes: List[str] = field(default_factory=list)

    def add_character(self, character_name: str):
        self.characters.append(character_name)

    def add_note(self, note: str):
        self.notes.append(note)
