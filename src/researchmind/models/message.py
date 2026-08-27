"""Conversation message model."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal


MessageRole = Literal["user", "assistant"]
MessageTask = Literal[
    "translate",
    "explain:concept",
    "explain:math",
    "explain:algorithm",
    "explain:contextual",
    "followup",
]


@dataclass
class Message:
    """One user or assistant message associated with a research task."""

    role: MessageRole
    task: MessageTask
    content: str
    selection_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
