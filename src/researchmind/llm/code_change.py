"""Strict response protocol for one bounded T5-B1 code replacement."""

from __future__ import annotations

import re

from researchmind.llm.errors import LlmBadResponseError


MAX_CODE_REPLACEMENT_CHARACTERS = 20_000
_MAX_RESPONSE_CHARACTERS = MAX_CODE_REPLACEMENT_CHARACTERS + 64
_REPLACEMENT_PATTERN = re.compile(
    r"\A<replacement>(?P<replacement>[\s\S]*?)</replacement>\Z"
)


def parse_code_replacement(response: str) -> str:
    """Return only the replacement body from one exact, bounded wrapper."""

    normalized = response.strip()
    if not normalized:
        raise LlmBadResponseError("The code-change proposal was empty.")
    if len(normalized) > _MAX_RESPONSE_CHARACTERS:
        raise LlmBadResponseError(
            "The code-change proposal exceeded the response character limit."
        )
    match = _REPLACEMENT_PATTERN.fullmatch(normalized)
    if match is None:
        raise LlmBadResponseError(
            "The code-change proposal must contain exactly one replacement wrapper."
        )
    replacement = match.group("replacement")
    if "<replacement>" in replacement or "</replacement>" in replacement:
        raise LlmBadResponseError(
            "The code-change proposal contained more than one action."
        )
    if not replacement.strip():
        raise LlmBadResponseError("The code replacement must not be blank.")
    if len(replacement) > MAX_CODE_REPLACEMENT_CHARACTERS:
        raise LlmBadResponseError(
            "The code replacement exceeded the 20,000-character limit."
        )
    if "\x00" in replacement:
        raise LlmBadResponseError(
            "The code replacement contains an unsupported null character."
        )
    return replacement
