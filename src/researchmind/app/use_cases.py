"""Application API coordinating ResearchMind domain and infrastructure modules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from researchmind.config import ConfigError, Settings, load_settings
from researchmind.core import build_research_context, locate_selection
from researchmind.llm import (
    LlmError,
    LlmProvider,
    build_algorithm_prompt,
    build_concept_prompt,
    build_contextual_prompt,
    build_followup_prompt,
    build_math_prompt,
    create_llm_provider,
)
from researchmind.integration.obsidian import (
    ObsidianError,
    VaultConfigurationError,
    render_markdown,
    write_note_to_vault,
)
from researchmind.models import (
    Conversation,
    KnowledgeNote,
    Message,
    Page,
    ReadingSelection,
)
from researchmind.pdf import (
    OpenedDocument,
    PdfError,
    TextMatch,
    extract_page,
    open_pdf as pdf_open_pdf,
    render_figure_images,
    render_page_image,
    search_text as pdf_search_text,
)
from researchmind.translation import (
    LlmTranslationProvider,
    TranslationError,
    TranslationProvider,
    translate_text,
)


ExplainMode = Literal["concept", "math", "algorithm", "contextual"]
USER_FACING_ERRORS = (
    ConfigError,
    PdfError,
    LlmError,
    TranslationError,
    ObsidianError,
    ValueError,
)


@dataclass(frozen=True)
class PageView:
    """One rendered page plus its extracted, selectable text."""

    page: Page
    image_png: bytes
    zoom: float
    figure_images: tuple[bytes, ...] = ()


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

    page = extract_page(document, page_number)
    return PageView(
        page=page,
        image_png=render_page_image(document, page_number, zoom=zoom),
        zoom=float(zoom),
        figure_images=render_figure_images(document, page_number),
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


def capture_knowledge(
    document: OpenedDocument,
    selection: ReadingSelection | None,
    messages: list[Message],
    user_notes: str,
    tags: list[str],
    *,
    title: str | None = None,
) -> KnowledgeNote:
    """Assemble selected reading and conversation content into a KnowledgeNote."""

    return KnowledgeNote(
        title=_knowledge_title(title, document, selection),
        source=document.document.title,
        authors=list(document.document.authors),
        page_number=_selection_page_number(selection),
        selected_text=_optional_text(None if selection is None else selection.text),
        translation=_joined_message_content(
            messages,
            role="assistant",
            tasks={"translate"},
        ),
        question=_joined_message_content(
            messages,
            role="user",
            tasks={
                "explain:concept",
                "explain:math",
                "explain:algorithm",
                "explain:contextual",
                "followup",
            },
        ),
        ai_explanation=_joined_message_content(
            messages,
            role="assistant",
            tasks={
                "explain:concept",
                "explain:math",
                "explain:algorithm",
                "explain:contextual",
                "followup",
            },
        ),
        user_notes=_optional_text(user_notes),
        tags=_normalized_tags(tags),
    )


def save_note_to_vault(
    note: KnowledgeNote,
    *,
    settings: Settings | None = None,
) -> Path:
    """Write a note through the sole Obsidian Vault integration boundary."""

    resolved_settings = settings or load_settings()
    if resolved_settings.obsidian_vault_path is None:
        raise VaultConfigurationError(
            "OBSIDIAN_VAULT_PATH is not configured. Add it before saving notes."
        )
    return write_note_to_vault(
        note,
        vault_path=resolved_settings.obsidian_vault_path,
        subdirectory=resolved_settings.obsidian_subdirectory,
    )


def preview_note_markdown(note: KnowledgeNote) -> str:
    """Render a note for UI preview through the application API."""

    return render_markdown(note)


def _knowledge_title(
    title: str | None,
    document: OpenedDocument,
    selection: ReadingSelection | None,
) -> str:
    requested_title = _single_line(title)
    if requested_title:
        return requested_title

    if selection is not None:
        selection_title = _single_line(selection.text)
        if selection_title:
            return selection_title[:80].rstrip()
    return _single_line(document.document.title) or "Research note"


def _selection_page_number(selection: ReadingSelection | None) -> int | None:
    if selection is None or selection.locator is None:
        return None
    page_number = selection.locator.get("page_number")
    if isinstance(page_number, int) and not isinstance(page_number, bool):
        return page_number
    return None


def _joined_message_content(
    messages: list[Message],
    *,
    role: str,
    tasks: set[str],
) -> str | None:
    selected_content = [
        content
        for message in messages
        if message.role == role
        and message.task in tasks
        and (content := message.content.strip())
    ]
    return "\n\n".join(selected_content) or None


def _normalized_tags(tags: list[str]) -> list[str]:
    normalized_tags: list[str] = []
    seen: set[str] = set()
    for tag in tags:
        normalized = _single_line(tag)
        identity = normalized.casefold()
        if normalized and identity not in seen:
            normalized_tags.append(normalized)
            seen.add(identity)
    return normalized_tags


def _optional_text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _single_line(value: str | None) -> str:
    return "" if value is None else " ".join(value.split())
