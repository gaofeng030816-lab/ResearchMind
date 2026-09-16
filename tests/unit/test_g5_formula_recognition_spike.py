"""Deterministic tests for the isolated V3-G5 quality gate."""

from __future__ import annotations

from base64 import b64encode
import hashlib
import json
from pathlib import Path

import pytest

from experiments.g5_formula_recognition.evaluation import (
    ADOPTION_THRESHOLDS,
    evaluate_predictions,
    load_manifest,
    normalize_latex,
    structural_signature,
    tokenize_latex,
    token_similarity,
)
from experiments.g5_formula_recognition.diagnose_real_paper_response import (
    _sanitize_response_structure,
)
from experiments.g5_formula_recognition.evaluate_real_paper_detector import (
    evaluate_detector,
)
from experiments.g5_formula_recognition.evaluate_real_paper_predictions import (
    evaluate_real_paper_predictions,
)
from experiments.g5_formula_recognition.fake_formula_server import FormulaHandler
from experiments.g5_formula_recognition.inspect_real_papers import (
    inspect_papers,
    parse_paper_spec,
)
from experiments.g5_formula_recognition.run_recognizer_case import (
    recognize_manifest_case,
    store_prediction,
)
from experiments.g5_formula_recognition.run_real_paper_recognizer import (
    AUTHORIZATION_RECORD,
    recognize_real_paper_case,
    store_real_prediction,
)
from researchmind.models import FormulaCrop
from researchmind.llm.latex import parse_latex_response


EXPERIMENT_DIR = (
    Path(__file__).resolve().parents[2]
    / "experiments"
    / "g5_formula_recognition"
)


def _perfect_predictions(manifest: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "predictions": [
            {
                "case_id": case["id"],
                "status": "ok",
                "latex": case["reference_latex"],
                "recognizer": "fake-perfect",
                "model_revision": "fixture-v1",
                "execution": "local",
                "elapsed_ms": 1.0,
            }
            for case in manifest["cases"]
        ],
    }


def test_manifest_has_hash_locked_twenty_case_corpus() -> None:
    manifest = load_manifest(EXPERIMENT_DIR / "corpus.json")

    assert len(manifest["cases"]) == 20
    categories = {
        category
        for case in manifest["cases"]
        for category in case["categories"]
    }
    assert {
        "integral", "sum", "limit", "fraction", "root", "greek",
        "subscript", "superscript", "matrix", "aligned", "equation_number",
    } <= categories
    for case in manifest["cases"]:
        crop = EXPERIMENT_DIR / case["crop_file"]
        assert crop.is_file()
        assert hashlib.sha256(crop.read_bytes()).hexdigest().upper() == case[
            "crop_sha256"
        ]


def test_candidate_audit_proves_no_legacy_runtime_was_adopted() -> None:
    audit = json.loads(
        (EXPERIMENT_DIR / "candidate_audit.json").read_text(encoding="utf-8")
    )

    assert audit["inspection"]["license"] == "GPL-3.0"
    assert audit["inspection"]["candidate_code_executed"] is False
    assert audit["inspection"]["dependencies_installed"] is False
    assert audit["inspection"]["files_copied_into_researchmind"] is False
    assert audit["inspection"]["data_submodule_present"] is False
    assert audit["inspection"]["model_weights_present"] is False


def test_local_candidate_audit_defers_unpinned_weight_runtime() -> None:
    audit = json.loads(
        (EXPERIMENT_DIR / "local_candidate_audit.json").read_text(encoding="utf-8")
    )

    assert audit["candidate"]["license"] == "MIT"
    assert len(audit["candidate"]["wheel_sha256"]) == 64
    assert audit["inspection"]["wheel_installed"] is False
    assert audit["inspection"]["candidate_code_executed"] is False
    assert audit["inspection"]["model_weights_downloaded"] is False
    assert audit["decision"]["production_adoption"] == "deferred"


