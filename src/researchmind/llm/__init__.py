"""Public LLM provider and prompt infrastructure API."""

from researchmind.llm.base import ChatMessage, ChatRole, LlmProvider
from researchmind.llm.errors import (
    LlmApiError,
    LlmBadResponseError,
    LlmConfigurationError,
    LlmError,
)
from researchmind.llm.factory import create_llm_provider
from researchmind.llm.formula_recognizer import (
    canonicalize_formula_latex,
    FormulaRecognizer,
    OpenAiCompatibleFormulaRecognizer,
    create_formula_recognizer,
)
from researchmind.llm.code_change import parse_code_replacement
from researchmind.llm.latex import parse_latex_response
from researchmind.llm.read_only_assistant import parse_assistant_action
from researchmind.llm.prompts import (
    CodePromptBuilder,
    PromptBuilder,
    build_algorithm_prompt,
    build_code_change_prompt,
    build_code_explanation_prompt,
    build_concept_prompt,
    build_contextual_prompt,
    build_followup_prompt,
    build_latex_prompt,
    build_math_prompt,
    build_read_only_assistant_prompt,
)

__all__ = [
    "ChatMessage",
    "ChatRole",
    "CodePromptBuilder",
    "LlmApiError",
    "LlmBadResponseError",
    "LlmConfigurationError",
    "LlmError",
    "LlmProvider",
    "FormulaRecognizer",
    "OpenAiCompatibleFormulaRecognizer",
    "PromptBuilder",
    "build_algorithm_prompt",
    "build_code_change_prompt",
    "build_code_explanation_prompt",
    "build_concept_prompt",
    "build_contextual_prompt",
    "build_followup_prompt",
    "build_latex_prompt",
    "build_math_prompt",
    "build_read_only_assistant_prompt",
    "create_llm_provider",
    "create_formula_recognizer",
    "parse_assistant_action",
    "parse_code_replacement",
    "parse_latex_response",
]
