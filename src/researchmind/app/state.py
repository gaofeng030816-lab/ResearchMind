"""Centralized Streamlit session-state access and mutation."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import streamlit as st

from researchmind.models import (
    CodeChangeAuditEvent,
    CodeChangeProposal,
    CodeChangeReceipt,
    CodeChangeRollbackReceipt,
    CodeProject,
    CodeSelection,
    Conversation,
    EvidenceLink,
    KnowledgeNote,
    Message,
    MessageTask,
    ReadOnlyAssistantSession,
    ReadingSelection,
    ZoteroBrowseResult,
    ZoteroItemDetails,
)
from researchmind.pdf import OpenedDocument, TextMatch


OPENED_DOCUMENT_KEY = "opened_document"
CURRENT_PAGE_NUMBER_KEY = "current_page_number"
CURRENT_SELECTION_KEY = "current_selection"
CURRENT_CONVERSATION_KEY = "current_conversation"
SEARCH_RESULTS_KEY = "search_results"
CURRENT_NOTE_KEY = "current_knowledge_note"
KNOWLEDGE_PANEL_OPEN_KEY = "knowledge_panel_open"
LAST_SAVED_PATH_KEY = "last_saved_path"
OPENED_CODE_PROJECT_KEY = "opened_code_project"
CURRENT_CODE_SELECTION_KEY = "current_code_selection"
CURRENT_CODE_RESPONSE_KEY = "current_code_response"
CURRENT_CODE_RESPONSE_QUESTION_KEY = "current_code_response_question"
CURRENT_CODE_NOTE_KEY = "current_code_note"
LAST_CODE_NOTE_SAVED_PATH_KEY = "last_code_note_saved_path"
EVIDENCE_LINKS_KEY = "evidence_links"
READ_ONLY_ASSISTANT_SESSION_KEY = "read_only_assistant_session"
CODE_CHANGE_PROPOSAL_KEY = "code_change_proposal"
CODE_CHANGE_RECEIPT_KEY = "code_change_receipt"
CODE_CHANGE_ROLLBACK_RECEIPT_KEY = "code_change_rollback_receipt"
CODE_CHANGE_AUDIT_KEY = "code_change_audit"
REQUESTED_WORKSPACE_KEY = "requested_workspace"
ZOTERO_BROWSE_RESULT_KEY = "zotero_browse_result"
ZOTERO_ITEM_DETAILS_KEY = "zotero_item_details"
ZOTERO_ACTION_GENERATION_KEY = "zotero_action_generation"


def initialize_state() -> None:
    """Install all application-owned session defaults once per UI session."""

    defaults: dict[str, object] = {
        OPENED_DOCUMENT_KEY: None,
        CURRENT_PAGE_NUMBER_KEY: 1,
        CURRENT_SELECTION_KEY: None,
        CURRENT_CONVERSATION_KEY: None,
        SEARCH_RESULTS_KEY: [],
        CURRENT_NOTE_KEY: None,
        KNOWLEDGE_PANEL_OPEN_KEY: False,
        LAST_SAVED_PATH_KEY: None,
        OPENED_CODE_PROJECT_KEY: None,
        CURRENT_CODE_SELECTION_KEY: None,
        CURRENT_CODE_RESPONSE_KEY: None,
        CURRENT_CODE_RESPONSE_QUESTION_KEY: None,
        CURRENT_CODE_NOTE_KEY: None,
        LAST_CODE_NOTE_SAVED_PATH_KEY: None,
        EVIDENCE_LINKS_KEY: [],
        READ_ONLY_ASSISTANT_SESSION_KEY: None,
        CODE_CHANGE_PROPOSAL_KEY: None,
        CODE_CHANGE_RECEIPT_KEY: None,
        CODE_CHANGE_ROLLBACK_RECEIPT_KEY: None,
        CODE_CHANGE_AUDIT_KEY: [],
        REQUESTED_WORKSPACE_KEY: None,
        ZOTERO_BROWSE_RESULT_KEY: None,
        ZOTERO_ITEM_DETAILS_KEY: None,
        ZOTERO_ACTION_GENERATION_KEY: 0,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_opened_document() -> OpenedDocument | None:
    return cast(OpenedDocument | None, st.session_state[OPENED_DOCUMENT_KEY])


def set_opened_document(document: OpenedDocument) -> None:
    """Replace the active document and reset all document-scoped state."""

    st.session_state[OPENED_DOCUMENT_KEY] = document
    st.session_state[CURRENT_PAGE_NUMBER_KEY] = 1
    st.session_state[CURRENT_SELECTION_KEY] = None
    st.session_state[CURRENT_CONVERSATION_KEY] = Conversation(
        document_id=document.document.id
    )
    st.session_state[SEARCH_RESULTS_KEY] = []
    st.session_state[CURRENT_NOTE_KEY] = None
    st.session_state[KNOWLEDGE_PANEL_OPEN_KEY] = False
    st.session_state[LAST_SAVED_PATH_KEY] = None
    st.session_state[EVIDENCE_LINKS_KEY] = []
    _clear_read_only_assistant_session()
    page_widget_key = page_number_widget_key(document.document.id)
    if page_widget_key in st.session_state:
        st.session_state[page_widget_key] = 1


def get_current_page_number() -> int:
    return int(st.session_state[CURRENT_PAGE_NUMBER_KEY])


def set_current_page_number(page_number: int) -> None:
    document = get_opened_document()
    if document is None:
        raise ValueError("Open a PDF before changing pages.")
    if page_number < 1 or page_number > document.document.num_pages:
        raise ValueError(
            f"Page number must be between 1 and {document.document.num_pages}."
        )
    st.session_state[CURRENT_PAGE_NUMBER_KEY] = page_number
    page_widget_key = page_number_widget_key(document.document.id)
    if page_widget_key in st.session_state:
        st.session_state[page_widget_key] = page_number


def set_current_page_number_from_widget(widget_key: str) -> None:
    """Synchronize the active page from a page-number input callback."""

    page_number = int(st.session_state[widget_key])
    document = get_opened_document()
    if document is None:
        raise ValueError("Open a PDF before changing pages.")
    if page_number < 1 or page_number > document.document.num_pages:
        raise ValueError(
            f"Page number must be between 1 and {document.document.num_pages}."
        )
    st.session_state[CURRENT_PAGE_NUMBER_KEY] = page_number


def page_number_widget_key(document_id: str) -> str:
    """Return the stable widget key for one document's page-number input."""

    return f"page_jump_input_{document_id}"


