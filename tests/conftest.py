"""Shared pytest fixtures for ResearchMind."""

from collections.abc import Iterator

import pytest


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


@pytest.fixture
def clean_config_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Remove ResearchMind configuration variables for an isolated test."""

    for key in CONFIG_ENVIRONMENT_KEYS:
        monkeypatch.delenv(key, raising=False)
    yield
