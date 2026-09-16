"""Framework-independent ResearchMind domain rules."""

from researchmind.core.code_changes import (
    MAX_CHANGED_LINES,
    MAX_CODE_CHANGE_FILE_BYTES,
    MAX_CODE_REPLACEMENT_CHARACTERS,
    build_code_change_proposal,
    replace_code_project_file,
    validate_code_change_snapshot,
)

from researchmind.core.code_context import (
    build_code_context,
    get_code_file,
    select_code_lines,
    select_code_symbol,
    summarize_code_project,
)
from researchmind.core.conversation import trim_conversation_history
from researchmind.core.evidence_links import (
    add_evidence_link,
    create_user_confirmed_evidence_link,
)
from researchmind.core.research_context import build_research_context
from researchmind.core.read_only_assistant import (
    MAX_ASSISTANT_LLM_CALLS,
    MAX_ASSISTANT_QUESTION_CHARS,
    MAX_ASSISTANT_TOOL_CALLS,
    MAX_ASSISTANT_TOOL_OUTPUT_CHARS,
    MAX_ASSISTANT_TOTAL_TOOL_OUTPUT_CHARS,
    create_read_only_assistant_session,
    record_assistant_final_step,
    record_assistant_tool_step,
    stop_read_only_assistant_session,
    tool_output_stop_reason,
    tool_request_stop_reason,
)
from researchmind.core.selection import locate_selection, select_text_block
from researchmind.core.note_drafts import (
    MAX_DRAFT_MARKDOWN_CHARS,
    MAX_DRAFT_TITLE_CHARS,
    MAX_EVIDENCE_CONTENT_CHARS,
    MAX_EVIDENCE_ITEMS_PER_DRAFT,
    MAX_EVIDENCE_LOCATOR_BYTES,
    MAX_EVIDENCE_SOURCE_LABEL_CHARS,
    serialize_evidence_locator,
    validate_evidence_snapshot,
    validate_note_draft,
)

__all__ = [
    "MAX_CHANGED_LINES",
    "MAX_CODE_CHANGE_FILE_BYTES",
    "MAX_CODE_REPLACEMENT_CHARACTERS",
    "build_code_change_proposal",
    "replace_code_project_file",
    "validate_code_change_snapshot",
    "build_code_context",
    "build_research_context",
    "add_evidence_link",
    "create_user_confirmed_evidence_link",
    "get_code_file",
    "locate_selection",
    "select_code_lines",
    "select_code_symbol",
    "summarize_code_project",
    "select_text_block",
    "trim_conversation_history",
    "MAX_DRAFT_MARKDOWN_CHARS",
    "MAX_DRAFT_TITLE_CHARS",
    "MAX_EVIDENCE_CONTENT_CHARS",
    "MAX_EVIDENCE_ITEMS_PER_DRAFT",
    "MAX_EVIDENCE_LOCATOR_BYTES",
    "MAX_EVIDENCE_SOURCE_LABEL_CHARS",
    "serialize_evidence_locator",
    "validate_evidence_snapshot",
    "validate_note_draft",
    "MAX_ASSISTANT_LLM_CALLS",
    "MAX_ASSISTANT_QUESTION_CHARS",
    "MAX_ASSISTANT_TOOL_CALLS",
    "MAX_ASSISTANT_TOOL_OUTPUT_CHARS",
    "MAX_ASSISTANT_TOTAL_TOOL_OUTPUT_CHARS",
    "create_read_only_assistant_session",
    "record_assistant_final_step",
    "record_assistant_tool_step",
    "stop_read_only_assistant_session",
    "tool_output_stop_reason",
    "tool_request_stop_reason",
]
