"""Only synthetic files: exercise the Windows attachment read boundary."""

import os
from pathlib import Path

import pytest

from researchmind.integration.zotero.errors import ZoteroProtocolError
from researchmind.integration.zotero.local_files import (
    read_local_pdf,
    validate_attachment_location,
)


@pytest.mark.parametrize("url", [
    "https://example.invalid/paper.pdf", "file://server/share/paper.pdf",
    "file:///C:/approved/../private.pdf", "file:///C:/approved/%2e%2e/private.pdf",
    "file:///C:/approved/paper.pdf:secret", "file:///C:/approved/paper.pdf?x=1",
    "file:///C:/approved/paper.pdf#x", "file:///C:/approved/paper.pdf%00",
    "file:////?/C:/approved/paper.pdf", "file:///C:/approved/CON.pdf",
    "file:///C:/approved/sub./paper.pdf", "file:///C:/approved/not.txt",
    "file:///C:/approved-other/paper.pdf", "file:///D:/approved/paper.pdf",
    "file:///C:/approved/%ZZ.pdf", "file:///C:/approved//paper.pdf",
])
def test_rejects_unsafe_locations_without_io(url: str) -> None:
    with pytest.raises(ZoteroProtocolError):
        validate_attachment_location(url, "C:/approved")


def test_accepts_encoded_unicode_and_spaces() -> None:
    path = validate_attachment_location(
        "file:///C:/approved/%E6%95%B0%E5%AD%A6%20paper.pdf", "C:/approved",
    )
    assert path.name == "数学 paper.pdf"


@pytest.mark.skipif(os.name != "nt", reason="Windows handle boundary")
def test_reads_one_pdf_without_modifying_source(tmp_path: Path) -> None:
    source = tmp_path / "paper.pdf"
    data = b"%PDF-1.7\nsynthetic"
    source.write_bytes(data)
    before = source.stat()
    assert read_local_pdf(source.as_uri(), str(tmp_path), max_size_bytes=100) == data
    after = source.stat()
    assert source.read_bytes() == data
    assert before.st_mtime_ns == after.st_mtime_ns


@pytest.mark.skipif(os.name != "nt", reason="Windows handle boundary")
@pytest.mark.parametrize("content,limit", [(b"not pdf", 100), (b"%PDF-1.7", 4)])
def test_invalid_content_and_size_are_private_errors(
    tmp_path: Path, content: bytes, limit: int,
) -> None:
    source = tmp_path / "private-name.pdf"
    source.write_bytes(content)
    with pytest.raises(ZoteroProtocolError) as caught:
        read_local_pdf(source.as_uri(), str(tmp_path), max_size_bytes=limit)
    assert str(tmp_path) not in str(caught.value)
    assert source.name not in str(caught.value)


@pytest.mark.skipif(os.name != "nt", reason="Windows handle boundary")
def test_junction_and_hardlink_are_rejected_without_reading(tmp_path: Path, monkeypatch) -> None:
    import _winapi
    from researchmind.integration.zotero import local_files
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "paper.pdf").write_bytes(b"%PDF-1.7\n")
    root = tmp_path / "approved"
    root.mkdir()
    junction = root / "alias"
    _winapi.CreateJunction(str(outside), str(junction))
    hardlink = root / "hardlink.pdf"
    os.link(outside / "paper.pdf", hardlink)
    def forbid(*args):
        raise AssertionError("Rejected alias reached file reading")
    monkeypatch.setattr(local_files._WindowsReadHandles, "read", forbid)
    try:
        for source, approved in [(junction / "paper.pdf", root),
                                 (junction / "paper.pdf", junction), (hardlink, root)]:
            with pytest.raises(ZoteroProtocolError, match="Links"):
                read_local_pdf(source.as_uri(), str(approved), max_size_bytes=100)
    finally:
        junction.rmdir()  # Remove this test's junction, never its target.


@pytest.mark.skipif(os.name != "nt", reason="Windows handle boundary")
def test_open_handles_prevent_write_delete_and_ancestor_swap(tmp_path: Path, monkeypatch) -> None:
    from researchmind.integration.zotero import local_files
    root = tmp_path / "approved"
    folder = root / "attachment"
    folder.mkdir(parents=True)
    source = folder / "paper.pdf"
    source.write_bytes(b"%PDF-1.7\noriginal")
    replacement = tmp_path / "replacement.pdf"
    replacement.write_bytes(b"%PDF-1.7\nreplacement")
    original_read = local_files._WindowsReadHandles.read
    def try_swaps(self, handle, limit):
        with pytest.raises(OSError):
            os.replace(replacement, source)
        with pytest.raises(OSError):
            source.unlink()
        with pytest.raises(OSError):
            source.write_bytes(b"overwrite")
        with pytest.raises(OSError):
            folder.rename(root / "moved")
        with pytest.raises(OSError):
            root.rename(tmp_path / "moved-root")
        return original_read(self, handle, limit)
    monkeypatch.setattr(local_files._WindowsReadHandles, "read", try_swaps)
    assert read_local_pdf(source.as_uri(), str(root), max_size_bytes=100).endswith(b"original")
    source.rename(folder / "renamed.pdf")  # Handles were released after success.


@pytest.mark.skipif(os.name != "nt", reason="Windows handle boundary")
def test_existing_writer_is_rejected_and_handles_close_on_failure(tmp_path: Path, monkeypatch) -> None:
    from researchmind.integration.zotero import local_files
    source = tmp_path / "paper.pdf"
    source.write_bytes(b"%PDF-1.7\n")
    with source.open("r+b"):
        with pytest.raises(ZoteroProtocolError, match="locked"):
            read_local_pdf(source.as_uri(), str(tmp_path), max_size_bytes=100)
    def fail(*args):
        raise ZoteroProtocolError("Injected read failure")
    monkeypatch.setattr(local_files._WindowsReadHandles, "read", fail)
    with pytest.raises(ZoteroProtocolError, match="Injected"):
        read_local_pdf(source.as_uri(), str(tmp_path), max_size_bytes=100)
    source.rename(tmp_path / "after-failure.pdf")


@pytest.mark.skipif(os.name != "nt", reason="Windows handle boundary")
def test_mapped_network_drive_is_rejected_before_open(tmp_path: Path, monkeypatch) -> None:
    from researchmind.integration.zotero import local_files
    class NetworkOnly:
        api = type("Api", (), {"GetDriveTypeW": staticmethod(lambda drive: 4)})()
        def open(self, *args, **kwargs):
            raise AssertionError("Network drive reached open")
    monkeypatch.setattr(local_files, "_WindowsReadHandles", NetworkOnly)
    with pytest.raises(ZoteroProtocolError, match="fixed local"):
        read_local_pdf((tmp_path / "paper.pdf").as_uri(), str(tmp_path), max_size_bytes=100)