def request_workspace(workspace: str) -> None:
    if workspace not in {"paper", "code", "assistant", "library"}:
        raise ValueError("Requested workspace is unsupported.")
    st.session_state[REQUESTED_WORKSPACE_KEY] = workspace


def apply_requested_workspace() -> None:
    workspace = cast(
        str | None,
        st.session_state[REQUESTED_WORKSPACE_KEY],
    )
    if workspace is not None:
        st.session_state["workspace_navigation"] = workspace
        st.session_state[REQUESTED_WORKSPACE_KEY] = None


def get_zotero_browse_result() -> ZoteroBrowseResult | None:
    return cast(
        ZoteroBrowseResult | None,
        st.session_state[ZOTERO_BROWSE_RESULT_KEY],
    )


def set_zotero_browse_result(result: ZoteroBrowseResult) -> None:
    st.session_state[ZOTERO_BROWSE_RESULT_KEY] = result
    st.session_state[ZOTERO_ITEM_DETAILS_KEY] = None


def clear_zotero_browse_result() -> None:
    st.session_state[ZOTERO_BROWSE_RESULT_KEY] = None
    st.session_state[ZOTERO_ITEM_DETAILS_KEY] = None


def get_zotero_item_details() -> ZoteroItemDetails | None:
    return cast(
        ZoteroItemDetails | None,
        st.session_state[ZOTERO_ITEM_DETAILS_KEY],
    )


