"""Read one approved Windows PDF, never follow links or write source files.

Keep every ancestor handle open without write/delete sharing until reading ends.
This prevents a checked directory or file being swapped before the next open.
Non-Windows systems fail closed until an equivalent boundary is implemented.
"""

from contextlib import ExitStack
import ctypes
from ctypes import wintypes
import os
from pathlib import PureWindowsPath
import re
from urllib.parse import unquote, urlsplit

from researchmind.integration.zotero.errors import ZoteroProtocolError


def _windows_path(raw: str) -> PureWindowsPath:
    normalized = raw.replace("\\", "/")
    if not re.match(r"^[A-Za-z]:/", normalized):
        raise ZoteroProtocolError("Only absolute local drive paths are allowed.")
    parts = normalized[3:].split("/")
    if any(
        not part or part in {".", ".."} or part.endswith((" ", "."))
        or any(ord(c) < 32 or c in '<>:"|?*' for c in part)
        or PureWindowsPath(part).is_reserved()
        for part in parts
    ):
        raise ZoteroProtocolError("Unsafe attachment path components were rejected.")
    return PureWindowsPath(normalized)


def validate_attachment_location(url: str, approved_root: str) -> PureWindowsPath:
    """Lexical validation only; do not touch disk or normalize away traversal."""
    try:
        if len(url) > 8192 or any(ord(c) < 32 for c in url):
            raise ValueError
        parsed = urlsplit(url)
        if (
            parsed.scheme != "file" or parsed.netloc or parsed.query
            or parsed.fragment or not parsed.path.startswith("/")
            or "\\" in parsed.path or re.search(r"%(?![0-9a-fA-F]{2})", parsed.path)
        ):
            raise ValueError
        decoded = unquote(parsed.path, encoding="utf-8", errors="strict")
        path = _windows_path(decoded[1:])
        root = _windows_path(approved_root)
        if path.suffix.lower() != ".pdf" or not path.is_relative_to(root) or path == root:
            raise ValueError
        return path
    except (ValueError, UnicodeError):
        raise ZoteroProtocolError(
            "Attachment must be a local PDF inside the approved directory."
        ) from None


class _FileInformation(ctypes.Structure):
    _fields_ = [
        ("attributes", wintypes.DWORD),
        ("created", wintypes.FILETIME),
        ("accessed", wintypes.FILETIME),
        ("modified", wintypes.FILETIME),
        ("volume", wintypes.DWORD),
        ("size_high", wintypes.DWORD),
        ("size_low", wintypes.DWORD),
        ("links", wintypes.DWORD),
        ("index_high", wintypes.DWORD),
        ("index_low", wintypes.DWORD),
    ]


