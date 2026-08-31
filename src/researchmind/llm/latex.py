"""Parse constrained LaTeX expressions returned by an LLM."""

from __future__ import annotations

import re

from researchmind.llm.errors import LlmBadResponseError


MAX_LATEX_EXPRESSION_CHARS = 4_000
_RESPONSE_PATTERN = re.compile(r"\s*<latex>(?P<body>.*?)</latex>\s*", re.DOTALL)
_FORBIDDEN_COMMAND_PATTERN = re.compile(
    r"\\(?:"
    r"catcode|class|csname|def|documentclass|edef|endcsname|gdef|href|"
    r"html(?:Class|Data|Id|Style)|include|includegraphics|input|newcommand|"
    r"openout|providecommand|read|renewcommand|special|style|url|usepackage|"
    r"write\d*|xdef"
    r")\b",
    re.IGNORECASE,
)
_ENVIRONMENT_PATTERN = re.compile(
    r"\\(?:begin|end)\s*\{\s*([^{}\s]+)\s*\}",
    re.IGNORECASE,
)
_ALLOWED_ENVIRONMENTS = frozenset(
    {
        "aligned",
        "alignedat",
        "array",
        "bmatrix",
        "Bmatrix",
        "cases",
        "gathered",
        "matrix",
        "pmatrix",
        "smallmatrix",
        "split",
        "vmatrix",
        "Vmatrix",
    }
)


def parse_latex_response(response: str) -> str:
    """Return one display-math body while rejecting executable TeX features."""

    if not isinstance(response, str):
        raise LlmBadResponseError("The LLM did not return LaTeX text.")

    match = _RESPONSE_PATTERN.fullmatch(response)
    if match is None:
        raise LlmBadResponseError(
            "The LLM did not return one <latex> expression."
        )

    expression = "\n".join(
        line.rstrip()
        for line in match.group("body").strip().splitlines()
        if line.strip()
    )
    if not expression:
        raise LlmBadResponseError("The LLM returned an empty LaTeX expression.")
    if len(expression) > MAX_LATEX_EXPRESSION_CHARS:
        raise LlmBadResponseError("The LaTeX expression exceeded the size limit.")
    if "\x00" in expression:
        raise LlmBadResponseError("The LaTeX expression contained invalid text.")
    if (
        "$" in expression
        or "\\[" in expression
        or "\\]" in expression
        or "\\(" in expression
        or "\\)" in expression
    ):
        raise LlmBadResponseError(
            "The LaTeX expression must not include display-math delimiters."
        )
    if "```" in expression or "<latex>" in expression or "</latex>" in expression:
        raise LlmBadResponseError(
            "The LaTeX expression contained an unsupported wrapper."
        )
    if _FORBIDDEN_COMMAND_PATTERN.search(expression):
        raise LlmBadResponseError(
            "The LaTeX expression contained a disallowed command."
        )

    environments = {
        match.group(1).casefold()
        for match in _ENVIRONMENT_PATTERN.finditer(expression)
    }
    unsupported = environments - {
        environment.casefold()
        for environment in _ALLOWED_ENVIRONMENTS
    }
    if unsupported:
        raise LlmBadResponseError(
            "The LaTeX expression contained an unsupported environment."
        )
    return expression
