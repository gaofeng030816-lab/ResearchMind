"""Provider-neutral translation contract."""

from typing import Protocol


class TranslationProvider(Protocol):
    """Interface implemented by ResearchMind translation providers."""

    def translate(self, text: str, target_language: str) -> str:
        """Translate text into the requested target language."""
