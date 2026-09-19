"""Supported static code languages and filename mapping."""

from pathlib import PurePosixPath

from researchmind.models import CodeLanguage


SUPPORTED_CODE_EXTENSIONS = frozenset({".py", ".c", ".h", ".java", ".jl", ".r"})
_LANGUAGE_BY_EXTENSION: dict[str, CodeLanguage] = {
    ".py": "python",
    ".c": "c",
    ".h": "c",
    ".java": "java",
    ".jl": "julia",
    ".r": "r",
}


def language_for_relative_path(relative_path: str) -> CodeLanguage | None:
    """Return the supported language identified only from a relative filename."""

    suffix = PurePosixPath(relative_path).suffix.lower()
    return _LANGUAGE_BY_EXTENSION.get(suffix)