class _WindowsReadHandles:
    """Small ctypes boundary with explicit signatures (including 64-bit handles)."""

    def __init__(self) -> None:
        self.api = ctypes.WinDLL("kernel32", use_last_error=True)
        signatures = {
            "CreateFileW": ([wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD,
                             ctypes.c_void_p, wintypes.DWORD, wintypes.DWORD,
                             wintypes.HANDLE], wintypes.HANDLE),
            "CloseHandle": ([wintypes.HANDLE], wintypes.BOOL),
            "GetFileInformationByHandle": ([wintypes.HANDLE,
                                           ctypes.POINTER(_FileInformation)], wintypes.BOOL),
            "GetFinalPathNameByHandleW": ([wintypes.HANDLE, wintypes.LPWSTR,
                                          wintypes.DWORD, wintypes.DWORD], wintypes.DWORD),
            "GetDriveTypeW": ([wintypes.LPCWSTR], wintypes.UINT),
            "ReadFile": ([wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                          ctypes.POINTER(wintypes.DWORD), ctypes.c_void_p], wintypes.BOOL),
        }
        for name, (arguments, result) in signatures.items():
            function = getattr(self.api, name)
            function.argtypes = arguments
            function.restype = result

    def open(self, path: PureWindowsPath, *, directory: bool) -> int:
        # OPEN_EXISTING; OPEN_REPARSE_POINT prevents following the final component.
        # FILE_SHARE_READ only: do not permit write/delete handles during the copy.
        handle = self.api.CreateFileW(
            str(path), 0x80 if directory else 0x80000000, 1, None,
            3, 0x00200000 | 0x02000000, None,
        )
        if handle == ctypes.c_void_p(-1).value:
            raise ZoteroProtocolError(
                "Attachment is missing, locked, or not safely readable."
            )
        return handle

    def inspect(self, handle: int, path: PureWindowsPath, *, directory: bool) -> int:
        info = _FileInformation()
        if not self.api.GetFileInformationByHandle(handle, ctypes.byref(info)):
            raise ZoteroProtocolError("Unable to verify the attachment handle.")
        if (
            info.attributes & 0x400  # Any reparse point, including junctions/cloud placeholders.
            or bool(info.attributes & 0x10) != directory
            or (not directory and info.links != 1)
        ):
            raise ZoteroProtocolError("Links, reparse points, and non-regular PDFs are rejected.")
        buffer = ctypes.create_unicode_buffer(32768)
        length = self.api.GetFinalPathNameByHandleW(handle, buffer, len(buffer), 0)
        if not length or length >= len(buffer):
            raise ZoteroProtocolError("Unable to verify the final attachment location.")
        actual = buffer.value
        if not actual.startswith("\\\\?\\") or PureWindowsPath(actual[4:]) != path:
            raise ZoteroProtocolError("The opened attachment location changed or is unsafe.")
        return (info.size_high << 32) | info.size_low

    def read(self, handle: int, limit: int) -> bytes:
        chunks = []
        total = 0
        while total <= limit:
            buffer = ctypes.create_string_buffer(min(65536, limit + 1 - total))
            count = wintypes.DWORD()
            if not self.api.ReadFile(handle, buffer, len(buffer), ctypes.byref(count), None):
                raise ZoteroProtocolError("Unable to read the selected attachment safely.")
            if not count.value:
                break
            total += count.value
            chunks.append(buffer.raw[:count.value])
        if total > limit:
            raise ZoteroProtocolError("Attachment exceeds the configured size limit.")
        return b"".join(chunks)


def read_local_pdf(url: str, approved_root: str, *, max_size_bytes: int) -> bytes:
    """Return bounded bytes from one locked file; paths never leave this module."""
    path = validate_attachment_location(url, approved_root)
    if os.name != "nt":
        raise ZoteroProtocolError("Direct attachment copy currently requires Windows.")
    if max_size_bytes <= 0:
        raise ZoteroProtocolError("PDF size limit must be positive.")
    try:
        handles = _WindowsReadHandles()
        if handles.api.GetDriveTypeW(path.anchor) != 3:  # DRIVE_FIXED, excludes mapped network drives.
            raise ZoteroProtocolError("Only a fixed local disk is allowed for attachments.")
        chain = [*reversed(path.parents), path]
        with ExitStack() as cleanup:
            opened = []
            for component in chain:
                directory = component != path
                handle = handles.open(component, directory=directory)
                cleanup.callback(handles.api.CloseHandle, handle)
                size = handles.inspect(handle, component, directory=directory)
                opened.append((handle, component, directory))
            if size <= 0 or size > max_size_bytes:
                raise ZoteroProtocolError("Attachment exceeds the configured size limit or is empty.")
            content = handles.read(handle, max_size_bytes)
            for held_handle, component, directory in opened:
                final_size = handles.inspect(held_handle, component, directory=directory)
            if len(content) != size or final_size != size or not content.startswith(b"%PDF-"):
                raise ZoteroProtocolError("Attachment changed or is not a PDF file.")
            return content
    except OSError:
        raise ZoteroProtocolError("Unable to read the selected attachment safely.") from None
