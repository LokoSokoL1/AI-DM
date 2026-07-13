from .item import Item
from .character import Character
from .campaign import Campaign


def main():

    sword = Item(
        name="Nightfang",
        item_type="Longsword",
        magical=True,
        rarity="Rare",
        properties=[
            "Deals additional cold damage",
            "Whispers near undead"
        ]
    )

    nek = Character(
        name="Nekria",
        race="Unknown",
        character_class="Rogue"
    )

    nek.add_item(sword.name)
    nek.add_note("Searching for the truth about her past.")

    campaign = Campaign(
        name="The Lost Mine Adventure"
    )

    campaign.add_character(nek.name)
    campaign.add_note("Ancient ruins discovered.")

    print(sword)
    print(nek)
    print(campaign)


if __name__ == "__main__":
    main()