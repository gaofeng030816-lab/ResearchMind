"""Synthetic V3 library, draft, backup, and restore performance gate."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from dataclasses import asdict, dataclass
import json
from pathlib import Path
import platform
import tempfile
from time import perf_counter

from researchmind.app import use_cases
from researchmind.config import Settings
from researchmind.models import UploadedFileData


@dataclass(frozen=True)
class Metric:
    """One local elapsed-time measurement with a generous blocking limit."""

    name: str
    elapsed_seconds: float
    limit_seconds: float

    @property
    def passed(self) -> bool:
        return self.elapsed_seconds <= self.limit_seconds


def run_benchmark(
    *,
    library_records: int = 250,
    note_drafts: int = 250,
) -> dict[str, object]:
    """Measure V3 persistence using only temporary synthetic files."""

    if library_records <= 0 or note_drafts <= 0:
        raise ValueError("Benchmark input counts must be positive.")

    with tempfile.TemporaryDirectory(prefix="researchmind-g7-") as raw_root:
        root = Path(raw_root)
        settings = Settings(researchmind_data_dir=root / "library")
        metrics: list[Metric] = []

        metrics.append(
            _measure(
                "library_population",
                lambda: _populate_library(settings, library_records),
                limit_seconds=20.0,
            )
        )
        metrics.append(
            _measure(
                "draft_population",
                lambda: _populate_drafts(settings, note_drafts),
                limit_seconds=10.0,
            )
        )

        listed: tuple[int, int] = (0, 0)

        def list_persistent_state() -> None:
            nonlocal listed
            listed = (
                len(use_cases.list_library_entries(settings=settings)),
                len(use_cases.list_note_drafts(settings=settings)),
            )

        metrics.append(
            _measure(
                "library_and_draft_list",
                list_persistent_state,
                limit_seconds=2.0,
            )
        )
        if listed != (library_records, note_drafts):
            raise RuntimeError("Persistent library counts are inconsistent.")

        archive = root / "library-backup.zip"
        metrics.append(
            _measure(
                "library_backup",
                lambda: use_cases.backup_local_library(
                    archive,
                    settings=settings,
                ),
                limit_seconds=10.0,
            )
        )
        restored_root = root / "restored-library"
        metrics.append(
            _measure(
                "library_restore",
                lambda: use_cases.restore_local_library_backup(
                    archive,
                    restored_root,
                    settings=settings,
                ),
                limit_seconds=10.0,
            )
        )
        restored = Settings(researchmind_data_dir=restored_root)
        restored_counts = (
            len(use_cases.list_library_entries(settings=restored)),
            len(use_cases.list_note_drafts(settings=restored)),
        )
        if restored_counts != listed:
            raise RuntimeError("Restored library counts are inconsistent.")

    return {
        "schema_version": 1,
        "python": platform.python_version(),
        "platform": platform.platform(),
        "inputs": {
            "library_records": library_records,
            "note_drafts": note_drafts,
        },
        "passed": all(metric.passed for metric in metrics),
        "metrics": [
            {**asdict(metric), "passed": metric.passed}
            for metric in metrics
        ],
    }


def _populate_library(settings: Settings, count: int) -> None:
    for index in range(count):
        use_cases.import_code_directory_to_library(
            [
                UploadedFileData(
                    name=f"project-{index:04d}/main.py",
                    content=(
                        f"def value_{index}() -> int:\n"
                        f"    return {index}\n"
                    ).encode("utf-8"),
                )
            ],
            settings=settings,
        )


def _populate_drafts(settings: Settings, count: int) -> None:
    for index in range(count):
        use_cases.create_note_draft(
            f"Synthetic draft {index}",
            body_markdown=f"## Evidence\n\nSynthetic item {index}.\n",
            settings=settings,
        )


def _measure(
    name: str,
    operation: Callable[[], object],
    *,
    limit_seconds: float,
) -> Metric:
    started = perf_counter()
    operation()
    return Metric(
        name=name,
        elapsed_seconds=round(perf_counter() - started, 6),
        limit_seconds=limit_seconds,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library-records", type=int, default=250)
    parser.add_argument("--note-drafts", type=int, default=250)
    args = parser.parse_args()
    result = run_benchmark(
        library_records=args.library_records,
        note_drafts=args.note_drafts,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
