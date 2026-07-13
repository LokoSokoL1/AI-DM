from abc import ABC, abstractmethod


class AIProvider(ABC):
    """
    Base interface for AI providers.

    Any AI backend must implement this interface.
    """

    @abstractmethod
    def generate(self, prompt: str) -> str:
        """
        Send a prompt and return the generated response.
        """
        pass