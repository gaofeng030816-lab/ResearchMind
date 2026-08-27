"""Framework-independent ResearchMind domain rules."""
"""Pure domain rules for selections, context assembly, and conversations."""

from researchmind.core.conversation import trim_conversation_history
from researchmind.core.research_context import build_research_context
from researchmind.core.selection import locate_selection

__all__ = [
    "build_research_context",
    "locate_selection",
    "trim_conversation_history",
]