def test_perfect_fixture_meets_predeclared_thresholds() -> None:
    manifest = load_manifest(EXPERIMENT_DIR / "corpus.json")
    result = evaluate_predictions(manifest, _perfect_predictions(manifest))

    assert result["thresholds"] == ADOPTION_THRESHOLDS
    assert result["adoption_thresholds_met"] is True
    assert all(result["threshold_checks"].values())


def test_normalization_is_conservative_and_token_metric_detects_symbol_loss() -> None:
    assert normalize_latex(r"\left( \dfrac{a}{b} \right)") == normalize_latex(
        r"(\frac{a}{b})"
    )
    assert token_similarity(r"\sum_{i=1}^{n}i", r"\sum_{i=1}^{n}") < 1.0


def test_scoring_treats_only_single_token_script_braces_as_equivalent() -> None:
    assert tokenize_latex(r"x_t+y^{2}+z_{\theta}") == tokenize_latex(
        r"x_{t}+y^2+z_\theta"
    )
    assert tokenize_latex(r"x_{ij}") != tokenize_latex(r"x_ij")
    assert tokenize_latex(r"x_{i+1}") != tokenize_latex(r"x_i+1")


def test_structure_metric_detects_flattened_matrix() -> None:
    reference = r"\begin{bmatrix}a&b\\c&d\end{bmatrix}"
    flattened = "a b c d"

    assert structural_signature(reference) != structural_signature(flattened)


def test_abstention_and_unsafe_latex_keep_gate_open() -> None:
    manifest = load_manifest(EXPERIMENT_DIR / "corpus.json")
    predictions = _perfect_predictions(manifest)
    predictions["predictions"][0].update(status="unreadable", latex=None)
    predictions["predictions"][1]["latex"] = r"\input{private}"

    result = evaluate_predictions(manifest, predictions)

    assert result["adoption_thresholds_met"] is False
    assert result["metrics"]["coverage"] == 0.95
    assert result["metrics"]["strict_valid_rate"] < 1.0
    assert result["cases"][1]["strict_valid"] is False


class _FakeCaseRecognizer:
    name = "fake-case-recognizer"
    model_revision = "fake-case-v1"
    execution = "remote"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def recognize(self, crop: FormulaCrop) -> str:
        self.calls.append(crop.sha256)
        return r"E=mc^{2}"


def test_case_runner_requires_exact_crop_hash_before_provider_call() -> None:
    manifest = load_manifest(EXPERIMENT_DIR / "corpus.json")
    recognizer = _FakeCaseRecognizer()

    try:
        recognize_manifest_case(
            case_id="basic_superscript",
            confirmed_sha256="0" * 64,
            recognizer=recognizer,
            manifest=manifest,
            experiment_dir=EXPERIMENT_DIR,
        )
    except ValueError as exc:
        assert "exact SHA-256" in str(exc)
    else:
        raise AssertionError("Mismatched crop consent was not rejected")
    assert recognizer.calls == []

    case = manifest["cases"][0]
    result = recognize_manifest_case(
        case_id="basic_superscript",
        confirmed_sha256=case["crop_sha256"],
        recognizer=recognizer,
        manifest=manifest,
        experiment_dir=EXPERIMENT_DIR,
    )
    assert result["status"] == "ok"
    assert result["latex"] == r"E=mc^{2}"
    assert recognizer.calls == [case["crop_sha256"].casefold()]


def test_case_runner_stores_only_sanitized_predictions(tmp_path: Path) -> None:
    output = tmp_path / "predictions.json"
    prediction = {
        "case_id": "basic_superscript",
        "status": "ok",
        "latex": r"E=mc^{2}",
        "recognizer": "fake",
        "model_revision": "fake-v1",
        "execution": "remote",
        "elapsed_ms": 1.0,
    }

    store_prediction(output, prediction)

    stored = json.loads(output.read_text(encoding="utf-8"))
    assert stored == {"schema_version": 1, "predictions": [prediction]}
    assert "api_key" not in output.read_text(encoding="utf-8").casefold()


