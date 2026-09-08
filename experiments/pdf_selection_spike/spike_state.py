"""Session mutation belongs here for the isolated app, never in production state."""

from dataclasses import dataclass, replace
from uuid import uuid4

import streamlit as st

from contract import PageSnapshot, Selection, validate_selection
from fixtures import make_snapshot

STATE_KEY = "g3_spike_session"
COMPONENT_KEY = "g3_selection_harness"


@dataclass(frozen=True)
class HarnessState:
    identity: tuple[str, int, int]
    snapshot: PageSnapshot
    last_sequence: int = 0
    selection: Selection | None = None
    error: str | None = None


def transition(state: HarnessState, event: object) -> HarnessState:
    try:
        selected = validate_selection(event, state.snapshot, last_sequence=state.last_sequence)
    except ValueError as exc:
        return replace(state, selection=None, error=str(exc))
    return replace(state, selection=selected, last_sequence=selected.sequence, error=None)


def configure(case: str, page: int, generation: int) -> HarnessState:
    identity = (case, page, generation)
    current = st.session_state.get(STATE_KEY)
    if current is None or current.identity != identity:
        current = HarnessState(identity, make_snapshot(case, page, uuid4().hex))
        st.session_state[STATE_KEY] = current
    return current


def receive_selection() -> None:
    event = st.session_state[COMPONENT_KEY].submitted
    current = st.session_state.get(STATE_KEY)
    if current is not None and event is not None:
        st.session_state[STATE_KEY] = transition(current, event)
