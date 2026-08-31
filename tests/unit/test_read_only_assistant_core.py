"""Pure budget and state tests for the T5-A assistant."""

from dataclasses import replace

import pytest

from researchmind.core import (
    MAX_ASSISTANT_QUESTION_CHARS,
    MAX_ASSISTANT_TOOL_CALLS,
    MAX_ASSISTANT_TOOL_OUTPUT_CHARS,
    MAX_ASSISTANT_TOTAL_TOOL_OUTPUT_CHARS,
    create_read_only_assistant_session,
    record_assistant_tool_step,
    tool_output_stop_reason,
    tool_request_stop_reason,
)
from researchmind.models import AssistantAction, AssistantToolResult


def test_create_assistant_session_rejects_blank_or_oversized_question() -> None:
    with pytest.raises(ValueError):
        create_read_only_assistant_session("   ")
    with pytest.raises(ValueError):
        create_read_only_assistant_session(
            "x" * (MAX_ASSISTANT_QUESTION_CHARS + 1)
        )


def test_tool_request_rule_rejects_repeat_and_hard_call_limit() -> None:
    session = create_read_only_assistant_session("Inspect current evidence.")
    result = AssistantToolResult(
        tool_name="inspect_paper_context",
        status="available",
        source_summary="paper page 1",
        content="bounded evidence",
    )
    session = record_assistant_tool_step(
        session,
        AssistantAction(action="inspect_paper_context"),
        result,
        request_character_count=100,
        response_character_count=50,
    )

    assert (
        tool_request_stop_reason(session, "inspect_paper_context")
        == "repeated_tool"
    )
    at_limit = replace(session, tool_call_count=MAX_ASSISTANT_TOOL_CALLS)
    assert (
        tool_request_stop_reason(at_limit, "inspect_code_context")
        == "tool_budget"
    )


def test_tool_output_rule_rejects_one_oversized_result() -> None:
    session = create_read_only_assistant_session("Inspect current evidence.")
    oversized = AssistantToolResult(
        tool_name="inspect_paper_context",
        status="available",
        source_summary="paper page 1",
        content="x" * (MAX_ASSISTANT_TOOL_OUTPUT_CHARS + 1),
    )

    assert tool_output_stop_reason(session, oversized) == "tool_output_budget"


def test_tool_output_rule_rejects_total_budget_overflow() -> None:
    session = create_read_only_assistant_session("Inspect current evidence.")
    first = AssistantToolResult(
        tool_name="inspect_paper_context",
        status="available",
        source_summary="paper",
        content="p" * MAX_ASSISTANT_TOOL_OUTPUT_CHARS,
    )
    second = AssistantToolResult(
        tool_name="inspect_code_context",
        status="available",
        source_summary="code",
        content="c" * MAX_ASSISTANT_TOOL_OUTPUT_CHARS,
    )
    for action, result in (
        (AssistantAction(action="inspect_paper_context"), first),
        (AssistantAction(action="inspect_code_context"), second),
    ):
        session = record_assistant_tool_step(
            session,
            action,
            result,
            request_character_count=100,
            response_character_count=50,
        )
    overflow = AssistantToolResult(
        tool_name="inspect_evidence_links",
        status="available",
        source_summary="links",
        content="x",
    )

    assert sum(
        item.character_count for item in session.tool_results
    ) == MAX_ASSISTANT_TOTAL_TOOL_OUTPUT_CHARS
    assert tool_output_stop_reason(session, overflow) == "tool_output_budget"


def test_audit_records_metadata_without_tool_payload() -> None:
    session = create_read_only_assistant_session("Inspect current evidence.")
    sensitive_content = "private source evidence"
    result = AssistantToolResult(
        tool_name="inspect_code_context",
        status="available",
        source_summary="project:module.py:1-2",
        content=sensitive_content,
    )
    session = record_assistant_tool_step(
        session,
        AssistantAction(action="inspect_code_context"),
        result,
        request_character_count=120,
        response_character_count=60,
    )

    audit = session.audit_log[0]
    assert audit.tool_output_character_count == len(sensitive_content)
    assert sensitive_content not in repr(audit)
