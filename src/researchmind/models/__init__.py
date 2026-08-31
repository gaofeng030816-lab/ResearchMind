"""Shared, framework-independent ResearchMind data models."""

from researchmind.models.conversation import Conversation
from researchmind.models.code_change import (
    CodeChangeAuditAction,
    CodeChangeAuditEvent,
    CodeChangeAuditStatus,
    CodeChangeProposal,
    CodeChangeReceipt,
    CodeChangeRollbackReceipt,
    CodeFileSnapshot,
)
from researchmind.models.code_context import (
    CodeContext,
    CodeFile,
    CodeFileStatus,
    CodeProject,
    CodeProjectSummary,
    CodeSymbol,
)
from researchmind.models.code_selection import (
    CodeExtractionMethod,
    CodeSelection,
    CodeSymbolKind,
)
from researchmind.models.document import Document
from researchmind.models.evidence_link import (
    CodeEvidenceReference,
    EvidenceGenerationMethod,
    EvidenceLink,
    EvidenceRelation,
    PaperEvidenceKind,
    PaperEvidenceReference,
)
from researchmind.models.figure_region import FigureRegion
from researchmind.models.knowledge_note import KnowledgeNote
from researchmind.models.maintenance import (
    ConfigurationCheck,
    ConfigurationReport,
    DiagnosticStatus,
    MarkdownBackupResult,
    MarkdownRestoreResult,
)
from researchmind.models.message import Message, MessageRole, MessageTask
from researchmind.models.page import Page
from researchmind.models.reading_selection import ReadingSelection
from researchmind.models.read_only_assistant import (
    AssistantAction,
    AssistantActionName,
    AssistantAuditEvent,
    AssistantAuditStatus,
    AssistantStatus,
    AssistantStopReason,
    AssistantToolName,
    AssistantToolResult,
    AssistantToolStatus,
    ReadOnlyAssistantSession,
)
from researchmind.models.research_context import ResearchContext
from researchmind.models.text_block import BoundingBox, TextBlock, TextBlockRole

__all__ = [
    "BoundingBox",
    "CodeChangeAuditAction",
    "CodeChangeAuditEvent",
    "CodeChangeAuditStatus",
    "CodeChangeProposal",
    "CodeChangeReceipt",
    "CodeChangeRollbackReceipt",
    "CodeContext",
    "CodeExtractionMethod",
    "CodeFile",
    "CodeFileSnapshot",
    "CodeFileStatus",
    "CodeProject",
    "CodeProjectSummary",
    "CodeSelection",
    "CodeSymbol",
    "CodeSymbolKind",
    "Conversation",
    "Document",
    "CodeEvidenceReference",
    "EvidenceGenerationMethod",
    "EvidenceLink",
    "EvidenceRelation",
    "FigureRegion",
    "KnowledgeNote",
    "ConfigurationCheck",
    "ConfigurationReport",
    "DiagnosticStatus",
    "MarkdownBackupResult",
    "MarkdownRestoreResult",
    "Message",
    "MessageRole",
    "MessageTask",
    "Page",
    "PaperEvidenceKind",
    "PaperEvidenceReference",
    "ReadingSelection",
    "AssistantAction",
    "AssistantActionName",
    "AssistantAuditEvent",
    "AssistantAuditStatus",
    "AssistantStatus",
    "AssistantStopReason",
    "AssistantToolName",
    "AssistantToolResult",
    "AssistantToolStatus",
    "ReadOnlyAssistantSession",
    "ResearchContext",
    "TextBlock",
    "TextBlockRole",
]
