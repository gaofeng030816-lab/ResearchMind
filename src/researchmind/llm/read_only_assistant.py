"""Strict text action protocol for the T5-A read-only assistant."""

from __future__ import annotations

import json
import re

from researchmind.llm.errors import LlmBadResponseError
from researchmind.models import AssistantAction


MAX_ASSISTANT_RESPONSE_CHARS = 8_000
MAX_ASSISTANT_FINAL_ANSWER_CHARS = 6_000
_ACTION_PATTERN = re.compile(
    r"<assistant_action>(?P<payload>.*?)</assistant_action>",
    re.DOTALL,
)
_TOOL_ACTIONS = frozenset(
    {
        "inspect_paper_context",
        "inspect_code_context",
        "inspect_evidence_links",
    }
)


def parse_assistant_action(response: str) -> AssistantAction:
    """Parse exactly one allowlisted action with no arguments."""

    if not isinstance(response, str) or not response.strip():
        raise LlmBadResponseError(
            "The read-only assistant returned an empty action."
        )
    normalized = response.strip()
    if len(normalized) > MAX_ASSISTANT_RESPONSE_CHARS:
        raise LlmBadResponseError(
            "The read-only assistant action exceeded the response limit."
        )
    match = _ACTION_PATTERN.fullmatch(normalized)
    if match is None:
        raise LlmBadResponseError(
            "The read-only assistant returned an invalid action wrapper."
        )
    try:
        payload = json.loads(match.group("payload"))
    except (json.JSONDecodeError, TypeError):
        raise LlmBadResponseError(
            "The read-only assistant returned invalid action JSON."
        ) from None
    if not isinstance(payload, dict):
        raise LlmBadResponseError(
            "The read-only assistant action must be a JSON object."
        )

    action = payload.get("action")
    if action in _TOOL_ACTIONS:
        if set(payload) != {"action"}:
            raise LlmBadResponseError(
                "Read-only assistant tools do not accept arguments."
            )
        return AssistantAction(action=action)
    if action == "final":
        if set(payload) != {"action", "answer"}:
            raise LlmBadResponseError(
                "The final assistant action has invalid fields."
            )
        answer = payload.get("answer")
        if not isinstance(answer, str) or not answer.strip():
            raise LlmBadResponseError(
                "The final assistant answer must not be blank."
            )
        normalized_answer = answer.strip()
        if len(normalized_answer) > MAX_ASSISTANT_FINAL_ANSWER_CHARS:
            raise LlmBadResponseError(
                "The final assistant answer exceeded the response limit."
            )
        return AssistantAction(action="final", answer=normalized_answer)
    raise LlmBadResponseError(
        "The read-only assistant requested an unsupported action."
    )
