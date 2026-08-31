"""Project-owned models for the bounded T5-A read-only assistant."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4


AssistantToolName = Literal[
    "inspect_paper_context",
    "inspect_code_context",
    "inspect_evidence_links",
]
AssistantActionName = Literal[
    "inspect_paper_context",
    "inspect_code_context",
    "inspect_evidence_links",
    "final",
]
AssistantStatus = Literal[
    "ready",
    "awaiting_user",
    "completed",
    "stopped",
]
AssistantToolStatus = Literal["available", "unavailable"]
AssistantAuditStatus = Literal["tool_completed", "final", "stopped"]
AssistantStopReason = Literal[
    "user_stopped",
    "invalid_protocol",
    "repeated_tool",
    "tool_budget",
    "llm_budget",
    "tool_output_budget",
    "provider_error",
    "tool_error",
]


@dataclass(frozen=True)
class AssistantAction:
    """One strictly parsed model action."""

    action: AssistantActionName
    answer: str | None = None


@dataclass(frozen=True)
class AssistantToolResult:
    """One local read-only result waiting to be sent on user continuation."""

    tool_name: AssistantToolName
    status: AssistantToolStatus
    source_summary: str
    content: str

    @property
    def character_count(self) -> int:
        return len(self.content)


@dataclass(frozen=True)
class AssistantAuditEvent:
    """Non-sensitive metadata for one model or user-controlled step."""

    step_number: int
    requested_action: str
    executed_tool: AssistantToolName | None
    status: AssistantAuditStatus
    request_character_count: int
    response_character_count: int
    tool_output_character_count: int
    stop_reason: AssistantStopReason | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class ReadOnlyAssistantSession:
    """One bounded, user-stepped assistant run held only in session memory."""

    question: str
    status: AssistantStatus
    tool_results: tuple[AssistantToolResult, ...] = ()
    audit_log: tuple[AssistantAuditEvent, ...] = ()
    tool_call_count: int = 0
    llm_call_count: int = 0
    final_answer: str | None = None
    stop_reason: AssistantStopReason | None = None
    last_error: str | None = None
    id: str = field(default_factory=lambda: uuid4().hex)