def test_browser_fake_acceptance_server_allows_only_one_bounded_crop() -> None:
    png = b"\x89PNG\r\n\x1a\nacceptance"
    request = {
        "model": "g5-loopback-formula",
        "messages": [
            {"role": "system", "content": "fixed system prompt"},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "fixed crop prompt"},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64,"
                            + b64encode(png).decode("ascii")
                        },
                    },
                ],
            },
        ],
    }

    image, model = FormulaHandler._validate_request(request)

    assert image == png
    assert model == "g5-loopback-formula"

    with pytest.raises(ValueError, match="history"):
        FormulaHandler._validate_request(
            {**request, "messages": [*request["messages"], {"role": "assistant"}]}
        )
    leaking = json.loads(json.dumps(request))
    leaking["messages"][1]["content"][0]["text"] = r"read D:\private\paper.pdf"
    with pytest.raises(ValueError, match="Path or PDF"):
        FormulaHandler._validate_request(leaking)
    malformed = {**request, "messages": ["not-a-message", {}]}
    with pytest.raises(ValueError, match="history"):
        FormulaHandler._validate_request(malformed)


def test_real_paper_inspector_keeps_report_path_and_text_free(tmp_path: Path) -> None:
    output_dir = tmp_path / "private-output"
    source_path = EXPERIMENT_DIR / "corpus.pdf"

    report = inspect_papers(
        (("synthetic-paper", source_path),),
        output_dir=output_dir,
        max_crops_per_paper=3,
    )

    serialized = json.dumps(report, ensure_ascii=False)
    assert report["network_used"] is False
    assert report["source_paths_stored"] is False
    assert report["source_text_stored"] is False
    assert str(source_path.parent) not in serialized
    assert report["summary"]["paper_count"] == 1
    assert report["summary"]["page_count"] == 20
    assert report["summary"]["rendered_candidate_count"] <= 3
    for candidate in report["papers"][0]["candidates"]:
        assert "source_text" not in candidate
        crop_path = output_dir / candidate["crop_file"]
        assert crop_path.is_file()
        assert hashlib.sha256(crop_path.read_bytes()).hexdigest() == candidate[
            "crop_sha256"
        ]


def test_real_paper_spec_requires_safe_path_free_identifier() -> None:
    source_id, path = parse_paper_spec("paper-01=C:/private/paper.pdf")
    assert source_id == "paper-01"
    assert path.name == "paper.pdf"

    with pytest.raises(Exception, match="safe SOURCE_ID"):
        parse_paper_spec("../paper=C:/private/paper.pdf")


def test_real_paper_annotations_are_bounded_path_free_and_strict_latex() -> None:
    annotation_path = EXPERIMENT_DIR / "real_paper_annotations.json"
    document = json.loads(annotation_path.read_text(encoding="utf-8"))
    serialized = annotation_path.read_text(encoding="utf-8")

    assert document["external_transfer_authorized"] is False
    assert document["source_paths_stored"] is False
    assert document["source_text_stored"] is False
    assert len(document["papers"]) == 3
    assert len(document["recognition_cases"]) == 18
    assert len(document["detector_audit_cases"]) == 10
    assert "D:\\" not in serialized
    assert "crop_file" not in serialized
    assert len({case["id"] for case in document["recognition_cases"]}) == 18
    assert {case["source_id"] for case in document["recognition_cases"]} == {
        paper["source_id"] for paper in document["papers"]
    }
    for case in document["recognition_cases"]:
        assert len(case["crop_sha256"]) == 64
        assert len(case["bbox"]) == 4
        assert parse_latex_response(
            f"<latex>{case['reference_latex']}</latex>"
        ) == case["reference_latex"]
    for case in document["detector_audit_cases"]:
        assert len(case["crop_sha256"]) == 64
        assert len(case["bbox"]) == 4
        assert case["source_id"] in {
            paper["source_id"] for paper in document["papers"]
        }


