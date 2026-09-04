"""Application configuration loaded from environment variables or a .env file."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
import os
from pathlib import Path

from dotenv import dotenv_values


DEFAULT_LLM_BASE_URL = "https://api.openai.com/v1"
DEFAULT_LLM_API_KEY_HEADER = "Authorization"
DEFAULT_TARGET_LANGUAGE = "zh-CN"
DEFAULT_OBSIDIAN_SUBDIRECTORY = "ResearchMind"
DEFAULT_CONTEXT_TOKEN_BUDGET = 6_000
DEFAULT_HISTORY_TOKEN_BUDGET = 3_000
DEFAULT_PDF_MAX_SIZE_MB = 50


class ConfigError(ValueError):
    """Raised when a configuration value cannot be parsed safely."""


@dataclass(frozen=True)
class Settings:
    """Typed ResearchMind settings.

    Credentials are optional during startup so the local PDF workflow and tests
    do not require a configured network provider. Provider use cases will require
    them at their own boundary.
    """

    llm_base_url: str = DEFAULT_LLM_BASE_URL
    llm_api_key: str | None = field(default=None, repr=False)
    llm_api_key_header: str = DEFAULT_LLM_API_KEY_HEADER
    llm_model: str | None = None
    target_language: str = DEFAULT_TARGET_LANGUAGE
    researchmind_data_dir: Path | None = None
    zotero_local_api_enabled: bool = False
    obsidian_vault_path: Path | None = None
    obsidian_subdirectory: str = DEFAULT_OBSIDIAN_SUBDIRECTORY
    context_token_budget: int = DEFAULT_CONTEXT_TOKEN_BUDGET
    history_token_budget: int = DEFAULT_HISTORY_TOKEN_BUDGET
    pdf_max_size_bytes: int = DEFAULT_PDF_MAX_SIZE_MB * 1024 * 1024


def load_settings(
    env_file: Path | None = None,
    *,
    env: Mapping[str, str] | None = None,
    secrets: Mapping[str, object] | None = None,
) -> Settings:
    """Load settings with process environment values taking highest priority.

    Passing ``env`` makes the function deterministic for tests and callers that
    already own a configuration mapping. When it is omitted, the process
    environment is used, a project ``.env`` file is discovered automatically,
    and root-level Streamlit secrets are read when available. Precedence is
    process environment, Streamlit secrets, then ``.env``.
    """

    file_values = _load_env_file(env_file, skip_default_search=env is not None)
    secret_values = (
        _load_streamlit_secrets()
        if env is None and secrets is None
        else _normalize_config_values(secrets or {})
    )
    process_values = os.environ if env is None else env
    values = {**file_values, **secret_values, **process_values}

    pdf_max_size_mb = _positive_int(
        values,
        "PDF_MAX_SIZE_MB",
        DEFAULT_PDF_MAX_SIZE_MB,
    )

    return Settings(
        llm_base_url=_text_or_default(
            values,
            "LLM_BASE_URL",
            DEFAULT_LLM_BASE_URL,
        ),
        llm_api_key=_optional_text(values, "LLM_API_KEY"),
        llm_api_key_header=_text_or_default(
            values,
            "LLM_API_KEY_HEADER",
            DEFAULT_LLM_API_KEY_HEADER,
        ),
        llm_model=_optional_text(values, "LLM_MODEL"),
        target_language=_text_or_default(
            values,
            "TRANSLATION_TARGET_LANGUAGE",
            DEFAULT_TARGET_LANGUAGE,
        ),
        researchmind_data_dir=_optional_path(
            values,
            "RESEARCHMIND_DATA_DIR",
        ),
        zotero_local_api_enabled=_boolean(
            values,
            "ZOTERO_LOCAL_API_ENABLED",
            False,
        ),
        obsidian_vault_path=_optional_path(values, "OBSIDIAN_VAULT_PATH"),
        obsidian_subdirectory=_text_or_default(
            values,
            "OBSIDIAN_SUBDIRECTORY",
            DEFAULT_OBSIDIAN_SUBDIRECTORY,
        ),
        context_token_budget=_positive_int(
            values,
            "CONTEXT_TOKEN_BUDGET",
            DEFAULT_CONTEXT_TOKEN_BUDGET,
        ),
        history_token_budget=_positive_int(
            values,
            "HISTORY_TOKEN_BUDGET",
            DEFAULT_HISTORY_TOKEN_BUDGET,
        ),
        pdf_max_size_bytes=pdf_max_size_mb * 1024 * 1024,
    )


def _load_env_file(
    env_file: Path | None,
    *,
    skip_default_search: bool,
) -> dict[str, str]:
    if skip_default_search and env_file is None:
        return {}

    raw_values = dotenv_values(dotenv_path=env_file)
    return {
        key: value
        for key, value in raw_values.items()
        if value is not None
    }


def _load_streamlit_secrets() -> dict[str, str]:
    """Read root-level Streamlit secrets without requiring a secrets file."""

    try:
        from streamlit import secrets as streamlit_secrets
        from streamlit.errors import StreamlitSecretNotFoundError

        return _normalize_config_values(streamlit_secrets)
    except (ImportError, StreamlitSecretNotFoundError):
        return {}


def _normalize_config_values(
    values: Mapping[str, object],
) -> dict[str, str]:
    return {
        str(key): str(value)
        for key, value in values.items()
        if value is not None
    }


def _optional_text(values: Mapping[str, str], key: str) -> str | None:
    value = values.get(key)
    if value is None:
        return None

    normalized = value.strip()
    return normalized or None


def _text_or_default(
    values: Mapping[str, str],
    key: str,
    default: str,
) -> str:
    return _optional_text(values, key) or default


def _optional_path(values: Mapping[str, str], key: str) -> Path | None:
    value = _optional_text(values, key)
    return Path(value).expanduser() if value is not None else None


def _positive_int(
    values: Mapping[str, str],
    key: str,
    default: int,
) -> int:
    raw_value = _optional_text(values, key)
    if raw_value is None:
        return default

    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ConfigError(f"{key} must be a positive integer.") from exc

    if value <= 0:
        raise ConfigError(f"{key} must be a positive integer.")

    return value


def _boolean(
    values: Mapping[str, str],
    key: str,
    default: bool,
) -> bool:
    raw_value = _optional_text(values, key)
    if raw_value is None:
        return default
    normalized = raw_value.casefold()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ConfigError(
        f"{key} must be true/false, yes/no, on/off, or 1/0."
    )
