"""Streamlit smoke coverage for the complete M5 product loop."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from researchmind.app import use_cases
from researchmind.config import Settings
from researchmind.models import (
    ConfigurationCheck,
    ConfigurationReport,
    Message,
)


APP_PATH = Path(__file__).parents[2] / "src" / "researchmind" / "app" / "app.py"


def test_user_can_run_safe_configuration_diagnostics(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = ConfigurationReport(
        checks=(
            ConfigurationCheck(
                code="python_runtime",
                label="Python",
                status="ok",
                message="Python runtime is supported.",
            ),
            ConfigurationCheck(
                code="vault",
                label="Obsidian Vault",
                status="warning",
                message="Vault is optional and not configured.",
            ),
        )
    )
    monkeypatch.setattr(
        use_cases,
        "get_configuration_report",
        lambda: report,
    )

    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.button(key="run_configuration_diagnostics").click().run()

    assert not app.exception
    assert any("Python" in item.value for item in app.success)
    assert any("Obsidian Vault" in item.value for item in app.warning)


def test_code_workspace_is_independent_from_pdf_and_has_two_goals(
    tmp_path: Path,
) -> None:
    project_path = tmp_path / "standalone-code"
    project_path.mkdir()
    (project_path / "train.py").write_text(
        "import numpy\n"
        "def main():\n"
        "    return numpy.array([1])\n",
        encoding="utf-8",
    )

    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.radio(key="workspace_navigation").set_value("code").run()

    assert not app.exception
    assert app.session_state["opened_document"] is None
    assert app.text_input(key="code_project_path_input")
    assert all(
        item.key != "pdf_path_input"
        for item in app.text_input
    )

    app.text_input(key="code_project_path_input").set_value(
        str(project_path)
    )
    app.button(key="open_code_project_button").click().run()

    assert not app.exception
    assert app.session_state["opened_document"] is None
    assert app.radio(key="code_workspace_goal").value == "beginner"
    assert any(
        "静态项目概览" in markdown.value
        for markdown in app.markdown
    )
    assert any(
        "从这里开始" in markdown.value
        for markdown in app.markdown
    )

    app.radio(key="code_workspace_goal").set_value("reproduction").run()

    assert not app.exception
    assert any(
        "静态复现检查" in markdown.value
        for markdown in app.markdown
    )
    assert any(
        "numpy" in text.value
        for text in app.text
    )
    app.button(key="select_code_button").click().run()

    assert not app.exception
    selection_id = app.session_state["current_code_selection"].id
    reproduction_question = app.text_area(
        key=f"code_question_input_{selection_id}_reproduction"
    ).value
    assert "科研代码复现角度" in reproduction_question

    app.radio(key="code_workspace_goal").set_value("beginner").run()

    assert not app.exception
    beginner_question = app.text_area(
        key=f"code_question_input_{selection_id}_beginner"
    ).value
    assert "第一次学习编程" in beginner_question


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


def test_reader_labels_copyable_formula_blocks(
    unicode_math_pdf: Path,
) -> None:
    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.text_input(key="pdf_path_input").set_value(str(unicode_math_pdf))
    app.button(key="open_pdf_button").click().run()

    assert not app.exception
    assert any(
        "疑似数学公式" in caption.value
        for caption in app.caption
    )
    assert any(
        "数学公式候选" in caption.value
        for caption in app.caption
    )


def test_reader_formula_block_can_become_selection_with_one_click(
    unicode_math_pdf: Path,
) -> None:
    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.text_input(key="pdf_path_input").set_value(str(unicode_math_pdf))
    app.button(key="open_pdf_button").click().run()

    assert not app.exception
    opened = app.session_state["opened_document"]
    document_id = opened.document.id
    formula_block = next(
        block for block in opened.pages[0].blocks if block.role == "formula"
    )

    app.button(
        key=f"select_block_{document_id}_1_{formula_block.block_index}"
    ).click().run()

    assert not app.exception
    selection = app.session_state["current_selection"]
    assert selection.text == formula_block.text
    assert selection.locator == {
        "page_number": 1,
        "block_index": formula_block.block_index,
        "bbox": formula_block.bbox,
    }
    assert app.text_area(key=f"selection_text_{document_id}").value == (
        formula_block.text
    )


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


def test_code_workspace_opens_selects_previews_and_explains_without_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_path = tmp_path / "code-project"
    project_path.mkdir()
    (project_path / "analysis.py").write_text(
        "def normalize(value: float) -> float:\n"
        "    return value / 100\n",
        encoding="utf-8",
    )

    def fake_explain_code(*args: object, **kwargs: object) -> Message:
        return Message(
            role="assistant",
            task="explain:code",
            content="This function scales a value to a fraction.",
        )

    monkeypatch.setattr(
        use_cases,
        "explain_code_selection",
        fake_explain_code,
    )
    monkeypatch.setattr(
        use_cases,
        "load_settings",
        lambda: Settings(context_token_budget=200),
    )

    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.radio(key="workspace_navigation").set_value("code").run()
    app.text_input(key="code_project_path_input").set_value(str(project_path))
    app.button(key="open_code_project_button").click().run()

    assert not app.exception
    assert app.session_state["opened_code_project"].name == "code-project"
    app.button(key="select_code_button").click().run()

    assert not app.exception
    assert app.session_state["current_code_selection"].symbol_name == "normalize"
    assert any(
        expander.label == "代码上下文证据（发送前预览）"
        for expander in app.expander
    )

    app.button(key="explain_code_button").click().run()

    assert not app.exception
    assert app.session_state["current_code_response"].content.startswith(
        "This function"
    )


def test_code_workspace_previews_and_saves_optional_obsidian_note(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    temporary_vault: Path,
) -> None:
    project_path = tmp_path / "note-code-project"
    project_path.mkdir()
    (project_path / "pipeline.py").write_text(
        "def prepare(data):\n    return list(data)\n",
        encoding="utf-8",
    )
    original_save_note = use_cases.save_note_to_vault

    def fake_explain_code(
        project: object,
        selection: object,
        **kwargs: object,
    ) -> Message:
        return Message(
            role="assistant",
            task="explain:code",
            content="This converts the input iterable into a list.",
            selection_id=getattr(selection, "id"),
        )

    def save_to_temporary_vault(note: object) -> Path:
        return original_save_note(
            note,
            settings=Settings(
                obsidian_vault_path=temporary_vault,
                obsidian_subdirectory="ResearchMind",
            ),
        )

    monkeypatch.setattr(
        use_cases,
        "explain_code_selection",
        fake_explain_code,
    )
    monkeypatch.setattr(
        use_cases,
        "save_note_to_vault",
        save_to_temporary_vault,
    )
    monkeypatch.setattr(
        use_cases,
        "load_settings",
        lambda: Settings(context_token_budget=200),
    )

    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.radio(key="workspace_navigation").set_value("code").run()
    app.text_input(key="code_project_path_input").set_value(str(project_path))
    app.button(key="open_code_project_button").click().run()
    app.button(key="select_code_button").click().run()
    selection = app.session_state["current_code_selection"]
    app.button(key="explain_code_button").click().run()

    app.text_input(key=f"code_note_title_{selection.id}").set_value(
        "Prepare pipeline input"
    )
    app.text_area(key=f"code_note_user_notes_{selection.id}").set_value(
        "This normalizes an arbitrary iterable before training."
    )
    app.text_input(key=f"code_note_tags_{selection.id}").set_value(
        "reproduction, preprocessing"
    )
    app.button(key="preview_code_note_button").click().run()

    assert not app.exception
    note = app.session_state["current_code_note"]
    assert note.source_type == "code"
    assert note.code_selection.relative_path == "pipeline.py"
    assert str(project_path) not in use_cases.preview_note_markdown(note)

    app.button(key="save_code_note_button").click().run()

    assert not app.exception
    saved_files = list((temporary_vault / "ResearchMind").glob("*.md"))
    assert len(saved_files) == 1
    markdown = saved_files[0].read_text(encoding="utf-8")
    assert "# Prepare pipeline input" in markdown
    assert "- 相对路径：pipeline.py" in markdown
    assert "This converts the input iterable" in markdown
    assert "This normalizes an arbitrary iterable" in markdown
    assert str(project_path) not in markdown


def test_t5_b1_previews_requires_confirmation_applies_and_rolls_back(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_path = tmp_path / "controlled-write"
    project_path.mkdir()
    source_path = project_path / "model.py"
    original = "def score(value):\n    return value + 1\n"
    source_path.write_text(original, encoding="utf-8")

    class ReplacementProvider:
        def complete(self, messages: object, **kwargs: object) -> str:
            return (
                "<replacement>def score(value):\n"
                "    return value + 2</replacement>"
            )

    monkeypatch.setattr(
        use_cases,
        "create_llm_provider",
        lambda settings: ReplacementProvider(),
    )
    monkeypatch.setattr(
        use_cases,
        "load_settings",
        lambda: Settings(context_token_budget=200),
    )

    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.radio(key="workspace_navigation").set_value("code").run()
    app.text_input(key="code_project_path_input").set_value(
        str(project_path)
    )
    app.button(key="open_code_project_button").click().run()
    app.button(key="select_code_button").click().run()
    selection = app.session_state["current_code_selection"]
    app.text_area(
        key=f"code_change_instruction_{selection.id}"
    ).set_value("Increase the score by two.")
    app.button(key="propose_code_change_button").click().run()

    assert not app.exception
    proposal = app.session_state["code_change_proposal"]
    assert proposal.relative_path == "model.py"
    assert source_path.read_text(encoding="utf-8") == original
    assert app.button(key="apply_code_change_button").disabled is True
    assert any("--- a/model.py" in item.value for item in app.code)

    app.checkbox(
        key=f"confirm_code_change_apply_{proposal.id}"
    ).set_value(True).run()
    app.button(key="apply_code_change_button").click().run()

    assert not app.exception
    assert source_path.read_text(encoding="utf-8").endswith("value + 2\n")
    receipt = app.session_state["code_change_receipt"]
    recovery_path = project_path / Path(receipt.recovery_relative_path)
    assert recovery_path.read_text(encoding="utf-8") == original
    assert app.session_state["current_code_selection"] is None
    assert app.session_state["code_change_audit"][-1].action == "apply"

    app.checkbox(
        key=f"confirm_code_change_rollback_{receipt.proposal_id}"
    ).set_value(True).run()
    app.button(key="rollback_code_change_button").click().run()

    assert not app.exception
    assert source_path.read_text(encoding="utf-8") == original
    assert app.session_state["code_change_receipt"] is None
    assert app.session_state["code_change_audit"][-1].action == "rollback"


def test_t5_b1_cancel_keeps_disk_unchanged_and_audits_metadata_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    project_path = tmp_path / "cancel-write"
    project_path.mkdir()
    source_path = project_path / "model.py"
    original = "value = 1\n"
    source_path.write_text(original, encoding="utf-8")

    class ReplacementProvider:
        def complete(self, messages: object, **kwargs: object) -> str:
            return "<replacement>value = 2</replacement>"

    monkeypatch.setattr(
        use_cases,
        "create_llm_provider",
        lambda settings: ReplacementProvider(),
    )
    monkeypatch.setattr(
        use_cases,
        "load_settings",
        lambda: Settings(context_token_budget=200),
    )

    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.radio(key="workspace_navigation").set_value("code").run()
    app.text_input(key="code_project_path_input").set_value(
        str(project_path)
    )
    app.button(key="open_code_project_button").click().run()
    app.button(key="select_code_button").click().run()
    selection = app.session_state["current_code_selection"]
    app.text_area(
        key=f"code_change_instruction_{selection.id}"
    ).set_value("Set the value to two.")
    app.button(key="propose_code_change_button").click().run()
    app.button(key="cancel_code_change_button").click().run()

    assert not app.exception
    assert source_path.read_text(encoding="utf-8") == original
    assert app.session_state["code_change_proposal"] is None
    event = app.session_state["code_change_audit"][-1]
    assert event.action == "cancel"
    assert event.status == "canceled"
    audit_text = repr(app.session_state["code_change_audit"])
    assert "value = 1" not in audit_text
    assert str(project_path) not in audit_text


def test_user_confirms_paper_to_code_link_and_note_includes_it(
    monkeypatch: pytest.MonkeyPatch,
    multi_page_pdf: Path,
    tmp_path: Path,
) -> None:
    project_path = tmp_path / "linked-code"
    project_path.mkdir()
    (project_path / "solver.py").write_text(
        "def step(value):\n"
        "    return value + 1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        use_cases,
        "translate_selection",
        lambda selection: Message(
            role="assistant",
            task="translate",
            content="Translated page one text.",
        ),
    )

    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.text_input(key="pdf_path_input").set_value(str(multi_page_pdf))
    app.button(key="open_pdf_button").click().run()
    document_id = app.session_state["opened_document"].document.id
    app.text_area(key=f"selection_text_{document_id}").set_value(
        "Page one unique text"
    )
    app.button(key="create_selection_button").click().run()
    app.button(key="translate_selection_button").click().run()

    app.radio(key="workspace_navigation").set_value("code").run()
    app.text_input(key="code_project_path_input").set_value(str(project_path))
    app.button(key="open_code_project_button").click().run()
    app.button(key="select_code_button").click().run()
    app.button(key="create_evidence_link_button").click().run()

    assert not app.exception
    links = app.session_state["evidence_links"]
    assert len(links) == 1
    assert links[0].generation_method == "user_confirmed"
    assert links[0].paper.page_number == 1
    assert links[0].code.relative_path == "solver.py"
    assert any(
        "用户确认" in markdown.value
        for markdown in app.markdown
    )

    app.radio(key="workspace_navigation").set_value("paper").run()
    app.button(key="open_knowledge_panel_button").click().run()
    app.button(key="preview_knowledge_button").click().run()

    assert not app.exception
    note = app.session_state["current_knowledge_note"]
    assert note.evidence_links == links

    second_project = tmp_path / "second-code-project"
    second_project.mkdir()
    (second_project / "other.py").write_text(
        "value = 2\n",
        encoding="utf-8",
    )
    app.radio(key="workspace_navigation").set_value("code").run()
    app.text_input(key="code_project_path_input").set_value(
        str(second_project)
    )
    app.button(key="open_code_project_button").click().run()

    assert not app.exception
    assert app.session_state["evidence_links"] == []


def test_t5_read_only_assistant_requires_user_continue_and_keeps_audit(
    monkeypatch: pytest.MonkeyPatch,
    multi_page_pdf: Path,
) -> None:
    class AssistantProvider:
        def __init__(self) -> None:
            self.responses = [
                (
                    '<assistant_action>{"action":"inspect_paper_context"}'
                    "</assistant_action>"
                ),
                (
                    '<assistant_action>{"action":"final",'
                    '"answer":"The paper evidence supports the claim."}'
                    "</assistant_action>"
                ),
            ]
            self.calls: list[object] = []

        def complete(
            self,
            messages: object,
            **kwargs: object,
        ) -> str:
            self.calls.append(messages)
            return self.responses.pop(0)

    provider = AssistantProvider()
    monkeypatch.setattr(
        use_cases,
        "create_llm_provider",
        lambda settings: provider,
    )
    monkeypatch.setattr(
        use_cases,
        "load_settings",
        lambda: Settings(
            context_token_budget=200,
            history_token_budget=200,
        ),
    )

    app = AppTest.from_file(APP_PATH, default_timeout=10).run()
    app.text_input(key="pdf_path_input").set_value(str(multi_page_pdf))
    app.button(key="open_pdf_button").click().run()
    document_id = app.session_state["opened_document"].document.id
    app.text_area(key=f"selection_text_{document_id}").set_value(
        "Page one unique text"
    )
    app.button(key="create_selection_button").click().run()
    app.radio(key="workspace_navigation").set_value("assistant").run()
    app.text_area(key="read_only_assistant_question").set_value(
        "How does this evidence support the claim?"
    )
    app.button(key="start_read_only_assistant_button").click().run()

    assert not app.exception
    session = app.session_state["read_only_assistant_session"]
    assert session.status == "awaiting_user"
    assert session.tool_call_count == 1
    assert session.llm_call_count == 1
    assert len(provider.calls) == 1
    assert any(
        expander.label.startswith("待发送工具结果")
        for expander in app.expander
    )

    app.button(key="continue_read_only_assistant_button").click().run()

    assert not app.exception
    session = app.session_state["read_only_assistant_session"]
    assert session.status == "completed"
    assert session.final_answer == "The paper evidence supports the claim."
    assert session.llm_call_count == 2
    assert len(provider.calls) == 2
    assert not any(
        expander.label.startswith("待发送工具结果")
        for expander in app.expander
    )
    assert any(
        expander.label.startswith("已发送工具结果")
        for expander in app.expander
    )

    app.radio(key="workspace_navigation").set_value("paper").run()
    app.text_area(key=f"selection_text_{document_id}").set_value(
        "Shared optimization method"
    )
    app.button(key="create_selection_button").click().run()

    assert not app.exception
    assert app.session_state["read_only_assistant_session"] is None


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

    def fake_convert_latex(*args: object, **kwargs: object) -> Message:
        calls.append("latex")
        return Message(
            role="assistant",
            task="convert:latex",
            content=r"x_{2}=x_{1}+d",
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
    monkeypatch.setattr(
        use_cases,
        "convert_selection_to_latex",
        fake_convert_latex,
    )
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

    app.button(key="convert_latex_button").click().run()
    assert not app.exception
    assert calls == ["translate", "latex"]
    assert app.session_state["current_conversation"].messages[-1].content == (
        r"x_{2}=x_{1}+d"
    )

    app.selectbox(key="explanation_mode_select").set_value("contextual")
    app.text_input(key="explanation_question_input").set_value(
        "Why is this evidence important?"
    )
    app.button(key="explain_selection_button").click().run()
    assert not app.exception
    assert calls == ["translate", "latex", "explain"]

    app.text_input(key=f"followup_question_{document_id}").set_value(
        "What depends on this evidence?"
    )
    app.button(key="ask_followup_button").click().run()
    assert not app.exception
    assert calls == ["translate", "latex", "explain", "followup"]

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
    assert calls == ["translate", "latex", "explain", "followup", "save"]

    saved_files = list((temporary_vault / "ResearchMind").glob("*.md"))
    assert len(saved_files) == 1
    markdown = saved_files[0].read_text(encoding="utf-8")
    assert "# Page two evidence" in markdown
    assert "> Page two unique text" in markdown
    assert "第二页的唯一文本。" in markdown
    assert "$$\nx_{2}=x_{1}+d\n$$" in markdown
    assert "This passage identifies the evidence" in markdown
    assert "The later conclusion depends" in markdown
    assert "This is the bridge" in markdown
