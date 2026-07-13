import requests

from .provider import AIProvider


class OllamaProvider(AIProvider):

    def __init__(self, model: str, endpoint: str):
        self.model = model
        self.endpoint = endpoint

    def generate(self, prompt: str) -> str:

        response = requests.post(
            f"{self.endpoint}/api/generate",
            json={
                "model": self.model,
                "prompt": prompt,
                "stream": False
            },
            timeout=120
        )

        response.raise_for_status()

        data = response.json()

        return data["response"]