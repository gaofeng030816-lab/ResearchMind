"""Context model used to ground AI explanation and follow-up tasks."""

from dataclasses import dataclass, field

from researchmind.models.message import Message


@dataclass
class ResearchContext:
    """The minimum relevant context for one research-aware AI call."""

    selected_text: str
    surrounding_text: str
    document_id: str
    document_title: str
    author: str
    source: str
    user_question: str
    page_number: int | None = None
    conversation_history: list[Message] = field(default_factory=list)
