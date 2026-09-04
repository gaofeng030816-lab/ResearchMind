"""Reproducible local T6-C performance checks with synthetic safe data."""

from __future__ import annotations

import argparse
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
import gc
import json
from pathlib import Path
import platform
import tempfile
from time import perf_counter
import tracemalloc
from typing import TypeVar

import pymupdf

from researchmind.code import open_code_project
from researchmind.config import Settings
from researchmind.integration.obsidian import (
    create_markdown_backup,
    restore_markdown_backup,
)
from researchmind.maintenance import inspect_settings
from researchmind.pdf import open_pdf, render_page_image


_T = TypeVar("_T")


@dataclass(frozen=True)
class BenchmarkMetric:
    """One measured operation and its deliberately generous local limit."""

    name: str
    elapsed_seconds: float
    limit_seconds: float
    peak_mib: float
    peak_limit_mib: float

    @property
    def passed(self) -> bool:
        return (
            self.elapsed_seconds <= self.limit_seconds
            and self.peak_mib <= self.peak_limit_mib
        )


def run_benchmark(
    *,
    pdf_pages: int = 100,
    code_files: int = 2_000,
    markdown_notes: int = 1_000,
) -> dict[str, object]:
    """Measure bounded PDF, code, configuration, and recovery workloads."""

    _require_positive(pdf_pages, code_files, markdown_notes)
    with tempfile.TemporaryDirectory(prefix="researchmind-t6c-") as raw_directory:
        root = Path(raw_directory)
        vault = root / "vault"
        vault.mkdir()
        pdf_path = root / "synthetic-100-pages.pdf"
        code_root = root / "code-project"
        note_root = vault / "ResearchMind"
        _create_pdf(pdf_path, page_count=pdf_pages)
        _create_code_project(code_root, file_count=code_files)
        _create_markdown_notes(note_root, note_count=markdown_notes)

        metrics: list[BenchmarkMetric] = []
        _, metric = _measure(
            "configuration_diagnostics",
            lambda: inspect_settings(
                Settings(
                    llm_base_url="https://example.invalid/v1",
                    llm_api_key="benchmark-placeholder",
                    llm_model="benchmark-model",
                    obsidian_vault_path=vault,
                )
            ),
            limit_seconds=0.25,
            peak_limit_mib=32.0,
        )
        metrics.append(metric)

        opened, metric = _measure(
            "pdf_open_and_extract",
            lambda: open_pdf(pdf_path),
            limit_seconds=5.0,
            peak_limit_mib=256.0,
        )
        metrics.append(metric)
        rendered, metric = _measure(
            "pdf_render_first_page",
            lambda: render_page_image(opened, 1, zoom=1.5),
            limit_seconds=2.0,
            peak_limit_mib=128.0,
        )
        if not rendered.startswith(b"\x89PNG"):
            raise RuntimeError("PDF render benchmark did not produce PNG data.")
        metrics.append(metric)

        project, metric = _measure(
            "code_index",
            lambda: open_code_project(code_root),
            limit_seconds=20.0,
            peak_limit_mib=256.0,
        )
        if len(project.files) != code_files:
            raise RuntimeError("Code benchmark did not index the expected files.")
        metrics.append(metric)

        archive = root / "researchmind-notes.zip"
        memory_archive = root / "researchmind-notes-memory.zip"
        backup, metric = _measure(
            "markdown_backup",
            lambda: create_markdown_backup(
                vault_path=vault,
                subdirectory="ResearchMind",
                archive_path=archive,
            ),
            memory_operation=lambda: create_markdown_backup(
                vault_path=vault,
                subdirectory="ResearchMind",
                archive_path=memory_archive,
            ),
            limit_seconds=10.0,
            peak_limit_mib=256.0,
        )
        if backup.note_count != markdown_notes:
            raise RuntimeError("Backup benchmark note count is inconsistent.")
        metrics.append(metric)

        restored, metric = _measure(
            "markdown_restore",
            lambda: restore_markdown_backup(
                archive_path=archive,
                vault_path=vault,
                subdirectory="ResearchMind-Recovered",
            ),
            memory_operation=lambda: restore_markdown_backup(
                archive_path=memory_archive,
                vault_path=vault,
                subdirectory="ResearchMind-Recovered-Memory",
            ),
            limit_seconds=5.0,
            peak_limit_mib=256.0,
        )
        if restored.note_count != markdown_notes:
            raise RuntimeError("Restore benchmark note count is inconsistent.")
        metrics.append(metric)

    return {
        "schema_version": 1,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "inputs": {
            "pdf_pages": pdf_pages,
            "code_files": code_files,
            "markdown_notes": markdown_notes,
        },
        "passed": all(metric.passed for metric in metrics),
        "metrics": [
            {**asdict(metric), "passed": metric.passed}
            for metric in metrics
        ],
    }


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf-pages", type=int, default=100)
    parser.add_argument("--code-files", type=int, default=2_000)
    parser.add_argument("--markdown-notes", type=int, default=1_000)
    args = parser.parse_args(argv)
    result = run_benchmark(
        pdf_pages=args.pdf_pages,
        code_files=args.code_files,
        markdown_notes=args.markdown_notes,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


def _measure(
    name: str,
    operation: Callable[[], _T],
    *,
    memory_operation: Callable[[], object] | None = None,
    limit_seconds: float,
    peak_limit_mib: float,
) -> tuple[_T, BenchmarkMetric]:
    started = perf_counter()
    result = operation()
    elapsed = round(perf_counter() - started, 6)
    gc.collect()
    tracemalloc.start()
    try:
        (memory_operation or operation)()
        _, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return result, BenchmarkMetric(
        name=name, elapsed_seconds=elapsed, limit_seconds=limit_seconds,
        peak_mib=round(peak_bytes / (1024 * 1024), 3),
        peak_limit_mib=peak_limit_mib,
    )


def _create_pdf(path: Path, *, page_count: int) -> None:
    with pymupdf.open() as document:
        for index in range(page_count):
            page = document.new_page()
            page.insert_text(
                (72, 72),
                f"ResearchMind T6-C synthetic page {index + 1} x = y + 1",
            )
        document.save(path)


def _create_code_project(root: Path, *, file_count: int) -> None:
    root.mkdir()
    for index in range(file_count):
        (root / f"module_{index:04d}.py").write_text(
            f"def value_{index}() -> int:\n    return {index}\n",
            encoding="utf-8",
        )


def _create_markdown_notes(root: Path, *, note_count: int) -> None:
    root.mkdir()
    for index in range(note_count):
        (root / f"note-{index:04d}.md").write_text(
            f"# Synthetic note {index}\n\nT6-C recovery fixture.\n",
            encoding="utf-8",
        )


def _require_positive(*values: int) -> None:
    if any(value <= 0 for value in values):
        raise ValueError("Benchmark input counts must be positive.")


if __name__ == "__main__":
    raise SystemExit(main())
