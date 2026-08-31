"""Small deterministic coverage for the T6-C benchmark harness."""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


def test_t6_c_benchmark_uses_expected_bounded_operations() -> None:
    module = _load_benchmark_module()

    result = module.run_benchmark(
        pdf_pages=3,
        code_files=5,
        markdown_notes=4,
    )

    assert result["passed"] is True
    assert result["inputs"] == {
        "pdf_pages": 3,
        "code_files": 5,
        "markdown_notes": 4,
    }
    assert [metric["name"] for metric in result["metrics"]] == [
        "configuration_diagnostics",
        "pdf_open_and_extract",
        "pdf_render_first_page",
        "code_index",
        "markdown_backup",
        "markdown_restore",
    ]


def test_t6_c_benchmark_rejects_non_positive_workloads() -> None:
    module = _load_benchmark_module()

    with pytest.raises(ValueError, match="must be positive"):
        module.run_benchmark(pdf_pages=0, code_files=1, markdown_notes=1)


def _load_benchmark_module() -> object:
    path = (
        Path(__file__).parents[2]
        / "evaluations"
        / "t6_c"
        / "benchmark.py"
    )
    spec = importlib.util.spec_from_file_location("t6_c_benchmark", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
    return module
