"""Offline integration coverage for V3-G2 Zotero-to-library flows."""

from pathlib import Path

import pytest

from researchmind.app import use_cases
from researchmind.config import ConfigError, Settings
from researchmind.database import LibraryConflictError, LibraryConfirmationError
from researchmind.models import (
    UploadedFileData,
    ZoteroAttachment,
    ZoteroConnection,
    ZoteroDownloadedFile,
    ZoteroItem,
    ZoteroItemDetails,
)


class FakeZoteroClient:
    def __init__(self, pdf_bytes: bytes) -> None:
        self.connection = ZoteroConnection(
            server_id="server-A",
            api_version=3,
        )
        self.item = ZoteroItem(
            server_id="server-A",
            library_type="user",
            library_id="42",
            item_key="ITEM0001",
            item_version=11,
            item_type="journalArticle",
            title="Linked research paper",
            creators=("Ada Researcher",),
            publication_title="Journal of Tests",
            published_date="2026",
            doi="10.0000/example",
            url="https://example.test/paper",
        )
        self.attachment = ZoteroAttachment(
            item_key="PDF00001",
            item_version=4,
            parent_item_key=self.item.item_key,
            title="Full text PDF",
            filename="zotero-paper.pdf",
            content_type="application/pdf",
            link_mode="imported_file",
        )
        self.pdf_bytes = pdf_bytes
        self.probe_calls = 0
        self.download_calls = 0

    def probe(self) -> ZoteroConnection:
        self.probe_calls += 1
        return self.connection

    def list_recent_items(
        self,
        connection: ZoteroConnection,
        *,
        query: str,
        limit: int,
    ) -> list[ZoteroItem]:
        assert connection == self.connection
        assert limit == 20
        return [self.item] if not query or "linked" in query else []

    def list_pdf_attachments(
        self,
        connection: ZoteroConnection,
        item: ZoteroItem,
    ) -> list[ZoteroAttachment]:
        assert connection == self.connection
        assert item == self.item
        return [self.attachment]

    def download_pdf_attachment(
        self,
        connection: ZoteroConnection,
        attachment: ZoteroAttachment,
        *,
        max_size_bytes: int,
    ) -> ZoteroDownloadedFile:
        assert connection == self.connection
        assert attachment == self.attachment
        assert len(self.pdf_bytes) <= max_size_bytes
        self.download_calls += 1
        return ZoteroDownloadedFile(
            filename=attachment.filename,
            content=self.pdf_bytes,
        )


def test_zotero_stays_off_until_explicitly_enabled() -> None:
    client = FakeZoteroClient(b"%PDF-1.7\n")

    with pytest.raises(ConfigError, match="ZOTERO_LOCAL_API_ENABLED"):
        use_cases.browse_zotero_items(
            settings=Settings(zotero_local_api_enabled=False),
            client=client,
        )

    assert client.probe_calls == 0


def test_selected_zotero_pdf_imports_links_and_reopens_after_restart(
    tmp_path: Path,
    single_page_pdf: Path,
) -> None:
    settings = Settings(
        researchmind_data_dir=tmp_path / "library",
        zotero_local_api_enabled=True,
    )
    client = FakeZoteroClient(single_page_pdf.read_bytes())

    browse = use_cases.browse_zotero_items(
        query="linked",
        settings=settings,
        client=client,
    )
    details = use_cases.get_zotero_item_details(
        browse,
        client.item.item_key,
        settings=settings,
        client=client,
    )
    imported = use_cases.import_zotero_pdf_attachment(
        details,
        client.attachment.item_key,
        confirmed=True,
        settings=settings,
        client=client,
    )

    link = use_cases.get_zotero_source_link(
        imported.entry.record.id,
        settings=settings,
    )
    reopened = use_cases.open_library_paper(
        imported.entry.record.id,
        settings=settings,
    )

    assert imported.duplicate is False
    assert link is not None
    assert link.server_id == "server-A"
    assert link.item_key == client.item.item_key
    assert link.attachment_key == client.attachment.item_key
    assert reopened.document.title == "Fixture Research Paper"
    assert client.download_calls == 1

    with pytest.raises(LibraryConflictError, match="already linked"):
        use_cases.import_zotero_pdf_attachment(
            details,
            client.attachment.item_key,
            confirmed=True,
            settings=settings,
            client=client,
        )
    assert client.download_calls == 1

    assert use_cases.unlink_zotero_item_from_paper(
        imported.entry.record.id,
        confirmed=True,
        settings=settings,
    ) is True
    assert use_cases.get_zotero_source_link(
        imported.entry.record.id,
        settings=settings,
    ) is None
    assert use_cases.open_library_paper(
        imported.entry.record.id,
        settings=settings,
    ).document.title == "Fixture Research Paper"


def test_existing_managed_paper_can_link_without_downloading_again(
    tmp_path: Path,
    single_page_pdf: Path,
) -> None:
    settings = Settings(
        researchmind_data_dir=tmp_path / "library",
        zotero_local_api_enabled=True,
    )
    client = FakeZoteroClient(single_page_pdf.read_bytes())
    imported = use_cases.import_pdf_to_library(
        UploadedFileData(
            name="existing.pdf",
            content=single_page_pdf.read_bytes(),
        ),
        settings=settings,
    )
    browse = use_cases.browse_zotero_items(
        settings=settings,
        client=client,
    )
    details = use_cases.get_zotero_item_details(
        browse,
        client.item.item_key,
        settings=settings,
        client=client,
    )

    link = use_cases.link_zotero_item_to_paper(
        imported.entry.record.id,
        details,
        confirmed=True,
        settings=settings,
    )

    assert link.record_id == imported.entry.record.id
    assert link.attachment_key is None
    assert client.download_calls == 0

    with pytest.raises(LibraryConflictError, match="already linked"):
        use_cases.import_zotero_pdf_attachment(
            details,
            client.attachment.item_key,
            confirmed=True,
            settings=settings,
            client=client,
        )
    assert use_cases.get_zotero_source_link(
        imported.entry.record.id, settings=settings,
    ) == link
    assert client.download_calls == 0


def test_linked_paper_requires_explicit_unlink_before_copy_deletion(
    tmp_path: Path,
    single_page_pdf: Path,
) -> None:
    settings = Settings(
        researchmind_data_dir=tmp_path / "library",
        zotero_local_api_enabled=True,
    )
    client = FakeZoteroClient(single_page_pdf.read_bytes())
    details = ZoteroItemDetails(
        connection=client.connection,
        item=client.item,
        attachments=(client.attachment,),
    )
    imported = use_cases.import_zotero_pdf_attachment(
        details, client.attachment.item_key,
        confirmed=True, settings=settings, client=client,
    )
    record_id = imported.entry.record.id
    use_cases.remove_library_record(record_id, confirmed=True, settings=settings)
    with pytest.raises(LibraryConfirmationError, match="unlink"):
        use_cases.delete_library_managed_copies(
            record_id, confirmed=True, settings=settings,
        )
    assert use_cases.get_zotero_source_link(record_id, settings=settings)
    use_cases.unlink_zotero_item_from_paper(
        record_id, confirmed=True, settings=settings,
    )
    assert use_cases.delete_library_managed_copies(
        record_id, confirmed=True, settings=settings,
    ) == 1
    assert single_page_pdf.exists()
