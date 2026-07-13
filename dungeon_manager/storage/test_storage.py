from .json_storage import JSONStorage


def main():

    storage = JSONStorage()

    character = {
        "name": "Nekria",
        "class": "Rogue",
        "level": 1,
        "notes": [
            "Searching for her past"
        ]
    }

    storage.save(
        "characters",
        "nekria",
        character
    )

    loaded = storage.load(
        "characters",
        "nekria"
    )

    print(loaded)


if __name__ == "__main__":
    main()