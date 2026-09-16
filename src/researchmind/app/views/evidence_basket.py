"""Streamlit evidence-basket view for one durable V3 note draft."""

from __future__ import annotations

import streamlit as st

from researchmind.app import state, use_cases
from researchmind.models import EvidenceSnapshot, NoteDraft


_KIND_LABELS = {
    "source_text": "原文",
    "translation": "译文",
    "latex": "LaTeX",
    "question": "问题",
    "answer": "回答",
    "code": "代码",
}
_SOURCE_STATE_LABELS = {
    "current": "来源修订仍为当前版本",
    "stale": "来源已有新修订或已移除",
    "detached": "会话来源，未绑定资料库修订",
}


def render_evidence_basket() -> None:
    """Render only evidence that the user explicitly added to a draft."""

    st.subheader("3. 笔记证据篮")
    draft = state.get_current_note_draft()
    if draft is None:
        st.caption(
            "尚未建立草稿。点击上方“加入原文到证据篮”或"
            "“加入译文到证据篮”后才会持久化；当前对话不会自动进入。"
        )
        return

    try:
        evidence = use_cases.list_note_evidence(draft.id)
    except use_cases.USER_FACING_ERRORS as exc:
        st.error(str(exc))
        return

    st.caption(
        f"草稿：{draft.title} · 修订 {draft.revision}。"
        "这里的改动只写入 ResearchMind 本地资料库，不会写入 Obsidian。"
    )
    if not evidence:
        st.info("草稿已建立，但证据篮还是空的。")
        return

    for index, snapshot in enumerate(evidence):
        _render_evidence_item(draft, evidence, index, snapshot)


def _render_evidence_item(
    draft: NoteDraft,
    evidence: list[EvidenceSnapshot],
    index: int,
    snapshot: EvidenceSnapshot,
) -> None:
    try:
        source_state = use_cases.note_evidence_source_state(snapshot)
    except use_cases.USER_FACING_ERRORS as exc:
        st.error(str(exc))
        return

    with st.container(border=True):
        st.markdown(
            f"**{index + 1}. {_KIND_LABELS.get(snapshot.kind, snapshot.kind)}**"
        )
        st.caption(
            f"{snapshot.source_label} · {_SOURCE_STATE_LABELS[source_state]}"
        )
        excerpt = snapshot.content
        if len(excerpt) > 2_000:
            excerpt = f"{excerpt[:2_000]}\n…（内容已截断显示）"
        st.text(excerpt)

        included = st.checkbox(
            "纳入后续 Markdown 草稿",
            value=snapshot.included,
            key=(
                f"note_evidence_included_{snapshot.id}_"
                f"revision_{draft.revision}"
            ),
        )
        if included != snapshot.included:
            try:
                updated, _stored = use_cases.set_note_evidence_included(
                    draft.id,
                    snapshot.id,
                    included=included,
                    expected_draft_revision=draft.revision,
                )
                state.set_current_note_draft(updated)
                st.rerun()
            except use_cases.USER_FACING_ERRORS as exc:
                st.error(str(exc))

        with st.container(horizontal=True):
            if st.button(
                "上移",
                key=f"note_evidence_up_{snapshot.id}",
                disabled=index == 0,
            ):
                _move_evidence(draft, evidence, index, index - 1)
            if st.button(
                "下移",
                key=f"note_evidence_down_{snapshot.id}",
                disabled=index == len(evidence) - 1,
            ):
                _move_evidence(draft, evidence, index, index + 1)
            if st.button(
                "从证据篮移除",
                key=f"note_evidence_remove_{snapshot.id}",
            ):
                try:
                    updated = use_cases.remove_note_evidence(
                        draft.id,
                        snapshot.id,
                        expected_draft_revision=draft.revision,
                    )
                    state.set_current_note_draft(updated)
                    st.rerun()
                except use_cases.USER_FACING_ERRORS as exc:
                    st.error(str(exc))


def _move_evidence(
    draft: NoteDraft,
    evidence: list[EvidenceSnapshot],
    source_index: int,
    target_index: int,
) -> None:
    evidence_ids = [item.id for item in evidence]
    evidence_ids[source_index], evidence_ids[target_index] = (
        evidence_ids[target_index],
        evidence_ids[source_index],
    )
    try:
        updated, _ordered = use_cases.reorder_note_evidence(
            draft.id,
            evidence_ids,
            expected_draft_revision=draft.revision,
        )
        state.set_current_note_draft(updated)
        st.rerun()
    except use_cases.USER_FACING_ERRORS as exc:
        st.error(str(exc))