def set_zotero_item_details(details: ZoteroItemDetails) -> None:
    st.session_state[ZOTERO_ACTION_GENERATION_KEY] += 1
    st.session_state[ZOTERO_ITEM_DETAILS_KEY] = details


def clear_zotero_item_details() -> None:
    st.session_state[ZOTERO_ACTION_GENERATION_KEY] += 1
    st.session_state[ZOTERO_ITEM_DETAILS_KEY] = None


def get_zotero_action_generation() -> int:
    return int(st.session_state[ZOTERO_ACTION_GENERATION_KEY])


def get_current_selection() -> ReadingSelection | None:
    return cast(ReadingSelection | None, st.session_state[CURRENT_SELECTION_KEY])


def set_current_selection(selection: ReadingSelection) -> None:
    st.session_state[CURRENT_SELECTION_KEY] = selection
    st.session_state[CURRENT_NOTE_KEY] = None
    st.session_state[LAST_SAVED_PATH_KEY] = None
    _clear_read_only_assistant_session()


def set_current_selection_from_reader(
    selection: ReadingSelection,
    *,
    document_id: str,
) -> None:
    """Set a block selection and mirror its text into the action widget."""

    set_current_selection(selection)
    st.session_state[selection_text_widget_key(document_id)] = selection.text


def selection_text_widget_key(document_id: str) -> str:
    return f"selection_text_{document_id}"


def get_current_conversation() -> Conversation | None:
    return cast(Conversation | None, st.session_state[CURRENT_CONVERSATION_KEY])


def get_messages() -> list[Message]:
    conversation = get_current_conversation()
    return [] if conversation is None else list(conversation.messages)


def append_message(message: Message) -> None:
    conversation = _required_conversation()
    conversation.messages.append(message)
    st.session_state[CURRENT_NOTE_KEY] = None
    st.session_state[LAST_SAVED_PATH_KEY] = None
    _clear_read_only_assistant_session()


def append_exchange(
    user_content: str,
    user_task: MessageTask,
    assistant_message: Message,
) -> None:
    """Append a successful user/assistant exchange atomically."""

    normalized_content = user_content.strip()
    if not normalized_content:
        raise ValueError("Conversation message must not be blank.")
    conversation = _required_conversation()
    conversation.messages.extend(
        [
            Message(role="user", task=user_task, content=normalized_content),
            assistant_message,
        ]
    )
    st.session_state[CURRENT_NOTE_KEY] = None
    st.session_state[LAST_SAVED_PATH_KEY] = None
    _clear_read_only_assistant_session()


def get_search_results() -> list[TextMatch]:
    return list(cast(list[TextMatch], st.session_state[SEARCH_RESULTS_KEY]))


def set_search_results(matches: list[TextMatch]) -> None:
    st.session_state[SEARCH_RESULTS_KEY] = list(matches)


def get_current_note() -> KnowledgeNote | None:
    return cast(KnowledgeNote | None, st.session_state[CURRENT_NOTE_KEY])


def set_current_note(note: KnowledgeNote) -> None:
    st.session_state[CURRENT_NOTE_KEY] = note
    st.session_state[LAST_SAVED_PATH_KEY] = None


def is_knowledge_panel_open() -> bool:
    return bool(st.session_state[KNOWLEDGE_PANEL_OPEN_KEY])


def set_knowledge_panel_open(is_open: bool) -> None:
    st.session_state[KNOWLEDGE_PANEL_OPEN_KEY] = is_open


def get_last_saved_path() -> Path | None:
    return cast(Path | None, st.session_state[LAST_SAVED_PATH_KEY])


def set_last_saved_path(path: Path) -> None:
    st.session_state[LAST_SAVED_PATH_KEY] = path


def get_opened_code_project() -> CodeProject | None:
    return cast(
        CodeProject | None,
        st.session_state[OPENED_CODE_PROJECT_KEY],
    )


