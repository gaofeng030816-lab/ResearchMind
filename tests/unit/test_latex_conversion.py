"""Tests for grounded, constrained LaTeX conversion."""

from pathlib import Path

import pytest

from researchmind.app.use_cases import (
    convert_selection_to_latex,
    open_pdf,
    preview_latex_context,
)
from researchmind.config import Settings
from researchmind.llm import LlmBadResponseError
from researchmind.llm.latex import parse_latex_response
from researchmind.llm.prompts import build_latex_prompt
from researchmind.models import Conversation, ReadingSelection, ResearchContext


def test_latex_prompt_is_grounded_and_requires_one_expression() -> None:
    messages = build_latex_prompt(_research_context())

    assert [message.role for message in messages] == ["system", "user"]
    assert "selected mathematical material" in messages[0].content
    assert "<latex>" in messages[0].content
    assert "without display-math delimiters" in messages[0].content
    assert "<paper_context>" in messages[1].content
    assert "x / y" in messages[1].content
    assert "Nearby definition of x and y." in messages[1].content


def test_parse_latex_response_returns_formula_body() -> None:
    assert parse_latex_response(
        r"<latex>\frac{x_1}{y^2}</latex>"
    ) == r"\frac{x_1}{y^2}"


@pytest.mark.parametrize(
    "response",
    (
        "Here is the result: x + y",
        "<latex></latex>",
        "<latex>$$x + y$$</latex>",
        "<latex>$x + y$</latex>",
        r"<latex>\(x + y\)</latex>",
        "<latex>```latex\nx + y\n```</latex>",
        "<latex>x</latex><latex>y</latex>",
        r"<latex>\input{secrets}</latex>",
        r"<latex>\href{https://example.com}{x}</latex>",
        r"<latex>\begin{document}x\end{document}</latex>",
        "<latex>" + "x" * 4001 + "</latex>",
    ),
)
def test_parse_latex_response_rejects_malformed_or_unsafe_output(
    response: str,
) -> None:
    with pytest.raises(LlmBadResponseError):
        parse_latex_response(response)


def test_convert_selection_to_latex_uses_fresh_research_context(
    single_page_pdf: Path,
    fake_llm_provider: object,
) -> None:
    fake_llm_provider.responses = [r"<latex>h_{t+1}=h_t+f(h_t,\theta_t)</latex>"]
    opened = open_pdf(single_page_pdf, settings=Settings())
    selection = ReadingSelection(
        text="h t+1 = h t + f(h t, theta t)",
        locator={"page_number": 1, "block_index": 1},
    )
    conversation = Conversation(document_id=opened.document.id)
    settings = Settings(context_token_budget=200, history_token_budget=200)

    preview = preview_latex_context(
        selection,
        document=opened,
        conversation=conversation,
        settings=settings,
    )
    message = convert_selection_to_latex(
        selection,
        document=opened,
        conversation=conversation,
        llm_provider=fake_llm_provider,
        settings=settings,
    )

    assert message.task == "convert:latex"
    assert message.content == r"h_{t+1}=h_t+f(h_t,\theta_t)"
    request = fake_llm_provider.calls[0][0]
    assert "<paper_context>" in request[1].content
    assert "h t+1 = h t + f(h t, theta t)" in request[1].content
    assert preview.request_character_count == sum(
        len(item.content) for item in request
    )


def test_parse_latex_response_removes_blank_math_lines() -> None:
    assert parse_latex_response(
        "<latex>\\begin{aligned}\nx &= y\n\n"
        "y &= z\n\\end{aligned}</latex>"
    ) == "\\begin{aligned}\nx &= y\ny &= z\n\\end{aligned}"


def _research_context() -> ResearchContext:
    return ResearchContext(
        selected_text="x / y",
        surrounding_text="Nearby definition of x and y.",
        document_id="document-123",
        document_title="Optimization Paper",
        author="Ada Researcher",
        source="pdf",
        user_question="Convert the selected formula to LaTeX.",
        page_number=3,
    )
