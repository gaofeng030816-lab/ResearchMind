"""Centralized Streamlit session-state access and mutation."""

from __future__ import annotations

from pathlib import Path
from typing import cast

import streamlit as st

from researchmind.models import (
    Conversation,
    KnowledgeNote,
    Message,
    MessageTask,
    ReadingSelection,
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


def get_current_selection() -> ReadingSelection | None:
    return cast(ReadingSelection | None, st.session_state[CURRENT_SELECTION_KEY])


def set_current_selection(selection: ReadingSelection) -> None:
    st.session_state[CURRENT_SELECTION_KEY] = selection
    st.session_state[CURRENT_NOTE_KEY] = None
    st.session_state[LAST_SAVED_PATH_KEY] = None


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


def _required_conversation() -> Conversation:
    conversation = get_current_conversation()
    if conversation is None:
        raise ValueError("Open a PDF before starting a conversation.")
    return conversation
