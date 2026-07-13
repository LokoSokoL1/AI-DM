from dungeon_manager.ai.ollama_provider import OllamaProvider
from dungeon_manager.config_loader import load_config
from .tool_agent import ToolAgent


def main():

    config = load_config()

    ai_config = config["ai"]

    provider = OllamaProvider(
        model=ai_config["model"],
        endpoint=ai_config["endpoint"]
    )

    agent = ToolAgent(provider)

    print("Available tools:")
    print(agent.get_available_tools())

    print("\nAI Response:")

    response = agent.ask(
        "Create a human fighter named Arven."
    )

    print(response)


if __name__ == "__main__":
    main()