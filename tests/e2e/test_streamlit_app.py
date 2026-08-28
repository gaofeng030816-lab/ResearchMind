"""Streamlit smoke coverage for the complete M5 product loop."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from researchmind.app import use_cases
from researchmind.config import Settings
from researchmind.models import Message


APP_PATH = Path(__file__).parents[2] / "src" / "researchmind" / "app" / "app.py"


def test_page_number_widget_navigates_immediately(
    multi_page_pdf: Path,
) -> None:
    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.text_input(key="pdf_path_input").set_value(str(multi_page_pdf))
    app.button(key="open_pdf_button").click().run()
    assert not app.exception

    document_id = app.session_state["opened_document"].document.id
    app.number_input(key=f"page_jump_input_{document_id}").set_value(2).run()

    assert not app.exception
    assert app.session_state["current_page_number"] == 2


def test_reader_exposes_ordered_blocks_and_figure_download(
    two_column_pdf: Path,
) -> None:
    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.text_input(key="pdf_path_input").set_value(str(two_column_pdf))
    app.button(key="open_pdf_button").click().run()

    assert not app.exception
    code_values = [code.value for code in app.code]
    assert code_values[:5] == [
        "Two Column Study",
        "Left first paragraph continues here.",
        "Left second block.",
        "Right first block.",
        "Right second block.",
    ]
    assert len(app.image) == 2
    assert len(app.download_button) == 1
    assert app.download_button[0].label == "下载图表 1"


def test_reader_warns_when_document_has_no_extractable_text(
    blank_page_pdf: Path,
) -> None:
    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.text_input(key="pdf_path_input").set_value(str(blank_page_pdf))
    app.button(key="open_pdf_button").click().run()

    assert not app.exception
    assert any(
        "未提取到可用文本" in warning.value
        for warning in app.warning
    )


def test_context_evidence_is_visible_before_explanation(
    monkeypatch: pytest.MonkeyPatch,
    structured_pdf: Path,
) -> None:
    monkeypatch.setattr(
        use_cases,
        "load_settings",
        lambda: Settings(context_token_budget=200, history_token_budget=200),
    )

    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.text_input(key="pdf_path_input").set_value(str(structured_pdf))
    app.button(key="open_pdf_button").click().run()
    document_id = app.session_state["opened_document"].document.id
    app.text_area(key=f"selection_text_{document_id}").set_value(
        "Second context block"
    )
    app.button(key="create_selection_button").click().run()

    assert not app.exception
    assert any(
        expander.label == "AI 解释上下文证据（发送前预览）"
        for expander in app.expander
    )
    plain_text = [element.value for element in app.text]
    assert "章节：2 Proposed Method" in plain_text
    assert "图表说明：Figure 3. Update overview" in plain_text
    assert any(
        "约 " in caption.value and "tokens" in caption.value
        for caption in app.caption
    )


def test_reader_to_obsidian_flow_without_network(
    monkeypatch: pytest.MonkeyPatch,
    multi_page_pdf: Path,
    temporary_vault: Path,
) -> None:
    """Exercise the V1 UI loop without sending data to an external service."""

    original_save_note = use_cases.save_note_to_vault
    calls: list[str] = []

    def fake_translate(selection: object) -> Message:
        calls.append("translate")
        return Message(
            role="assistant",
            task="translate",
            content="第二页的唯一文本。",
        )

    def fake_explain(*args: object, **kwargs: object) -> Message:
        calls.append("explain")
        return Message(
            role="assistant",
            task="explain:contextual",
            content="This passage identifies the evidence on page two.",
        )

    def fake_followup(*args: object, **kwargs: object) -> Message:
        calls.append("followup")
        return Message(
            role="assistant",
            task="followup",
            content="The later conclusion depends on this evidence.",
        )

    def save_to_temporary_vault(note: object) -> Path:
        calls.append("save")
        return original_save_note(
            note,
            settings=Settings(
                obsidian_vault_path=temporary_vault,
                obsidian_subdirectory="ResearchMind",
            ),
        )

    monkeypatch.setattr(use_cases, "translate_selection", fake_translate)
    monkeypatch.setattr(use_cases, "explain_selection", fake_explain)
    monkeypatch.setattr(use_cases, "ask_followup", fake_followup)
    monkeypatch.setattr(use_cases, "save_note_to_vault", save_to_temporary_vault)

    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    assert not app.exception

    app.text_input(key="pdf_path_input").set_value(str(multi_page_pdf))
    app.button(key="open_pdf_button").click().run()
    assert not app.exception
    document_id = app.session_state["opened_document"].document.id
    assert app.session_state["current_page_number"] == 1
    assert any(
        "Page one unique text" in code.value
        for code in app.code
    )
    code_values = [code.value for code in app.code]
    assert "Page one unique text" in code_values
    assert "Shared optimization method" in code_values

    app.button(key="next_page_button").click().run()
    assert not app.exception
    assert app.session_state["current_page_number"] == 2

    app.number_input(key=f"page_jump_input_{document_id}").set_value(3).run()
    assert not app.exception
    assert app.session_state["current_page_number"] == 3

    app.text_input(key=f"pdf_search_query_{document_id}").set_value(
        "Page two unique text"
    )
    app.button(key="pdf_search_button").click().run()
    assert not app.exception
    assert app.session_state["search_results"][0].page_number == 2
    app.button(key=f"search_match_{document_id}_0").click().run()
    assert not app.exception
    assert app.session_state["current_page_number"] == 2

    app.text_area(key=f"selection_text_{document_id}").set_value(
        "Page two unique text"
    )
    app.button(key="create_selection_button").click().run()
    assert not app.exception
    assert app.session_state["current_selection"].locator["page_number"] == 2

    app.button(key="translate_selection_button").click().run()
    assert not app.exception
    assert calls == ["translate"]

    app.selectbox(key="explanation_mode_select").set_value("contextual")
    app.text_input(key="explanation_question_input").set_value(
        "Why is this evidence important?"
    )
    app.button(key="explain_selection_button").click().run()
    assert not app.exception
    assert calls == ["translate", "explain"]

    app.text_input(key=f"followup_question_{document_id}").set_value(
        "What depends on this evidence?"
    )
    app.button(key="ask_followup_button").click().run()
    assert not app.exception
    assert calls == ["translate", "explain", "followup"]

    app.button(key="open_knowledge_panel_button").click().run()
    assert not app.exception
    assert app.session_state["knowledge_panel_open"] is True

    app.text_input(key=f"knowledge_title_{document_id}").set_value(
        "Page two evidence"
    )
    app.text_area(key=f"knowledge_user_notes_{document_id}").set_value(
        "This is the bridge between the method and conclusion."
    )
    app.text_input(key=f"knowledge_tags_{document_id}").set_value(
        "evidence, research-reading"
    )
    app.button(key="preview_knowledge_button").click().run()
    assert not app.exception
    assert app.session_state["current_knowledge_note"].title == "Page two evidence"

    app.button(key="save_knowledge_button").click().run()
    assert not app.exception
    assert calls == ["translate", "explain", "followup", "save"]

    saved_files = list((temporary_vault / "ResearchMind").glob("*.md"))
    assert len(saved_files) == 1
    markdown = saved_files[0].read_text(encoding="utf-8")
    assert "# Page two evidence" in markdown
    assert "> Page two unique text" in markdown
    assert "第二页的唯一文本。" in markdown
    assert "This passage identifies the evidence" in markdown
    assert "The later conclusion depends" in markdown
    assert "This is the bridge" in markdown
