"""Document metadata model."""

from dataclasses import dataclass
from pathlib import Path


@dataclass
class Document:
    """A document opened in the current ResearchMind session."""

    id: str
    title: str
    authors: list[str]
    source_type: str
    path: Path
    num_pages: int
