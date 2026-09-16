"""Application-flow tests for explicit G5 formula recognition and evidence."""

from dataclasses import replace
from pathlib import Path
import shutil

import pytest

from researchmind.app import use_cases
from researchmind.config import Settings
from researchmind.database import LibraryConflictError
from researchmind.models import FormulaCrop, UploadedFileData
from researchmind.pdf import PdfFormulaError, open_pdf


CORPUS_PDF = (
    Path(__file__).parents[2]
    / "experiments"
    / "g5_formula_recognition"
    / "corpus.pdf"
)


class FakeRemoteRecognizer:
    name = "fake-vision"
    model_revision = "fake-v1"
    execution = "remote"

    def __init__(self, result: str | None = r"\sum_{i=1}^{n} i") -> None:
        self.result = result
        self.calls = 0

    def recognize(self, crop: FormulaCrop) -> str | None:
        self.calls += 1
        assert crop.png_bytes.startswith(b"\x89PNG")
        return self.result


def test_preview_does_not_call_provider_and_remote_requires_exact_consent() -> None:
    opened = open_pdf(CORPUS_PDF)
    region = use_cases.detect_formula_regions(opened, 5)[0]
    crop = use_cases.prepare_formula_crop(opened, region)
    recognizer = FakeRemoteRecognizer()

    preview = use_cases.preview_formula_recognition(crop, recognizer=recognizer)

    assert preview.region_id == region.id
    assert preview.crop_sha256 == crop.sha256
    assert preview.byte_count == len(crop.png_bytes)
    assert preview.execution == "remote"
    assert preview.will_leave_device is True
    assert recognizer.calls == 0

    with pytest.raises(ValueError, match="exact crop"):
        use_cases.recognize_formula_crop(
            crop,
            confirm_external_transfer=False,
            recognizer=recognizer,
        )
    assert recognizer.calls == 0

    candidate = use_cases.recognize_formula_crop(
        crop,
        confirm_external_transfer=True,
        recognizer=recognizer,
    )
    assert recognizer.calls == 1
    assert candidate.latex_candidate == r"\sum_{i=1}^{n} i"
    assert candidate.accepted_latex is None


def test_only_accepted_edited_latex_can_enter_note_evidence(tmp_path: Path) -> None:
    opened = open_pdf(CORPUS_PDF)
    crop = use_cases.prepare_formula_crop(
        opened,
        use_cases.detect_formula_regions(opened, 5)[0],
    )
    candidate = use_cases.recognize_formula_crop(
        crop,
        confirm_external_transfer=True,
        recognizer=FakeRemoteRecognizer(),
    )
    settings = Settings(researchmind_data_dir=tmp_path / "library")
    draft = use_cases.create_paper_note_draft(opened, settings=settings)

    with pytest.raises(ValueError, match="Accept"):
        use_cases.capture_formula_evidence(
            draft,
            candidate,
            opened,
            settings=settings,
        )
    assert use_cases.list_note_evidence(draft.id, settings=settings) == []

    accepted = use_cases.accept_formula_candidate(
        candidate,
        r"\sum_{i=1}^{n} i = \frac{n(n+1)}{2}",
        opened,
    )
    updated, evidence = use_cases.capture_formula_evidence(
        draft,
        accepted,
        opened,
        settings=settings,
    )

    assert accepted.accepted_at is not None
    assert evidence.kind == "latex"
    assert evidence.origin == "latex_conversion"
    assert evidence.content == r"\sum_{i=1}^{n} i = \frac{n(n+1)}{2}"
    assert evidence.locator["page_number"] == 5
    assert evidence.locator["crop_sha256"] == crop.sha256
    assert "source_text" not in evidence.locator
    assert "path" not in str(evidence.locator).casefold()
    assert use_cases.note_evidence_source_state(evidence, settings=settings) == "detached"

    with pytest.raises(LibraryConflictError, match="already"):
        use_cases.capture_formula_evidence(
            updated,
            accepted,
            opened,
            settings=settings,
        )


def test_acceptance_revalidates_safe_latex_and_current_crop() -> None:
    opened = open_pdf(CORPUS_PDF)
    crop = use_cases.prepare_formula_crop(
        opened,
        use_cases.detect_formula_regions(opened, 3)[0],
    )
    candidate = use_cases.recognize_formula_crop(
        crop,
        confirm_external_transfer=True,
        recognizer=FakeRemoteRecognizer(result=r"\int_a^b f(x)\,dx"),
    )

    with pytest.raises(Exception, match="disallowed command"):
        use_cases.accept_formula_candidate(
            candidate,
            r"\input{private-file}",
            opened,
        )
    accepted = use_cases.accept_formula_candidate(
        candidate,
        r"\int_a^b f(x)\,dx",
        opened,
    )
    assert accepted.accepted_latex == r"\int_a^b f(x)\,dx"


