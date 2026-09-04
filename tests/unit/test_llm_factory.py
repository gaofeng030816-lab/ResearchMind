"""Tests for constructing the configured V1 LLM provider."""

from __future__ import annotations

import pytest

from researchmind.config import Settings
from researchmind.llm import LlmConfigurationError, create_llm_provider
import researchmind.llm.factory as factory_module


def test_factory_passes_typed_settings_to_openai_compatible_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, str] = {}
    sentinel = object()

    def fake_provider(**kwargs: str) -> object:
        captured.update(kwargs)
        return sentinel

    monkeypatch.setattr(factory_module, "OpenAiCompatibleProvider", fake_provider)
    settings = Settings(
        llm_base_url="http://localhost:11434/v1",
        llm_api_key="local-placeholder-key",
        llm_api_key_header="api-key",
        llm_model="local-model",
    )

    provider = create_llm_provider(settings)

    assert provider is sentinel
    assert captured == {
        "api_key": "local-placeholder-key",
        "api_key_header": "api-key",
        "model": "local-model",
        "base_url": "http://localhost:11434/v1",
    }


@pytest.mark.parametrize(
    ("settings", "missing_key"),
    (
        (Settings(llm_model="model"), "LLM_API_KEY"),
        (Settings(llm_api_key="key"), "LLM_MODEL"),
    ),
)
def test_factory_reports_missing_required_configuration(
    settings: Settings,
    missing_key: str,
) -> None:
    with pytest.raises(LlmConfigurationError, match=missing_key):
        create_llm_provider(settings)
