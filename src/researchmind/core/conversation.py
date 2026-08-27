"""Pure conversation-history budgeting rules."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace

from researchmind.models import Message


APPROXIMATE_CHARS_PER_TOKEN = 4


def trim_conversation_history(
    messages: Sequence[Message],
    *,
    token_budget: int,
) -> list[Message]:
    """Keep the newest conversation messages within an approximate token budget.

    V1 deliberately avoids adding a model-specific tokenizer. Four characters per
    token is a deterministic approximation for request budgeting.
    """

    _validate_token_budget(token_budget)
    remaining_chars = token_budget * APPROXIMATE_CHARS_PER_TOKEN
    kept_newest_first: list[Message] = []

    for message in reversed(messages):
        content = message.content
        if len(content) <= remaining_chars:
            kept_newest_first.append(message)
            remaining_chars -= len(content)
            continue

        if not kept_newest_first and remaining_chars > 0:
            kept_newest_first.append(
                replace(message, content=content[:remaining_chars])
            )
        break

    return list(reversed(kept_newest_first))


def _validate_token_budget(token_budget: int) -> None:
    if isinstance(token_budget, bool) or not isinstance(token_budget, int):
        raise ValueError("Token budget must be a positive integer.")
    if token_budget <= 0:
        raise ValueError("Token budget must be a positive integer.")
