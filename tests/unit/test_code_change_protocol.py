"""Strict protocol tests for T5-B1 replacement proposals."""

import pytest

from researchmind.llm import LlmBadResponseError
from researchmind.llm.code_change import (
    MAX_CODE_REPLACEMENT_CHARACTERS,
    parse_code_replacement,
)


def test_parse_code_replacement_accepts_one_bounded_wrapper() -> None:
    response = (
        "<replacement>def normalize(value: float) -> float:\n"
        "    return value / 100.0</replacement>"
    )

    assert parse_code_replacement(response) == (
        "def normalize(value: float) -> float:\n"
        "    return value / 100.0"
    )


@pytest.mark.parametrize(
    "response",
    (
        '{"path":"other.py","replacement":"value = 2"}',
        '<replacement path="other.py">value = 2</replacement>',
        "<command>pytest</command>",
        "Before <replacement>value = 2</replacement>",
        (
            "<replacement>value = 2</replacement>"
            "<replacement>other = 3</replacement>"
        ),
        "<replacement>   </replacement>",
        "<replacement>value = 2\x00</replacement>",
    ),
)
def test_parse_code_replacement_rejects_protocol_expansion(
    response: str,
) -> None:
    with pytest.raises(LlmBadResponseError):
        parse_code_replacement(response)


def test_parse_code_replacement_rejects_oversized_output() -> None:
    response = (
        "<replacement>"
        + "x" * (MAX_CODE_REPLACEMENT_CHARACTERS + 1)
        + "</replacement>"
    )

    with pytest.raises(LlmBadResponseError, match="character limit"):
        parse_code_replacement(response)
