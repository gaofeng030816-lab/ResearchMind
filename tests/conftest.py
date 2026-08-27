"""Shared pytest fixtures for ResearchMind."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from researchmind.llm import ChatMessage
from tests.fixtures.pdf_factory import (
    create_corrupt_pdf,
    create_text_pdf,
    create_two_column_pdf,
    create_unicode_math_pdf,
)


CONFIG_ENVIRONMENT_KEYS = (
    "LLM_BASE_URL",
    "LLM_API_KEY",
    "LLM_API_KEY_HEADER",
    "LLM_MODEL",
    "TRANSLATION_TARGET_LANGUAGE",
    "OBSIDIAN_VAULT_PATH",
    "OBSIDIAN_SUBDIRECTORY",
    "CONTEXT_TOKEN_BUDGET",
    "HISTORY_TOKEN_BUDGET",
    "PDF_MAX_SIZE_MB",
)


class FakeLlmProvider:
    """Deterministic provider recording every request without network access."""

    def __init__(self, responses: list[str] | None = None) -> None:
        self.responses = list(responses or ["Fake LLM response"])
        self.calls: list[tuple[list[ChatMessage], dict[str, object]]] = []

    def complete(
        self,
        messages: list[ChatMessage],
        **kwargs: object,
    ) -> str:
        self.calls.append((messages, kwargs))
        if not self.responses:
            raise AssertionError("FakeLlmProvider has no response left.")
        return self.responses.pop(0)


@pytest.fixture
def clean_config_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Remove ResearchMind configuration variables for an isolated test."""

    for key in CONFIG_ENVIRONMENT_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield


@pytest.fixture
def fake_llm_provider() -> FakeLlmProvider:
    """Return a deterministic provider for unit and integration tests."""

    return FakeLlmProvider()


@pytest.fixture
def single_page_pdf(tmp_path: Path) -> Path:
    return create_text_pdf(
        tmp_path / "single-page.pdf",
        [["ResearchMind introduction", "Second context block"]],
        title="Fixture Research Paper",
        author="Ada Researcher; Grace Scientist",
    )


@pytest.fixture
def multi_page_pdf(tmp_path: Path) -> Path:
    return create_text_pdf(
        tmp_path / "multi-page.pdf",
        [
            ["Page one unique text", "Shared optimization method"],
            ["Page two unique text", "Shared Optimization result"],
            ["Page three conclusion"],
        ],
    )


@pytest.fixture
def blank_page_pdf(tmp_path: Path) -> Path:
    return create_text_pdf(tmp_path / "blank-page.pdf", [[]])


@pytest.fixture
def unicode_math_pdf(tmp_path: Path) -> Path:
    return create_unicode_math_pdf(tmp_path / "unicode-math.pdf")


@pytest.fixture
def two_column_pdf(tmp_path: Path) -> Path:
    return create_two_column_pdf(tmp_path / "two-column.pdf")


@pytest.fixture
def corrupt_pdf(tmp_path: Path) -> Path:
    return create_corrupt_pdf(tmp_path / "corrupt.pdf")


@pytest.fixture
def temporary_vault(tmp_path: Path) -> Path:
    """Return an isolated directory standing in for the user's Obsidian Vault."""

    vault = tmp_path / "vault"
    vault.mkdir()
    return vault
