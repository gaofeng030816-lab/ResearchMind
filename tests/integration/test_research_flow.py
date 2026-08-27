"""Integration coverage for the M3 reading-to-understanding workflow."""

from html import escape
from pathlib import Path

from researchmind.app.use_cases import (
    ask_followup,
    capture_knowledge,
    create_selection,
    explain_selection,
    get_page_view,
    open_pdf,
    save_note_to_vault,
    search_text,
    translate_selection,
)
from researchmind.config import Settings
from researchmind.models import Conversation, Message
from researchmind.translation import LlmTranslationProvider


def test_open_select_translate_explain_and_follow_up_without_network(
    single_page_pdf: Path,
    temporary_vault: Path,
    fake_llm_provider: object,
) -> None:
    fake_llm_provider.responses = [
        "第二个上下文块。",
        "This block supplies nearby evidence for the paper's claim.",
        "It matters because the next inference depends on that evidence.",
    ]
    settings = Settings(
        target_language="zh-CN",
        obsidian_vault_path=temporary_vault,
        obsidian_subdirectory="ResearchMind",
        context_token_budget=200,
        history_token_budget=200,
    )

    opened = open_pdf(single_page_pdf, settings=settings)
    page_view = get_page_view(opened, 1, zoom=1.0)
    matches = search_text(opened, "Second context")
    selection = create_selection(opened, "Second context block", current_page=1)

    translation = translate_selection(
        selection,
        translation_provider=LlmTranslationProvider(fake_llm_provider),
        settings=settings,
    )
    conversation = Conversation(document_id=opened.document.id)
    explanation_question = Message(
        role="user",
        task="explain:contextual",
        content="Why is this block relevant?",
    )
    explanation = explain_selection(
        selection,
        "contextual",
        document=opened,
        conversation=conversation,
        question=explanation_question.content,
        llm_provider=fake_llm_provider,
        settings=settings,
    )
    conversation.messages.extend([explanation_question, explanation])
    followup_question = Message(
        role="user",
        task="followup",
        content="Why does the next inference depend on it?",
    )
    followup = ask_followup(
        followup_question.content,
        document=opened,
        selection=selection,
        conversation=conversation,
        llm_provider=fake_llm_provider,
        settings=settings,
    )
    note = capture_knowledge(
        opened,
        selection,
        [
            translation,
            explanation_question,
            explanation,
            followup_question,
            followup,
        ],
        "The evidence connects the local claim to the next inference.",
        ["research-reading", "evidence"],
        title="Evidence chain",
    )
    saved_path = save_note_to_vault(note, settings=settings)
    saved_markdown = saved_path.read_text(encoding="utf-8")

    assert page_view.page.page_number == 1
    assert page_view.image_png.startswith(b"\x89PNG\r\n\x1a\n")
    assert matches[0].page_number == 1
    assert selection.locator is not None
    assert translation.task == "translate"
    assert translation.content == "第二个上下文块。"
    assert explanation.task == "explain:contextual"
    assert followup.task == "followup"
    assert len(fake_llm_provider.calls) == 3

    explanation_prompt = fake_llm_provider.calls[1][0][1].content
    assert "<paper_context>" in explanation_prompt
    assert "Second context block" in explanation_prompt
    assert "Why is this block relevant?" in explanation_prompt

    followup_prompt = fake_llm_provider.calls[2][0][1].content
    assert "<conversation_history>" in followup_prompt
    assert "Why is this block relevant?" in followup_prompt
    assert escape(explanation.content) in followup_prompt
    assert "Why does the next inference depend on it?" in followup_prompt

    assert saved_path.parent == temporary_vault / "ResearchMind"
    assert saved_path.suffix == ".md"
    assert "# Evidence chain" in saved_markdown
    assert "Fixture Research Paper" in saved_markdown
    assert "> Second context block" in saved_markdown
    assert translation.content in saved_markdown
    assert explanation_question.content in saved_markdown
    assert explanation.content in saved_markdown
    assert followup_question.content in saved_markdown
    assert followup.content in saved_markdown
    assert "The evidence connects" in saved_markdown
