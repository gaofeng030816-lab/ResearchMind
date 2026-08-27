"""Factory for the configured V1 language-model provider."""

from researchmind.config import Settings
from researchmind.llm.base import LlmProvider
from researchmind.llm.errors import LlmConfigurationError
from researchmind.llm.providers.openai_compatible import OpenAiCompatibleProvider


def create_llm_provider(settings: Settings) -> LlmProvider:
    """Construct the single V1 OpenAI-compatible provider from typed settings."""

    if settings.llm_api_key is None:
        raise LlmConfigurationError(
            "LLM_API_KEY is not configured. Add it before using AI features."
        )
    if settings.llm_model is None:
        raise LlmConfigurationError(
            "LLM_MODEL is not configured. Add it before using AI features."
        )

    return OpenAiCompatibleProvider(
        api_key=settings.llm_api_key,
        api_key_header=settings.llm_api_key_header,
        model=settings.llm_model,
        base_url=settings.llm_base_url,
    )
