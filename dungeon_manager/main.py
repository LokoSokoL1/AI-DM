from .config_loader import load_config
from .ai.manager import AIManager


def main():
    print("Starting Dungeon Manager...")

    config = load_config()

    print(
        f"Project: {config['project']['name']} "
        f"v{config['project']['version']}"
    )

    print(
        f"AI Provider: {config['ai']['provider']}"
    )

    print(
        f"AI Model: {config['ai']['model']}"
    )

    ai = AIManager(config)

    print("Sending test prompt...")

    response = ai.generate(
        "Introduce yourself briefly as an AI assistant."
    )

    print("\nAI Response:")
    print(response)

    print("\nDungeon Manager ready.")


if __name__ == "__main__":
    main()