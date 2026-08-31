"""Pure state and budget rules for the T5-A read-only assistant."""

from __future__ import annotations

from dataclasses import replace

from researchmind.models import (
    AssistantAction,
    AssistantAuditEvent,
    AssistantStopReason,
    AssistantToolName,
    AssistantToolResult,
    ReadOnlyAssistantSession,
)


MAX_ASSISTANT_QUESTION_CHARS = 2_000
MAX_ASSISTANT_TOOL_CALLS = 3
MAX_ASSISTANT_LLM_CALLS = 4
MAX_ASSISTANT_TOOL_OUTPUT_CHARS = 16_000
MAX_ASSISTANT_TOTAL_TOOL_OUTPUT_CHARS = 32_000


def create_read_only_assistant_session(
    question: str,
) -> ReadOnlyAssistantSession:
    """Create a ready session from one bounded user question."""

    normalized = question.strip()
    if not normalized:
        raise ValueError("Read-only assistant question must not be blank.")
    if len(normalized) > MAX_ASSISTANT_QUESTION_CHARS:
        raise ValueError(
            "Read-only assistant question must not exceed "
            f"{MAX_ASSISTANT_QUESTION_CHARS:,} characters."
        )
    return ReadOnlyAssistantSession(question=normalized, status="ready")


def tool_request_stop_reason(
    session: ReadOnlyAssistantSession,
    tool_name: AssistantToolName,
) -> AssistantStopReason | None:
    """Return the policy stop reason for one requested tool, if any."""

    if any(result.tool_name == tool_name for result in session.tool_results):
        return "repeated_tool"
    if session.tool_call_count >= MAX_ASSISTANT_TOOL_CALLS:
        return "tool_budget"
    return None


def tool_output_stop_reason(
    session: ReadOnlyAssistantSession,
    result: AssistantToolResult,
) -> AssistantStopReason | None:
    """Enforce per-result and total hard character limits."""

    if result.character_count > MAX_ASSISTANT_TOOL_OUTPUT_CHARS:
        return "tool_output_budget"
    total = sum(item.character_count for item in session.tool_results)
    if total + result.character_count > MAX_ASSISTANT_TOTAL_TOOL_OUTPUT_CHARS:
        return "tool_output_budget"
    return None


def record_assistant_tool_step(
    session: ReadOnlyAssistantSession,
    action: AssistantAction,
    result: AssistantToolResult,
    *,
    request_character_count: int,
    response_character_count: int,
) -> ReadOnlyAssistantSession:
    """Append one successfully executed read-only tool step."""

    if action.action == "final":
        raise ValueError("A final action cannot record a tool result.")
    audit = AssistantAuditEvent(
        step_number=len(session.audit_log) + 1,
        requested_action=action.action,
        executed_tool=result.tool_name,
        status="tool_completed",
        request_character_count=request_character_count,
        response_character_count=response_character_count,
        tool_output_character_count=result.character_count,
    )
    return replace(
        session,
        status="awaiting_user",
        tool_results=(*session.tool_results, result),
        audit_log=(*session.audit_log, audit),
        tool_call_count=session.tool_call_count + 1,
        llm_call_count=session.llm_call_count + 1,
        last_error=None,
    )


def record_assistant_final_step(
    session: ReadOnlyAssistantSession,
    action: AssistantAction,
    *,
    request_character_count: int,
    response_character_count: int,
) -> ReadOnlyAssistantSession:
    """Complete a session from one strictly parsed final answer."""

    if action.action != "final" or action.answer is None:
        raise ValueError("A final assistant action with an answer is required.")
    audit = AssistantAuditEvent(
        step_number=len(session.audit_log) + 1,
        requested_action="final",
        executed_tool=None,
        status="final",
        request_character_count=request_character_count,
        response_character_count=response_character_count,
        tool_output_character_count=0,
    )
    return replace(
        session,
        status="completed",
        audit_log=(*session.audit_log, audit),
        llm_call_count=session.llm_call_count + 1,
        final_answer=action.answer,
        stop_reason=None,
        last_error=None,
    )


def stop_read_only_assistant_session(
    session: ReadOnlyAssistantSession,
    *,
    stop_reason: AssistantStopReason,
    requested_action: str,
    error_message: str | None = None,
    request_character_count: int = 0,
    response_character_count: int = 0,
    llm_call_increment: int = 0,
) -> ReadOnlyAssistantSession:
    """Stop one session with an auditable, non-sensitive reason."""

    audit = AssistantAuditEvent(
        step_number=len(session.audit_log) + 1,
        requested_action=requested_action,
        executed_tool=None,
        status="stopped",
        request_character_count=request_character_count,
        response_character_count=response_character_count,
        tool_output_character_count=0,
        stop_reason=stop_reason,
    )
    return replace(
        session,
        status="stopped",
        audit_log=(*session.audit_log, audit),
        llm_call_count=session.llm_call_count + llm_call_increment,
        stop_reason=stop_reason,
        last_error=error_message,
    )
