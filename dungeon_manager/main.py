from .config_loader import load_config


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

    print("Dungeon Manager ready.")


if __name__ == "__main__":
    main()