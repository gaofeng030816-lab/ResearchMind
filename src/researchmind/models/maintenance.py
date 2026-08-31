"""Project-owned results for local configuration and data maintenance."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal


DiagnosticStatus = Literal["ok", "warning", "error"]


@dataclass(frozen=True)
class ConfigurationCheck:
    """One non-secret local preflight result."""

    code: str
    label: str
    status: DiagnosticStatus
    message: str


@dataclass(frozen=True)
class ConfigurationReport:
    """A safe configuration report that never contains credentials or paths."""

    checks: tuple[ConfigurationCheck, ...]

    @property
    def has_errors(self) -> bool:
        return any(check.status == "error" for check in self.checks)


@dataclass(frozen=True)
class MarkdownBackupResult:
    """Summary of one verified ResearchMind Markdown backup."""

    archive_path: Path
    note_count: int
    total_bytes: int


@dataclass(frozen=True)
class MarkdownRestoreResult:
    """Summary of one non-overwriting Markdown restore."""

    output_directory: Path
    note_count: int
    total_bytes: int
