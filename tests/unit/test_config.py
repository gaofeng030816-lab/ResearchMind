"""Tests for centralized ResearchMind configuration loading."""

from pathlib import Path

import pytest

from researchmind.config import (
    ConfigError,
    DEFAULT_LLM_API_KEY_HEADER,
    DEFAULT_CONTEXT_TOKEN_BUDGET,
    DEFAULT_HISTORY_TOKEN_BUDGET,
    DEFAULT_LLM_BASE_URL,
    DEFAULT_OBSIDIAN_SUBDIRECTORY,
    DEFAULT_PDF_MAX_SIZE_MB,
    DEFAULT_TARGET_LANGUAGE,
    load_settings,
)


def test_load_settings_uses_safe_defaults() -> None:
    settings = load_settings(env={})

    assert settings.llm_base_url == DEFAULT_LLM_BASE_URL
    assert settings.llm_api_key is None
    assert settings.llm_api_key_header == DEFAULT_LLM_API_KEY_HEADER
    assert settings.llm_model is None
    assert settings.target_language == DEFAULT_TARGET_LANGUAGE
    assert settings.researchmind_data_dir is None
    assert settings.zotero_local_api_enabled is False
    assert settings.obsidian_vault_path is None
    assert settings.obsidian_subdirectory == DEFAULT_OBSIDIAN_SUBDIRECTORY
    assert settings.context_token_budget == DEFAULT_CONTEXT_TOKEN_BUDGET
    assert settings.history_token_budget == DEFAULT_HISTORY_TOKEN_BUDGET
    assert settings.pdf_max_size_bytes == DEFAULT_PDF_MAX_SIZE_MB * 1024 * 1024


def test_load_settings_reads_dotenv_without_leaking_key_in_repr(
    tmp_path: Path,
    clean_config_environment: None,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            (
                "LLM_BASE_URL=http://localhost:11434/v1",
                "LLM_API_KEY=test-secret-value",
                "LLM_API_KEY_HEADER=api-key",
                "LLM_MODEL=local-model",
                "TRANSLATION_TARGET_LANGUAGE=zh-TW",
                f"RESEARCHMIND_DATA_DIR={(tmp_path / 'library').as_posix()}",
                "ZOTERO_LOCAL_API_ENABLED=true",
                f"OBSIDIAN_VAULT_PATH={tmp_path.as_posix()}",
                "OBSIDIAN_SUBDIRECTORY=Research Notes",
                "CONTEXT_TOKEN_BUDGET=7000",
                "HISTORY_TOKEN_BUDGET=2500",
                "PDF_MAX_SIZE_MB=12",
            )
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file, env={})

    assert settings.llm_base_url == "http://localhost:11434/v1"
    assert settings.llm_api_key == "test-secret-value"
    assert settings.llm_api_key_header == "api-key"
    assert settings.llm_model == "local-model"
    assert settings.target_language == "zh-TW"
    assert settings.researchmind_data_dir == tmp_path / "library"
    assert settings.zotero_local_api_enabled is True
    assert settings.obsidian_vault_path == tmp_path
    assert settings.obsidian_subdirectory == "Research Notes"
    assert settings.context_token_budget == 7_000
    assert settings.history_token_budget == 2_500
    assert settings.pdf_max_size_bytes == 12 * 1024 * 1024
    assert "test-secret-value" not in repr(settings)


def test_process_environment_overrides_dotenv(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("LLM_MODEL=file-model\n", encoding="utf-8")

    settings = load_settings(env_file, env={"LLM_MODEL": "environment-model"})

    assert settings.llm_model == "environment-model"


def test_streamlit_secrets_override_dotenv_but_environment_wins(
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        "LLM_API_KEY=file-key\nLLM_MODEL=file-model\n",
        encoding="utf-8",
    )

    settings = load_settings(
        env_file,
        env={"LLM_MODEL": "environment-model"},
        secrets={
            "LLM_API_KEY": "streamlit-key",
            "LLM_MODEL": "streamlit-model",
        },
    )

    assert settings.llm_api_key == "streamlit-key"
    assert settings.llm_model == "environment-model"
    assert "streamlit-key" not in repr(settings)


@pytest.mark.parametrize(
    ("key", "value"),
    (
        ("CONTEXT_TOKEN_BUDGET", "0"),
        ("HISTORY_TOKEN_BUDGET", "-1"),
        ("PDF_MAX_SIZE_MB", "not-a-number"),
    ),
)
def test_positive_integer_settings_reject_invalid_values(
    key: str,
    value: str,
) -> None:
    with pytest.raises(ConfigError, match=key):
        load_settings(env={key: value})


def test_zotero_boolean_setting_rejects_ambiguous_values() -> None:
    with pytest.raises(ConfigError, match="ZOTERO_LOCAL_API_ENABLED"):
        load_settings(env={"ZOTERO_LOCAL_API_ENABLED": "maybe"})