def test_unreadable_or_tampered_result_cannot_be_accepted() -> None:
    opened = open_pdf(CORPUS_PDF)
    crop = use_cases.prepare_formula_crop(
        opened,
        use_cases.detect_formula_regions(opened, 11)[0],
    )
    unreadable = use_cases.recognize_formula_crop(
        crop,
        confirm_external_transfer=True,
        recognizer=FakeRemoteRecognizer(result=None),
    )
    assert unreadable.status == "unreadable"
    with pytest.raises(ValueError, match="unreadable"):
        use_cases.accept_formula_candidate(unreadable, "x", opened)

    tampered = replace(crop, sha256="0" * 64)
    recognizer = FakeRemoteRecognizer()
    with pytest.raises(ValueError, match="hash"):
        use_cases.recognize_formula_crop(
            tampered,
            confirm_external_transfer=True,
            recognizer=recognizer,
        )
    assert recognizer.calls == 0


def test_candidate_with_malformed_timestamp_fails_closed() -> None:
    opened = open_pdf(CORPUS_PDF)
    crop = use_cases.prepare_formula_crop(
        opened,
        use_cases.detect_formula_regions(opened, 5)[0],
    )
    candidate = use_cases.recognize_formula_crop(
        crop,
        confirm_external_transfer=True,
        recognizer=FakeRemoteRecognizer(),
    )
    malformed = replace(candidate, created_at=None)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="timezone"):
        use_cases.accept_formula_candidate(malformed, r"\sum_i i", opened)


def test_capture_rejects_pdf_changed_after_acceptance(tmp_path: Path) -> None:
    copied = tmp_path / "corpus.pdf"
    shutil.copyfile(CORPUS_PDF, copied)
    opened = open_pdf(copied)
    crop = use_cases.prepare_formula_crop(
        opened,
        use_cases.detect_formula_regions(opened, 19)[0],
    )
    candidate = use_cases.recognize_formula_crop(
        crop,
        confirm_external_transfer=True,
        recognizer=FakeRemoteRecognizer(result=r"\oint_{\partial\Omega} F\cdot dr"),
    )
    accepted = use_cases.accept_formula_candidate(
        candidate,
        candidate.latex_candidate or "",
        opened,
    )
    settings = Settings(researchmind_data_dir=tmp_path / "library")
    draft = use_cases.create_paper_note_draft(opened, settings=settings)
    copied.write_bytes(copied.read_bytes() + b"\nchanged")

    with pytest.raises(PdfFormulaError, match="changed"):
        use_cases.capture_formula_evidence(
            draft,
            accepted,
            opened,
            settings=settings,
        )


def test_managed_formula_evidence_binds_exact_library_revision(tmp_path: Path) -> None:
    settings = Settings(researchmind_data_dir=tmp_path / "library")
    imported = use_cases.import_pdf_to_library(
        UploadedFileData(name="formula-corpus.pdf", content=CORPUS_PDF.read_bytes()),
        settings=settings,
    )
    opened = use_cases.open_library_paper(
        imported.entry.record.id,
        settings=settings,
    )
    crop = use_cases.prepare_formula_crop(
        opened,
        use_cases.detect_formula_regions(opened, 4)[0],
    )
    candidate = use_cases.recognize_formula_crop(
        crop,
        confirm_external_transfer=True,
        recognizer=FakeRemoteRecognizer(
            result=r"\int_{-\infty}^{\infty}e^{-x^2}\,dx=\sqrt{\pi}"
        ),
    )
    accepted = use_cases.accept_formula_candidate(
        candidate,
        candidate.latex_candidate or "",
        opened,
    )
    draft = use_cases.create_paper_note_draft(
        opened,
        library_entry=imported.entry,
        settings=settings,
    )

    _updated, evidence = use_cases.capture_formula_evidence(
        draft,
        accepted,
        opened,
        library_entry=imported.entry,
        settings=settings,
    )

    assert evidence.source_record_id == imported.entry.record.id
    assert evidence.source_asset_id == imported.entry.asset.id
    assert evidence.source_revision == imported.entry.asset.revision
    assert evidence.source_sha256 == imported.entry.asset.sha256
    assert use_cases.note_evidence_source_state(evidence, settings=settings) == "current"
