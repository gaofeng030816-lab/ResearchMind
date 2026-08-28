"""Shared, framework-independent ResearchMind data models."""

from researchmind.models.conversation import Conversation
from researchmind.models.document import Document
from researchmind.models.figure_region import FigureRegion
from researchmind.models.knowledge_note import KnowledgeNote
from researchmind.models.message import Message, MessageRole, MessageTask
from researchmind.models.page import Page
from researchmind.models.reading_selection import ReadingSelection
from researchmind.models.research_context import ResearchContext
from researchmind.models.text_block import BoundingBox, TextBlock, TextBlockRole

__all__ = [
    "BoundingBox",
    "Conversation",
    "Document",
    "FigureRegion",
    "KnowledgeNote",
    "Message",
    "MessageRole",
    "MessageTask",
    "Page",
    "ReadingSelection",
    "ResearchContext",
    "TextBlock",
    "TextBlockRole",
]