def set_opened_code_project(project: CodeProject) -> None:
    """Replace the active code folder and reset only code-scoped state."""

    st.session_state[OPENED_CODE_PROJECT_KEY] = project
    st.session_state[CURRENT_CODE_SELECTION_KEY] = None
    st.session_state[CURRENT_CODE_RESPONSE_KEY] = None
    st.session_state[CURRENT_CODE_RESPONSE_QUESTION_KEY] = None
    _clear_current_code_note()
    st.session_state[CODE_CHANGE_PROPOSAL_KEY] = None
    st.session_state[CODE_CHANGE_RECEIPT_KEY] = None
    st.session_state[CODE_CHANGE_ROLLBACK_RECEIPT_KEY] = None
    st.session_state[EVIDENCE_LINKS_KEY] = []
    st.session_state[CURRENT_NOTE_KEY] = None
    st.session_state[LAST_SAVED_PATH_KEY] = None
    _clear_read_only_assistant_session()


def get_current_code_selection() -> CodeSelection | None:
    return cast(
        CodeSelection | None,
        st.session_state[CURRENT_CODE_SELECTION_KEY],
    )


def set_current_code_selection(selection: CodeSelection) -> None:
    st.session_state[CURRENT_CODE_SELECTION_KEY] = selection
    st.session_state[CURRENT_CODE_RESPONSE_KEY] = None
    st.session_state[CURRENT_CODE_RESPONSE_QUESTION_KEY] = None
    st.session_state[CODE_CHANGE_PROPOSAL_KEY] = None
    _clear_current_code_note()
    _clear_read_only_assistant_session()


def get_current_code_response() -> Message | None:
    return cast(
        Message | None,
        st.session_state[CURRENT_CODE_RESPONSE_KEY],
    )


def set_current_code_response(response: Message, *, question: str) -> None:
    if response.task != "explain:code":
        raise ValueError("Code response must use the explain:code task.")
    normalized_question = question.strip()
    if not normalized_question:
        raise ValueError("Code response question must not be blank.")
    st.session_state[CURRENT_CODE_RESPONSE_KEY] = response
    st.session_state[CURRENT_CODE_RESPONSE_QUESTION_KEY] = normalized_question
    _clear_current_code_note()


def get_current_code_response_question() -> str | None:
    return cast(
        str | None,
        st.session_state[CURRENT_CODE_RESPONSE_QUESTION_KEY],
    )


def get_current_code_note() -> KnowledgeNote | None:
    return cast(
        KnowledgeNote | None,
        st.session_state[CURRENT_CODE_NOTE_KEY],
    )


def set_current_code_note(note: KnowledgeNote) -> None:
    if note.source_type != "code" or note.code_selection is None:
        raise ValueError("Current code note must contain code provenance.")
    st.session_state[CURRENT_CODE_NOTE_KEY] = note
    st.session_state[LAST_CODE_NOTE_SAVED_PATH_KEY] = None


def get_last_code_note_saved_path() -> Path | None:
    return cast(
        Path | None,
        st.session_state[LAST_CODE_NOTE_SAVED_PATH_KEY],
    )


def set_last_code_note_saved_path(path: Path) -> None:
    st.session_state[LAST_CODE_NOTE_SAVED_PATH_KEY] = path


def get_code_change_proposal() -> CodeChangeProposal | None:
    return cast(
        CodeChangeProposal | None,
        st.session_state[CODE_CHANGE_PROPOSAL_KEY],
    )


def set_code_change_proposal(proposal: CodeChangeProposal) -> None:
    st.session_state[CODE_CHANGE_PROPOSAL_KEY] = proposal


def clear_code_change_proposal() -> None:
    st.session_state[CODE_CHANGE_PROPOSAL_KEY] = None


def get_code_change_receipt() -> CodeChangeReceipt | None:
    return cast(
        CodeChangeReceipt | None,
        st.session_state[CODE_CHANGE_RECEIPT_KEY],
    )


def get_code_change_rollback_receipt() -> CodeChangeRollbackReceipt | None:
    return cast(
        CodeChangeRollbackReceipt | None,
        st.session_state[CODE_CHANGE_ROLLBACK_RECEIPT_KEY],
    )


