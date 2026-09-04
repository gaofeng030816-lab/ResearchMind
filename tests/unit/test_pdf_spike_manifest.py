"""Schema checks for the isolated T2 PDF/mathematics spike corpus."""

import json
from pathlib import Path, PurePath


MANIFEST_PATH = (
    Path(__file__).resolve().parents[2]
    / "experiments"
    / "pdf_parser_spike"
    / "corpus.json"
)


def test_t2_pdf_spike_manifest_covers_required_document_classes() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    documents = manifest["documents"]
    ids = [document["id"] for document in documents]
    categories = {
        category
        for document in documents
        for category in document["categories"]
    }

    assert manifest["schema_version"] == 1
    assert len(ids) == len(set(ids))
    assert {"double_column", "formula", "table", "figure", "scanned"} <= categories
    assert all(len(document["sha256"]) == 64 for document in documents)
    assert all(not PurePath(document["filename"]).is_absolute() for document in documents)
    assert all(document["sample_pages"] for document in documents)
