"""Tests for application-level ResearchContext evidence previews."""

from pathlib import Path

import pytest

from researchmind.app.use_cases import (
    create_selection,
    open_pdf,
    preview_explanation_context,
    preview_followup_context,
)
from researchmind.config import Settings
from researchmind.models import Conversation, Message


def test_explanation_preview_exposes_bounded_evidence_without_provider_call(
    structured_pdf: Path,
) -> None:
    settings = Settings(context_token_budget=200, history_token_budget=200)
    opened = open_pdf(structured_pdf, settings=settings)
    selection = create_selection(opened, "Second context block", current_page=1)
    conversation = Conversation(
        document_id=opened.document.id,
        messages=[
            Message(role="user", task="followup", content="Earlier question"),
        ],
    )

    preview = preview_explanation_context(
        selection,
        "contextual",
        document=opened,
        conversation=conversation,
        settings=settings,
    )

    assert preview.document_title == "Structured Research Paper"
    assert preview.page_number == 1
    assert preview.selected_text == "Second context block"
    assert preview.section_heading == "2 Proposed Method"
    assert preview.related_caption == "Figure 3. Update overview"
    assert preview.related_formula == ""
    assert "Second context block" in preview.surrounding_text
    assert preview.user_question == "Explain this selection in its paper context."
    assert preview.history_message_count == 1
    assert preview.request_character_count > len(preview.selected_text)
    assert preview.approximate_request_tokens == (
        preview.request_character_count + 3
    ) // 4


def test_math_preview_includes_formula_text_without_provider_call(
    unicode_math_pdf: Path,
) -> None:
    settings = Settings(context_token_budget=200, history_token_budget=200)
    opened = open_pdf(unicode_math_pdf, settings=settings)
    selection = create_selection(opened, "x^2 + y^2 = z^2", current_page=1)

    preview = preview_explanation_context(
        selection,
        "math",
        document=opened,
        settings=settings,
    )

    assert preview.page_number == 1
    assert "x^2 + y^2 = z^2" in preview.related_formula


def test_followup_preview_rejects_blank_question_and_explanation_mode_is_validated(
    structured_pdf: Path,
) -> None:
    settings = Settings()
    opened = open_pdf(structured_pdf, settings=settings)
    selection = create_selection(opened, "Second context block", current_page=1)
    conversation = Conversation(document_id=opened.document.id)

    with pytest.raises(ValueError, match="must not be blank"):
        preview_followup_context(
            "  ",
            document=opened,
            selection=selection,
            conversation=conversation,
            settings=settings,
        )

    with pytest.raises(ValueError, match="Explain mode"):
        preview_explanation_context(
            selection,
            "unsupported",  # type: ignore[arg-type]
            document=opened,
            conversation=conversation,
            settings=settings,
        )
