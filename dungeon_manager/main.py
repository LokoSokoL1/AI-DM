from .config_loader import load_config
from .ai.manager import AIManager
from .logger import setup_logger


def main():

    logger = setup_logger()

    logger.info("Starting Dungeon Manager...")

    config = load_config()

    logger.info(
        f"Project: {config['project']['name']} "
        f"v{config['project']['version']}"
    )

    logger.info(
        f"AI Provider: {config['ai']['provider']}"
    )

    logger.info(
        f"AI Model: {config['ai']['model']}"
    )

    ai = AIManager(config)

    logger.info("Sending test prompt...")

    response = ai.generate(
        "Introduce yourself briefly as an AI assistant."
    )

    logger.info("AI Response received:")
    print(response)

    logger.info("Dungeon Manager ready.")


if __name__ == "__main__":
    main()