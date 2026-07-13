from .registry import ToolRegistry


def main():

    registry = ToolRegistry()

    result = registry.execute(
        "create_character",
        name="Mira",
        race="Human",
        character_class="Cleric"
    )

    print(result)


if __name__ == "__main__":
    main()