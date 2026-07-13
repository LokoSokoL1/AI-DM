import json
from pathlib import Path


CONFIG_PATH = Path("config/config.json")


def load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


if __name__ == "__main__":
    config = load_config()
    print(config)