def test_real_paper_detector_evaluator_preserves_recall_and_scores_rejections() -> None:
    annotations = {
        "papers": [{"source_id": "paper", "source_sha256": "a" * 64}],
        "recognition_cases": [
            {"id": "positive", "source_id": "paper", "page_number": 1,
             "bbox": [10.0, 10.0, 30.0, 30.0], "crop_sha256": "b" * 64}
        ],
        "detector_audit_cases": [
            {"id": "keep", "source_id": "paper", "page_number": 1,
             "bbox": [10.0, 10.0, 30.0, 30.0], "crop_sha256": "b" * 64,
             "expected_detected": True},
            {"id": "reject", "source_id": "paper", "page_number": 1,
             "bbox": [40.0, 40.0, 60.0, 60.0], "crop_sha256": "c" * 64,
             "expected_detected": False},
        ],
    }
    baseline = {
        "papers": [
            {"source_id": "paper", "source_sha256": "a" * 64,
             "detected_candidate_count": 2,
             "candidates": [
                 {"page_number": 1, "bbox": [10, 10, 30, 30],
                  "crop_sha256": "b" * 64},
                 {"page_number": 1, "bbox": [40, 40, 60, 60],
                  "crop_sha256": "c" * 64},
             ]}
        ]
    }
    candidate = {
        "papers": [
            {"source_id": "paper", "source_sha256": "a" * 64,
             "detected_candidate_count": 1,
             "candidates": [{"page_number": 1, "bbox": [10, 10, 30, 30]}]}
        ]
    }

    result = evaluate_detector(annotations, baseline, candidate)

    assert result["optimization_guardrails_met"] is True
    assert result["metrics"]["recognition_case_recall"] == 1.0
    assert result["metrics"]["unwanted_candidate_rejection"] == 1.0
    assert result["metrics"]["candidate_reduction_rate"] == 0.5
    assert result["remaining_audit_failures"] == []


class _FakeRealPaperRecognizer:
    name = "fake-real-paper"
    model_revision = "dots3-note-prev"
    execution = "remote"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def recognize(self, crop: FormulaCrop) -> str:
        self.calls.append(crop.sha256)
        return r"\sum_{i=1}^{n} i"


class _FailingRealPaperRecognizer(_FakeRealPaperRecognizer):
    def recognize(self, crop: FormulaCrop) -> str:
        from researchmind.llm import LlmApiError

        self.calls.append(crop.sha256)
        raise LlmApiError("provider detail must not be persisted")


def _real_paper_fixture(tmp_path: Path) -> tuple[dict, dict, Path, str]:
    crop_root = tmp_path / "private-crops"
    crop_path = crop_root / "paper" / "crops" / "case.png"
    crop_path.parent.mkdir(parents=True)
    crop_bytes = b"\x89PNG\r\n\x1a\nreal-paper-case"
    crop_path.write_bytes(crop_bytes)
    crop_hash = hashlib.sha256(crop_bytes).hexdigest()
    paper_hash = "a" * 64
    first_case = {
        "id": "paper-001",
        "source_id": "paper",
        "page_number": 1,
        "bbox": [10.0, 20.0, 100.0, 50.0],
        "crop_sha256": crop_hash,
        "reference_latex": r"\sum_{i=1}^{n} i",
        "categories": ["sum", "subscript", "superscript"],
    }
    cases = [first_case]
    cases.extend(
        {**first_case, "id": f"paper-{index:03d}"}
        for index in range(2, 19)
    )
    annotations = {
        "schema_version": 1,
        "annotation_status": "agent_visual_first_pass_requires_human_spot_check",
        "papers": [{"source_id": "paper", "source_sha256": paper_hash}],
        "recognition_cases": cases,
    }
    inspection = {
        "papers": [{
            "source_id": "paper",
            "source_sha256": paper_hash,
            "candidates": [{
                "page_number": 1,
                "bbox": first_case["bbox"],
                "kind": "display",
                "source_kind": "digital_text",
                "detector_origin": "fake-detector",
                "detector_confidence": 1.0,
                "signals": ["sum"],
                "crop_file": "paper/crops/case.png",
                "crop_sha256": crop_hash,
                "crop_byte_count": len(crop_bytes),
                "crop_width_px": 100,
                "crop_height_px": 30,
            }],
        }],
    }
    return annotations, inspection, crop_root, crop_hash


