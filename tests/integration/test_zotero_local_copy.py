"""Real Windows read + PDF parser + SQLite, with a fake loopback transport."""

from dataclasses import replace
import json
from pathlib import Path

import pytest

from researchmind.app import use_cases
from researchmind.config import ConfigError, Settings
from researchmind.database import LibraryConfirmationError, LibraryConflictError
from researchmind.integration.zotero import ZoteroHttpResponse, ZoteroLocalApi
from researchmind.models import ZoteroConnection, ZoteroItemDetails, UploadedFileData


class LocalFixtureTransport:
    def __init__(self, source: Path):
        self.source = source
        self.calls = []

    def get(self, relative_url, *, headers, max_bytes):
        self.calls.append(relative_url)
        assert headers["Zotero-Server-ID"] == "fixture-server"
        common = {"library": {"type": "user", "id": 1}, "version": 1}
        if relative_url == "users/0/items/ITEM0001?format=json&include=data":
            data = {"key": "ITEM0001", "version": 1, "itemType": "journalArticle",
                    "title": "Synthetic paper", "creators": []}
        elif relative_url == "users/0/items/PDF00001?format=json&include=data":
            data = {"key": "PDF00001", "version": 1, "itemType": "attachment",
                    "title": "PDF", "filename": "paper.pdf", "parentItem": "ITEM0001",
                    "contentType": "application/pdf", "linkMode": "imported_file"}
        elif relative_url == "users/0/items/PDF00001/file/view/url":
            return ZoteroHttpResponse(200, {
                "Zotero-Server-ID": "fixture-server", "Zotero-API-Version": "3",
                "Content-Type": "text/plain",
            }, self.source.as_uri().encode())
        else:
            raise AssertionError("Unexpected HTTP route")
        return ZoteroHttpResponse(200, {
            "Zotero-Server-ID": "fixture-server", "Zotero-API-Version": "3",
            "Content-Type": "application/json",
        }, json.dumps({**common, "key": data["key"], "data": data}).encode())


def _fixture(tmp_path, single_page_pdf):
    from researchmind.integration.zotero.local_api import _map_item, _map_pdf_attachment
    root = tmp_path / "attachments"
    root.mkdir()
    source = root / "paper.pdf"
    source.write_bytes(single_page_pdf.read_bytes())
    transport = LocalFixtureTransport(source)
    headers = {"Zotero-Server-ID": "fixture-server"}
    item = _map_item(json.loads(transport.get(
        "users/0/items/ITEM0001?format=json&include=data", headers=headers, max_bytes=10000,
    ).body), "fixture-server")
    attachment = _map_pdf_attachment(json.loads(transport.get(
        "users/0/items/PDF00001?format=json&include=data", headers=headers, max_bytes=10000,
    ).body), item)
    transport.calls.clear()
    settings = Settings(researchmind_data_dir=tmp_path / "managed", zotero_local_api_enabled=True,
                        zotero_attachment_root=str(root))
    details = ZoteroItemDetails(ZoteroConnection("fixture-server", 3), item, (attachment,))
    return source, transport, settings, details


@pytest.mark.parametrize("duplicate", [False, True])
def test_url_copy_parses_persists_reopens_and_never_changes_original(
    tmp_path, single_page_pdf, duplicate,
):
    source, transport, settings, details = _fixture(tmp_path, single_page_pdf)
    original = source.read_bytes()
    before = source.stat().st_mtime_ns
    if duplicate:
        use_cases.import_pdf_to_library(UploadedFileData("paper.pdf", original), settings=settings)
    imported = use_cases.import_zotero_pdf_attachment(
        details, "PDF00001", confirmed=True,
        approved_root_scope=use_cases.zotero_attachment_approval_scope(settings=settings),
        settings=settings, client=ZoteroLocalApi(transport=transport),
    )
    assert imported.duplicate == duplicate
    assert len(transport.calls) == 6
    # Re-create settings/repositories as a new session would; no live API needed.
    restarted = replace(settings, zotero_local_api_enabled=False)
    assert use_cases.open_library_paper(imported.entry.record.id, settings=restarted).document.num_pages == 1
    link = use_cases.get_zotero_source_link(imported.entry.record.id, settings=restarted)
    assert link.attachment_key == "PDF00001"
    assert str(source) not in repr(link)
    use_cases.unlink_zotero_item_from_paper(imported.entry.record.id, confirmed=True, settings=restarted)
    use_cases.remove_library_record(imported.entry.record.id, confirmed=True, settings=restarted)
    use_cases.delete_library_managed_copies(imported.entry.record.id, confirmed=True, settings=restarted)
    assert source.read_bytes() == original
    assert source.stat().st_mtime_ns == before


@pytest.mark.parametrize("mode", ["unconfirmed", "missing-root", "changed-root"])
def test_copy_gate_rejects_before_http_or_library_creation(tmp_path, single_page_pdf, mode):
    source, transport, settings, details = _fixture(tmp_path, single_page_pdf)
    scope = use_cases.zotero_attachment_approval_scope(settings=settings)
    if mode == "missing-root":
        settings = replace(settings, zotero_attachment_root=None)
    if mode == "changed-root":
        settings = replace(settings, zotero_attachment_root=str(tmp_path / "other"))
    with pytest.raises((LibraryConfirmationError, ConfigError)):
        use_cases.import_zotero_pdf_attachment(
            details, "PDF00001", confirmed=mode != "unconfirmed", approved_root_scope=scope,
            settings=settings, client=ZoteroLocalApi(transport=transport),
        )
    assert not transport.calls
    assert not settings.researchmind_data_dir.exists()


def test_link_failure_compensates_new_copy_without_touching_source(tmp_path, single_page_pdf, monkeypatch):
    source, transport, settings, details = _fixture(tmp_path, single_page_pdf)
    original = source.read_bytes()
    def fail(*args, **kwargs):
        raise LibraryConflictError("Injected source conflict")
    monkeypatch.setattr(use_cases, "link_zotero_item_to_paper", fail)
    with pytest.raises(LibraryConflictError, match="Injected"):
        use_cases.import_zotero_pdf_attachment(
            details, "PDF00001", confirmed=True,
            approved_root_scope=use_cases.zotero_attachment_approval_scope(settings=settings),
            settings=settings, client=ZoteroLocalApi(transport=transport),
        )
    assert not use_cases.list_library_entries(settings=settings)
    assert not list((settings.researchmind_data_dir / "assets").rglob("*.pdf"))
    assert source.read_bytes() == original
