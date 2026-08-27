"""Application API coordinating ResearchMind domain and infrastructure modules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from researchmind.config import Settings, load_settings
from researchmind.core import build_research_context, locate_selection
from researchmind.llm import (
    LlmProvider,
    build_algorithm_prompt,
    build_concept_prompt,
    build_contextual_prompt,
    build_followup_prompt,
    build_math_prompt,
    create_llm_provider,
)
from researchmind.models import Conversation, Message, Page, ReadingSelection
from researchmind.pdf import (
    OpenedDocument,
    TextMatch,
    extract_page,
    open_pdf as pdf_open_pdf,
    render_page_image,
    search_text as pdf_search_text,
)
from researchmind.translation import (
    LlmTranslationProvider,
    TranslationProvider,
    translate_text,
)


ExplainMode = Literal["concept", "math", "algorithm", "contextual"]


@dataclass(frozen=True)
class PageView:
    """One rendered page plus its extracted, selectable text."""

    page: Page
    image_png: bytes
    zoom: float


_EXPLANATION_BUILDERS = {
    "concept": build_concept_prompt,
    "math": build_math_prompt,
    "algorithm": build_algorithm_prompt,
    "contextual": build_contextual_prompt,
}

_DEFAULT_QUESTIONS = {
    "concept": "Explain this concept.",
    "math": "Explain this mathematical material.",
    "algorithm": "Explain this algorithm.",
    "contextual": "Explain this selection in its paper context.",
}


def open_pdf(path: Path, *, settings: Settings | None = None) -> OpenedDocument:
    """Open and extract a local PDF within the configured size limit."""

    resolved_settings = settings or load_settings()
    return pdf_open_pdf(path, max_size_bytes=resolved_settings.pdf_max_size_bytes)


def get_page_view(
    document: OpenedDocument,
    page_number: int,
    *,
    zoom: float = 1.0,
) -> PageView:
    """Return the page image and extracted text used by the reader view."""

    return PageView(
        page=extract_page(document, page_number),
        image_png=render_page_image(document, page_number, zoom=zoom),
        zoom=float(zoom),
    )


def search_text(document: OpenedDocument, query: str) -> list[TextMatch]:
    """Search extracted PDF text without exposing PDF-library objects."""

    return pdf_search_text(document, query)


def create_selection(
    document: OpenedDocument,
    text: str,
    current_page: int | None,
) -> ReadingSelection:
    """Create a selection, locating it when extracted text permits."""

    return locate_selection(text, document.pages, current_page=current_page)


def translate_selection(
    selection: ReadingSelection,
    *,
    translation_provider: TranslationProvider | None = None,
    settings: Settings | None = None,
) -> Message:
    """Translate a selection through the independent translation capability."""

    resolved_settings = settings or load_settings()
    provider = translation_provider
    if provider is None:
        provider = LlmTranslationProvider(create_llm_provider(resolved_settings))
    translated = translate_text(
        selection.text,
        resolved_settings.target_language,
        provider,
    )
    return Message(role="assistant", task="translate", content=translated)


def explain_selection(
    selection: ReadingSelection,
    mode: ExplainMode,
    *,
    document: OpenedDocument,
    conversation: Conversation | None = None,
    question: str | None = None,
    llm_provider: LlmProvider | None = None,
    settings: Settings | None = None,
) -> Message:
    """Explain the selection using a freshly assembled ResearchContext."""

    if mode not in _EXPLANATION_BUILDERS:
        allowed = ", ".join(_EXPLANATION_BUILDERS)
        raise ValueError(f"Explain mode must be one of: {allowed}.")

    resolved_settings = settings or load_settings()
    provider = llm_provider or create_llm_provider(resolved_settings)
    context = build_research_context(
        selection,
        document.document,
        document.pages,
        user_question=question or _DEFAULT_QUESTIONS[mode],
        conversation=conversation,
        context_token_budget=resolved_settings.context_token_budget,
        history_token_budget=resolved_settings.history_token_budget,
    )
    response = provider.complete(_EXPLANATION_BUILDERS[mode](context))
    return Message(
        role="assistant",
        task=f"explain:{mode}",
        content=response,
    )


def ask_followup(
    question: str,
    *,
    document: OpenedDocument,
    selection: ReadingSelection,
    conversation: Conversation,
    llm_provider: LlmProvider | None = None,
    settings: Settings | None = None,
) -> Message:
    """Answer a follow-up from fresh selection, paper, and history context."""

    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("Follow-up question must not be blank.")

    resolved_settings = settings or load_settings()
    provider = llm_provider or create_llm_provider(resolved_settings)
    context = build_research_context(
        selection,
        document.document,
        document.pages,
        user_question=normalized_question,
        conversation=conversation,
        context_token_budget=resolved_settings.context_token_budget,
        history_token_budget=resolved_settings.history_token_budget,
    )
    response = provider.complete(build_followup_prompt(context))
    return Message(role="assistant", task="followup", content=response)
