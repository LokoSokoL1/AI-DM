from .ollama_provider import OllamaProvider


class AIManager:

    def __init__(self, config: dict):
        self.config = config
        self.provider = self._create_provider()

    def _create_provider(self):

        provider = self.config["ai"]["provider"]

        if provider == "ollama":
            return OllamaProvider(
                model=self.config["ai"]["model"],
                endpoint=self.config["ai"]["endpoint"]
            )

        raise ValueError(
            f"Unsupported AI provider: {provider}"
        )

    def generate(self, prompt: str) -> str:
        return self.provider.generate(prompt)