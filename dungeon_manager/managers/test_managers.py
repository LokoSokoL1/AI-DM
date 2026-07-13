from .character_manager import CharacterManager
from .item_manager import ItemManager


def main():

    item_manager = ItemManager()

    sword = item_manager.create_item(
        "Nightfang",
        "Longsword",
        "A blade forged in forgotten darkness.",
        magical=True,
        rarity="Rare",
        properties=[
            "Deals cold damage",
            "Whispers near undead"
        ]
    )

    print("Created item:")
    print(sword)

    loaded = item_manager.load_item(
        "Nightfang"
    )

    print("\nLoaded item:")
    print(loaded)


if __name__ == "__main__":
    main()