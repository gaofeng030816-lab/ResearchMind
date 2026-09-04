"""Pure validation and candidate-building rules for approved T5-B1 changes."""

from __future__ import annotations

import ast
from dataclasses import replace
from difflib import SequenceMatcher, unified_diff
from hashlib import sha256

from researchmind.models import (
    CodeChangeProposal,
    CodeFile,
    CodeFileSnapshot,
    CodeProject,
    CodeSelection,
)


MAX_CODE_REPLACEMENT_CHARACTERS = 20_000
MAX_CHANGED_LINES = 400
MAX_CODE_CHANGE_FILE_BYTES = 1 * 1024 * 1024


def validate_code_change_snapshot(
    project: CodeProject,
    selection: CodeSelection,
    snapshot: CodeFileSnapshot,
) -> CodeFile:
    """Confirm project, selection, index, and current disk snapshot still agree."""

    if selection.project_id != project.id or snapshot.project_id != project.id:
        raise ValueError("Code change source does not belong to the opened project.")
    if (
        selection.relative_path != snapshot.relative_path
        or not snapshot.relative_path.endswith(".py")
    ):
        raise ValueError("Code change source must be the selected Python file.")
    code_file = next(
        (
            item
            for item in project.files
            if item.relative_path == snapshot.relative_path
        ),
        None,
    )
    if code_file is None:
        raise ValueError("Code change source is not part of the opened project.")
    if code_file.source != snapshot.source:
        raise ValueError(
            "Python source changed since it was indexed; reopen the code folder."
        )
    source_lines = snapshot.source.splitlines()
    if (
        selection.start_line < 1
        or selection.end_line < selection.start_line
        or selection.end_line > len(source_lines)
    ):
        raise ValueError("Code selection line range is no longer valid.")
    current_selection = "\n".join(
        source_lines[selection.start_line - 1 : selection.end_line]
    )
    if current_selection != selection.text:
        raise ValueError(
            "Code selection changed since it was created; select the lines again."
        )
    return code_file


def build_code_change_proposal(
    project: CodeProject,
    selection: CodeSelection,
    snapshot: CodeFileSnapshot,
    *,
    replacement_text: str,
) -> CodeChangeProposal:
    """Build one syntax-valid candidate and a relative-path-only unified diff."""

    validate_code_change_snapshot(project, selection, snapshot)
    if not replacement_text.strip():
        raise ValueError("Code replacement must not be blank.")
    if len(replacement_text) > MAX_CODE_REPLACEMENT_CHARACTERS:
        raise ValueError(
            "Code replacement exceeds the "
            f"{MAX_CODE_REPLACEMENT_CHARACTERS:,}-character limit."
        )
    if "\x00" in replacement_text:
        raise ValueError("Code replacement contains a null character.")

    original_lines = snapshot.source.splitlines()[
        selection.start_line - 1 : selection.end_line
    ]
    normalized_replacement = _normalized_replacement(replacement_text)
    replacement_lines = normalized_replacement.split("\n")
    changed_line_count = _changed_line_count(original_lines, replacement_lines)
    if changed_line_count == 0:
        raise ValueError("Code replacement does not change the selected lines.")
    if changed_line_count > MAX_CHANGED_LINES:
        raise ValueError(
            f"Code replacement changes {changed_line_count} lines; "
            f"maximum {MAX_CHANGED_LINES}."
        )

    candidate_source = _splice_source(
        snapshot.source,
        start_line=selection.start_line,
        end_line=selection.end_line,
        replacement=normalized_replacement,
    )
    try:
        candidate_bytes = candidate_source.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError("Candidate file cannot be encoded as UTF-8.") from exc
    raw_candidate = (
        b"\xef\xbb\xbf" + candidate_bytes
        if snapshot.has_utf8_bom
        else candidate_bytes
    )
    if len(raw_candidate) > MAX_CODE_CHANGE_FILE_BYTES:
        raise ValueError(
            "Candidate Python file exceeds the 1 MiB T5-B1 limit."
        )
    try:
        ast.parse(candidate_source, filename=snapshot.relative_path)
    except SyntaxError as exc:
        line_number = exc.lineno or "unknown"
        raise ValueError(
            "Candidate file is not valid Python syntax "
            f"(line {line_number}); nothing was written."
        ) from exc

    diff = "\n".join(
        unified_diff(
            snapshot.source.splitlines(),
            candidate_source.splitlines(),
            fromfile=f"a/{snapshot.relative_path}",
            tofile=f"b/{snapshot.relative_path}",
            lineterm="",
        )
    )
    return CodeChangeProposal(
        project_id=project.id,
        selection_id=selection.id,
        relative_path=snapshot.relative_path,
        start_line=selection.start_line,
        end_line=selection.end_line,
        original_sha256=snapshot.raw_sha256,
        candidate_sha256=sha256(raw_candidate).hexdigest(),
        replacement_text=normalized_replacement,
        candidate_source=candidate_source,
        unified_diff=diff,
        replacement_character_count=len(normalized_replacement),
        changed_line_count=changed_line_count,
        syntax_valid=True,
        has_utf8_bom=snapshot.has_utf8_bom,
    )


def replace_code_project_file(
    project: CodeProject,
    updated_file: CodeFile,
) -> CodeProject:
    """Replace one indexed file while preserving project identity and ordering."""

    previous = next(
        (
            item
            for item in project.files
            if item.relative_path == updated_file.relative_path
        ),
        None,
    )
    if previous is None:
        raise ValueError("Updated Python file is not part of the opened project.")
    files = tuple(
        updated_file if item.relative_path == updated_file.relative_path else item
        for item in project.files
    )
    return replace(
        project,
        files=files,
        total_source_bytes=(
            project.total_source_bytes
            - previous.size_bytes
            + updated_file.size_bytes
        ),
    )


def _normalized_replacement(replacement: str) -> str:
    normalized = replacement.replace("\r\n", "\n").replace("\r", "\n")
    if normalized.endswith("\n"):
        normalized = normalized[:-1]
    return normalized


def _changed_line_count(
    original_lines: list[str],
    replacement_lines: list[str],
) -> int:
    matcher = SequenceMatcher(
        None,
        original_lines,
        replacement_lines,
        autojunk=False,
    )
    return sum(
        (original_end - original_start)
        + (replacement_end - replacement_start)
        for tag, original_start, original_end, replacement_start, replacement_end
        in matcher.get_opcodes()
        if tag != "equal"
    )


def _splice_source(
    source: str,
    *,
    start_line: int,
    end_line: int,
    replacement: str,
) -> str:
    source_lines = source.splitlines(keepends=True)
    newline = _source_newline(source)
    replacement_segment = newline.join(replacement.split("\n"))
    selected_segment = source_lines[start_line - 1 : end_line]
    selection_had_terminator = bool(
        selected_segment
        and selected_segment[-1].endswith(("\n", "\r"))
    )
    if end_line < len(source_lines) or selection_had_terminator:
        replacement_segment += newline
    return "".join(
        (
            "".join(source_lines[: start_line - 1]),
            replacement_segment,
            "".join(source_lines[end_line:]),
        )
    )


def _source_newline(source: str) -> str:
    if "\r\n" in source:
        return "\r\n"
    if "\r" in source:
        return "\r"
    return "\n"
