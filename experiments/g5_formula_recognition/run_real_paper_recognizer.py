"""Run one explicitly authorized, hash-locked real-paper crop remotely.

The caller must name and confirm one crop on every invocation. The persisted
document contains only bounded authorization metadata and sanitized predictions;
it never stores provider credentials, endpoints, PDF paths, crop paths, or raw
responses.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path, PurePosixPath
from time import perf_counter
from typing import Any, Sequence

from researchmind.config import load_settings
from researchmind.llm import FormulaRecognizer, LlmError, create_formula_recognizer
from researchmind.models import FormulaCrop, FormulaRegion


EXPERIMENT_DIR = Path(__file__).parent
DEFAULT_ANNOTATIONS = EXPERIMENT_DIR / "real_paper_annotations.json"
DEFAULT_INSPECTION = EXPERIMENT_DIR / ".build" / "real_papers" / "inspection.json"
DEFAULT_CROP_ROOT = EXPERIMENT_DIR / ".build" / "real_papers"
DEFAULT_OUTPUT = EXPERIMENT_DIR / "real_paper_remote_predictions.json"
EXPECTED_CASE_COUNT = 18
EXPECTED_MODEL = "dots3-note-prev"
AUTHORIZATION_RECORD = {
    "scope": "18_hash_locked_formula_crops",
    "destination": "dots_studio",
    "model_revision": EXPECTED_MODEL,
    "confirmed_on": "2026-09-13",
    "case_count": EXPECTED_CASE_COUNT,
}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument("--confirm-sha256", required=True)
    parser.add_argument("--annotations", type=Path, default=DEFAULT_ANNOTATIONS)
    parser.add_argument("--inspection", type=Path, default=DEFAULT_INSPECTION)
    parser.add_argument("--crop-root", type=Path, default=DEFAULT_CROP_ROOT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--authorized-external-transfer",
        action="store_true",
        help="Required acknowledgement for this one crop.",
    )
    args = parser.parse_args(argv)

    try:
        prediction = recognize_real_paper_case(
            case_id=args.case_id,
            confirmed_sha256=args.confirm_sha256,
            external_transfer_authorized=args.authorized_external_transfer,
            annotations=_load_json(args.annotations),
            inspection=_load_json(args.inspection),
            crop_root=args.crop_root,
        )
        store_real_prediction(args.output, prediction)
    except OSError:
        print(json.dumps({"status": "error", "message": "A local crop operation failed."}))
        return 2
    except (LlmError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}))
        return 2

    print(
        json.dumps(
            {
                "case_id": prediction["case_id"],
                "status": prediction["status"],
                "model_revision": prediction["model_revision"],
                "elapsed_ms": prediction["elapsed_ms"],
            },
            ensure_ascii=False,
        )
    )
    return 0


def recognize_real_paper_case(
    *,
    case_id: str,
    confirmed_sha256: str,
    external_transfer_authorized: bool,
    annotations: dict[str, Any],
    inspection: dict[str, Any],
    crop_root: Path,
    recognizer: FormulaRecognizer | None = None,
) -> dict[str, object]:
    """Recognize exactly one approved crop after all local checks pass."""

    if not external_transfer_authorized:
        raise ValueError("Explicit external-transfer authorization is required.")
    cases = _validate_annotations(annotations)
    case = next((item for item in cases if item["id"] == case_id), None)
    if case is None:
        raise ValueError("Unknown real-paper formula case id.")
    expected_hash = str(case["crop_sha256"]).casefold()
    if confirmed_sha256.strip().casefold() != expected_hash:
        raise ValueError("Confirmation must match this one crop's exact SHA-256.")

    source_hashes = {
        item["source_id"]: item["source_sha256"]
        for item in annotations["papers"]
    }
    paper = next(
        (
            item for item in inspection.get("papers", [])
            if item.get("source_id") == case["source_id"]
            and item.get("source_sha256") == source_hashes[case["source_id"]]
        ),
        None,
    )
    if paper is None:
        raise ValueError("The inspection report does not match the approved paper.")
    matches = [
        item for item in paper.get("candidates", [])
        if item.get("crop_sha256") == expected_hash
        and item.get("page_number") == case["page_number"]
        and item.get("bbox") == case["bbox"]
    ]
    if len(matches) != 1:
        raise ValueError("The inspection report does not uniquely identify the crop.")
    candidate = matches[0]
    crop_path = _resolve_crop_path(crop_root, candidate.get("crop_file"))
    crop_bytes = crop_path.read_bytes()
    actual_hash = sha256(crop_bytes).hexdigest()
    if actual_hash != expected_hash:
        raise ValueError("The formula crop no longer matches the locked annotation.")
    if len(crop_bytes) != candidate.get("crop_byte_count"):
        raise ValueError("The formula crop byte count changed after inspection.")
    if not crop_bytes.startswith(b"\x89PNG\r\n\x1a\n"):
        raise ValueError("The authorized crop is not a PNG image.")

    resolved_recognizer = recognizer or create_formula_recognizer(load_settings())
    if resolved_recognizer.model_revision != EXPECTED_MODEL:
        raise ValueError(
            f"The configured formula model must be exactly {EXPECTED_MODEL}."
        )
    region = FormulaRegion(
        id=f"formula-region-real-paper-{case_id}",
        document_id=str(case["source_id"]),
        document_revision=f"sha256:{source_hashes[case['source_id']]}",
        page_number=int(case["page_number"]),
        bbox=tuple(float(value) for value in case["bbox"]),
        kind=str(candidate["kind"]),
        source_kind=str(candidate["source_kind"]),
        detector_origin=str(candidate["detector_origin"]),
        detector_confidence=float(candidate["detector_confidence"]),
        signals=tuple(str(value) for value in candidate.get("signals", [])),
    )
    crop = FormulaCrop(
        region=region,
        png_bytes=crop_bytes,
        sha256=actual_hash,
        width_px=int(candidate["crop_width_px"]),
        height_px=int(candidate["crop_height_px"]),
    )
    started = perf_counter()
    try:
        latex = resolved_recognizer.recognize(crop)
    except LlmError:
        return {
            "case_id": case_id,
            "status": "error",
            "latex": None,
            "recognizer": resolved_recognizer.name,
            "model_revision": resolved_recognizer.model_revision,
            "execution": resolved_recognizer.execution,
            "elapsed_ms": round((perf_counter() - started) * 1_000, 3),
        }
    elapsed_ms = round((perf_counter() - started) * 1_000, 3)
    return {
        "case_id": case_id,
        "status": "unreadable" if latex is None else "ok",
        "latex": latex,
        "recognizer": resolved_recognizer.name,
        "model_revision": resolved_recognizer.model_revision,
        "execution": resolved_recognizer.execution,
        "elapsed_ms": elapsed_ms,
    }


def store_real_prediction(path: Path, prediction: dict[str, object]) -> None:
    """Atomically upsert one sanitized result under the fixed authorization."""

    output = path.resolve()
    if output.exists():
        document = _load_json(output)
        if document.get("schema_version") != 1:
            raise ValueError("Unsupported real-paper prediction document.")
        if document.get("authorization") != AUTHORIZATION_RECORD:
            raise ValueError("Prediction authorization metadata does not match.")
        current = document.get("predictions")
        if not isinstance(current, list):
            raise ValueError("Predictions must be a list.")
    else:
        current = []
    predictions = [
        item for item in current
        if isinstance(item, dict) and item.get("case_id") != prediction["case_id"]
    ]
    predictions.append(prediction)
    predictions.sort(key=lambda item: str(item["case_id"]))
    document = {
        "schema_version": 1,
        "authorization": AUTHORIZATION_RECORD,
        "predictions": predictions,
    }
    _write_json_atomically(output, document)


def _validate_annotations(annotations: dict[str, Any]) -> list[dict[str, Any]]:
    cases = annotations.get("recognition_cases")
    papers = annotations.get("papers")
    if (
        annotations.get("schema_version") != 1
        or not isinstance(cases, list)
        or len(cases) != EXPECTED_CASE_COUNT
        or not isinstance(papers, list)
    ):
        raise ValueError("Unsupported real-paper annotation corpus.")
    ids = [item.get("id") for item in cases if isinstance(item, dict)]
    if len(ids) != len(cases) or len(set(ids)) != len(ids):
        raise ValueError("Real-paper case ids must be unique.")
    return cases


def _resolve_crop_path(crop_root: Path, raw_relative_path: object) -> Path:
    if not isinstance(raw_relative_path, str):
        raise ValueError("The crop report needs a relative crop path.")
    relative = PurePosixPath(raw_relative_path)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix.casefold() != ".png":
        raise ValueError("The crop report contains an unsafe crop path.")
    root = crop_root.resolve(strict=True)
    candidate = root.joinpath(*relative.parts).resolve(strict=True)
    if not candidate.is_relative_to(root):
        raise ValueError("The crop path escaped its approved root.")
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError("Formula crops may not pass through symbolic links.")
    if not candidate.is_file():
        raise ValueError("The authorized formula crop is missing.")
    return candidate


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("G5 inputs must be JSON objects.")
    return value


def _write_json_atomically(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    raise SystemExit(main())