def set_code_change_applied(
    project: CodeProject,
    receipt: CodeChangeReceipt,
) -> None:
    """Refresh the changed project and invalidate stale code-linked state."""

    st.session_state[OPENED_CODE_PROJECT_KEY] = project
    st.session_state[CURRENT_CODE_SELECTION_KEY] = None
    st.session_state[CURRENT_CODE_RESPONSE_KEY] = None
    st.session_state[CURRENT_CODE_RESPONSE_QUESTION_KEY] = None
    _clear_current_code_note()
    st.session_state[CODE_CHANGE_PROPOSAL_KEY] = None
    st.session_state[CODE_CHANGE_RECEIPT_KEY] = receipt
    st.session_state[CODE_CHANGE_ROLLBACK_RECEIPT_KEY] = None
    st.session_state[EVIDENCE_LINKS_KEY] = []
    st.session_state[CURRENT_NOTE_KEY] = None
    st.session_state[LAST_SAVED_PATH_KEY] = None
    _clear_read_only_assistant_session()


def set_code_change_rolled_back(
    project: CodeProject,
    receipt: CodeChangeRollbackReceipt,
) -> None:
    """Refresh the restored project and close the one-shot rollback action."""

    st.session_state[OPENED_CODE_PROJECT_KEY] = project
    st.session_state[CURRENT_CODE_SELECTION_KEY] = None
    st.session_state[CURRENT_CODE_RESPONSE_KEY] = None
    st.session_state[CURRENT_CODE_RESPONSE_QUESTION_KEY] = None
    _clear_current_code_note()
    st.session_state[CODE_CHANGE_PROPOSAL_KEY] = None
    st.session_state[CODE_CHANGE_RECEIPT_KEY] = None
    st.session_state[CODE_CHANGE_ROLLBACK_RECEIPT_KEY] = receipt
    st.session_state[EVIDENCE_LINKS_KEY] = []
    st.session_state[CURRENT_NOTE_KEY] = None
    st.session_state[LAST_SAVED_PATH_KEY] = None
    _clear_read_only_assistant_session()


def get_code_change_audit() -> list[CodeChangeAuditEvent]:
    return list(
        cast(
            list[CodeChangeAuditEvent],
            st.session_state[CODE_CHANGE_AUDIT_KEY],
        )
    )


def append_code_change_audit(event: CodeChangeAuditEvent) -> None:
    events = get_code_change_audit()
    events.append(event)
    st.session_state[CODE_CHANGE_AUDIT_KEY] = events


def get_evidence_links() -> list[EvidenceLink]:
    return list(
        cast(list[EvidenceLink], st.session_state[EVIDENCE_LINKS_KEY])
    )


def set_evidence_links(links: list[EvidenceLink]) -> None:
    st.session_state[EVIDENCE_LINKS_KEY] = list(links)
    st.session_state[CURRENT_NOTE_KEY] = None
    st.session_state[LAST_SAVED_PATH_KEY] = None
    _clear_read_only_assistant_session()


def get_read_only_assistant_session() -> ReadOnlyAssistantSession | None:
    return cast(
        ReadOnlyAssistantSession | None,
        st.session_state[READ_ONLY_ASSISTANT_SESSION_KEY],
    )


def set_read_only_assistant_session(
    session: ReadOnlyAssistantSession,
) -> None:
    st.session_state[READ_ONLY_ASSISTANT_SESSION_KEY] = session


def _required_conversation() -> Conversation:
    conversation = get_current_conversation()
    if conversation is None:
        raise ValueError("Open a PDF before starting a conversation.")
    return conversation


def _clear_read_only_assistant_session() -> None:
    st.session_state[READ_ONLY_ASSISTANT_SESSION_KEY] = None


def _clear_current_code_note() -> None:
    st.session_state[CURRENT_CODE_NOTE_KEY] = None
    st.session_state[LAST_CODE_NOTE_SAVED_PATH_KEY] = None
