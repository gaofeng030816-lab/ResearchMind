"""Run one explicitly confirmed clean-room formula crop through a recognizer."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
from typing import Any

from researchmind.config import load_settings
from researchmind.llm import FormulaRecognizer, LlmError, create_formula_recognizer
from researchmind.models import FormulaCrop, FormulaRegion

from experiments.g5_formula_recognition.evaluation import load_manifest


EXPERIMENT_DIR = Path(__file__).parent
DEFAULT_OUTPUT = EXPERIMENT_DIR / "remote_predictions.partial.json"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case-id", required=True)
    parser.add_argument(
        "--confirm-sha256",
        required=True,
        help="Exact SHA-256 displayed for this one crop",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    try:
        prediction = recognize_manifest_case(
            case_id=args.case_id,
            confirmed_sha256=args.confirm_sha256,
        )
        store_prediction(args.output, prediction)
    except OSError:
        print(json.dumps({"status": "error", "message": "A local formula file operation failed."}))
        return 2
    except (LlmError, ValueError) as exc:
        print(json.dumps({"status": "error", "message": str(exc)}))
        return 2
    print(json.dumps(prediction, ensure_ascii=False, indent=2))
    return 0 if prediction["status"] == "ok" else 2


def recognize_manifest_case(
    *,
    case_id: str,
    confirmed_sha256: str,
    recognizer: FormulaRecognizer | None = None,
    manifest: dict[str, Any] | None = None,
    experiment_dir: Path = EXPERIMENT_DIR,
) -> dict[str, object]:
    """Recognize exactly one hash-locked case; never batches implicit consent."""

    resolved_manifest = manifest or load_manifest(experiment_dir / "corpus.json")
    case = next(
        (item for item in resolved_manifest["cases"] if item["id"] == case_id),
        None,
    )
    if case is None:
        raise ValueError("Unknown G5 formula case id.")
    expected_sha256 = str(case["crop_sha256"]).casefold()
    if confirmed_sha256.strip().casefold() != expected_sha256:
        raise ValueError(
            "Confirmation must match the exact SHA-256 of this one formula crop."
        )
    crop_path = experiment_dir / str(case["crop_file"])
    crop_bytes = crop_path.read_bytes()
    actual_sha256 = sha256(crop_bytes).hexdigest()
    if actual_sha256 != expected_sha256:
        raise ValueError("The formula crop no longer matches the locked manifest.")

    resolved_recognizer = recognizer or create_formula_recognizer(load_settings())
    region = FormulaRegion(
        id=f"formula-region-cleanroom-{case_id}",
        document_id="g5-cleanroom-corpus",
        document_revision=f"sha256:{resolved_manifest['source_pdf_sha256'].casefold()}",
        page_number=int(case["page_number"]),
        bbox=(
            0.0,
            0.0,
            float(case["crop_width_px"]),
            float(case["crop_height_px"]),
        ),
        kind="display",
        source_kind="digital_text",
        detector_origin="cleanroom_hash_locked_crop_v1",
        detector_confidence=1.0,
        signals=tuple(str(item) for item in case["categories"]),
    )
    crop = FormulaCrop(
        region=region,
        png_bytes=crop_bytes,
        sha256=actual_sha256,
        width_px=int(case["crop_width_px"]),
        height_px=int(case["crop_height_px"]),
    )
    started = perf_counter()
    latex = resolved_recognizer.recognize(crop)
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


def store_prediction(path: Path, prediction: dict[str, object]) -> None:
    """Atomically upsert one non-sensitive prediction result."""

    output = path.resolve()
    if output.exists():
        document = json.loads(output.read_text(encoding="utf-8"))
    else:
        document = {"schema_version": 1, "predictions": []}
    if document.get("schema_version") != 1 or not isinstance(
        document.get("predictions"),
        list,
    ):
        raise ValueError("Unsupported prediction output document.")
    predictions = [
        item
        for item in document["predictions"]
        if isinstance(item, dict) and item.get("case_id") != prediction["case_id"]
    ]
    predictions.append(prediction)
    predictions.sort(key=lambda item: str(item["case_id"]))
    payload = json.dumps(
        {"schema_version": 1, "predictions": predictions},
        ensure_ascii=False,
        indent=2,
    ) + "\n"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".tmp")
    temporary.write_text(payload, encoding="utf-8")
    temporary.replace(output)


if __name__ == "__main__":
    raise SystemExit(main())
