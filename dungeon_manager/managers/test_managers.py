from .character_manager import CharacterManager


def main():

    manager = CharacterManager()

    character = manager.create_character(
        "Arven",
        "Human",
        "Fighter"
    )

    print("Created:")
    print(character)

    loaded = manager.load_character(
        "Arven"
    )

    print("\nLoaded:")
    print(loaded)


if __name__ == "__main__":
    main()