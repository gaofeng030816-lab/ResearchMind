"""LLM provider contract and provider-neutral chat messages."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol


ChatRole = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class ChatMessage:
    """One provider-neutral message sent to a configured language model."""

    role: ChatRole
    content: str


class LlmProvider(Protocol):
    """Interface implemented by every ResearchMind language-model provider."""

    def complete(
        self,
        messages: list[ChatMessage],
        **kwargs: object,
    ) -> str:
        """Send messages and return one assistant text response."""
