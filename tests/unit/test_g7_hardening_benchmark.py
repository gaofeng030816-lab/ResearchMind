"""Deterministic coverage for the G7 persistence benchmark harness."""

import importlib.util
from pathlib import Path
import sys

import pytest


def test_g7_benchmark_uses_bounded_persistent_operations() -> None:
    module = _load_benchmark_module()

    result = module.run_benchmark(library_records=3, note_drafts=4)

    assert result["passed"] is True
    assert result["inputs"] == {"library_records": 3, "note_drafts": 4}
    assert [item["name"] for item in result["metrics"]] == [
        "library_population",
        "draft_population",
        "library_and_draft_list",
        "library_backup",
        "library_restore",
    ]


def test_g7_benchmark_rejects_non_positive_workloads() -> None:
    module = _load_benchmark_module()

    with pytest.raises(ValueError, match="positive"):
        module.run_benchmark(library_records=0, note_drafts=1)


def _load_benchmark_module() -> object:
    path = (
        Path(__file__).parents[2]
        / "evaluations"
        / "g7"
        / "hardening_benchmark.py"
    )
    spec = importlib.util.spec_from_file_location(
        "g7_hardening_benchmark",
        path,
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module
