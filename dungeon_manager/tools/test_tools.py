from .character_tools import CharacterTools


def main():

    tools = CharacterTools()

    result = tools.create_character(
        "Lyra",
        "Elf",
        "Wizard"
    )

    print(result)

    loaded = tools.load_character(
        "Lyra"
    )

    print(loaded)


if __name__ == "__main__":
    main()