def test_real_paper_runner_requires_explicit_authorization_and_hash(tmp_path: Path) -> None:
    annotations, inspection, crop_root, crop_hash = _real_paper_fixture(tmp_path)
    recognizer = _FakeRealPaperRecognizer()

    with pytest.raises(ValueError, match="authorization"):
        recognize_real_paper_case(
            case_id="paper-001",
            confirmed_sha256=crop_hash,
            external_transfer_authorized=False,
            annotations=annotations,
            inspection=inspection,
            crop_root=crop_root,
            recognizer=recognizer,
        )
    with pytest.raises(ValueError, match="exact SHA-256"):
        recognize_real_paper_case(
            case_id="paper-001",
            confirmed_sha256="0" * 64,
            external_transfer_authorized=True,
            annotations=annotations,
            inspection=inspection,
            crop_root=crop_root,
            recognizer=recognizer,
        )
    assert recognizer.calls == []

    result = recognize_real_paper_case(
        case_id="paper-001",
        confirmed_sha256=crop_hash,
        external_transfer_authorized=True,
        annotations=annotations,
        inspection=inspection,
        crop_root=crop_root,
        recognizer=recognizer,
    )
    assert result["latex"] == r"\sum_{i=1}^{n} i"
    assert recognizer.calls == [crop_hash]


def test_real_paper_prediction_storage_is_sanitized_and_evaluable(tmp_path: Path) -> None:
    annotations, _, _, _ = _real_paper_fixture(tmp_path)
    output = tmp_path / "real-predictions.json"
    for case in annotations["recognition_cases"]:
        store_real_prediction(
            output,
            {
                "case_id": case["id"],
                "status": "ok",
                "latex": case["reference_latex"],
                "recognizer": "fake-real-paper",
                "model_revision": "dots3-note-prev",
                "execution": "remote",
                "elapsed_ms": 10.0,
            },
        )

    stored = json.loads(output.read_text(encoding="utf-8"))
    assert stored["authorization"] == AUTHORIZATION_RECORD
    assert "api_key" not in output.read_text(encoding="utf-8").casefold()
    result = evaluate_real_paper_predictions(annotations, stored)
    assert result["real_paper_quality_thresholds_met"] is True
    assert result["source_tex_recovery_thresholds_met"] is True
    assert result["human_spot_check_required"] is True
    assert result["metrics"]["median_elapsed_ms"] == 10.0


def test_real_paper_runner_sanitizes_provider_failures(tmp_path: Path) -> None:
    annotations, inspection, crop_root, crop_hash = _real_paper_fixture(tmp_path)
    recognizer = _FailingRealPaperRecognizer()

    result = recognize_real_paper_case(
        case_id="paper-001",
        confirmed_sha256=crop_hash,
        external_transfer_authorized=True,
        annotations=annotations,
        inspection=inspection,
        crop_root=crop_root,
        recognizer=recognizer,
    )

    assert result["status"] == "error"
    assert result["latex"] is None
    assert "detail" not in json.dumps(result)


def test_response_diagnostic_records_shapes_without_content() -> None:
    class Value:
        pass

    response = Value()
    response.choices = [Value()]
    response.choices[0].finish_reason = "length"
    response.choices[0].message = Value()
    response.choices[0].message.content = "private formula text"
    response.choices[0].message.refusal = None
    response.choices[0].message.model_extra = {
        "reasoning_content": "private reasoning text"
    }
    response.usage = Value()
    response.usage.prompt_tokens = 100
    response.usage.completion_tokens = 1600
    response.usage.total_tokens = 1700

    diagnostic = _sanitize_response_structure(response)
    serialized = json.dumps(diagnostic)

    assert diagnostic["content_char_count"] == len("private formula text")
    assert diagnostic["extra_fields"]["reasoning_content"]["char_count"] == len(
        "private reasoning text"
    )
    assert "private formula" not in serialized
    assert "private reasoning" not in serialized
