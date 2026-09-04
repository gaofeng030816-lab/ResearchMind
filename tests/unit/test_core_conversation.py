"""Tests for pure conversation-history budgeting."""

import pytest

from researchmind.core.conversation import trim_conversation_history
from researchmind.models import Message


def test_history_budget_keeps_newest_complete_messages_in_order() -> None:
    messages = [
        Message(role="user", task="followup", content="older"),
        Message(role="assistant", task="followup", content="middle"),
        Message(role="user", task="followup", content="newest"),
    ]

    trimmed = trim_conversation_history(messages, token_budget=2)

    assert [message.content for message in trimmed] == ["newest"]


def test_single_oversized_newest_message_is_truncated_without_mutating_input() -> None:
    message = Message(role="assistant", task="followup", content="abcdefghijklmnop")

    trimmed = trim_conversation_history([message], token_budget=2)

    assert trimmed[0].content == "abcdefgh"
    assert message.content == "abcdefghijklmnop"


@pytest.mark.parametrize("budget", (0, -1, True, 1.5))
def test_history_budget_must_be_a_positive_integer(budget: object) -> None:
    with pytest.raises(ValueError, match="positive integer"):
        trim_conversation_history([], token_budget=budget)  # type: ignore[arg-type]
