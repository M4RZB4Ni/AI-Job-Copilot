from app.config import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_INPUT_COST_PER_MILLION,
    ANTHROPIC_MODEL,
    ANTHROPIC_OUTPUT_COST_PER_MILLION,
    LLM_PROVIDER,
    OPENAI_API_KEY,
    OPENAI_INPUT_COST_PER_MILLION,
    OPENAI_MODEL,
    OPENAI_OUTPUT_COST_PER_MILLION,
)
from app.core.exceptions import ConfigurationError
from app.services.providers.anthropic_provider import AnthropicProvider
from app.services.providers.base import LLMProvider
from app.services.providers.openai_provider import OpenAIProvider
from app.core.enums import ProviderName


def build_provider() -> LLMProvider:
    if LLM_PROVIDER == ProviderName.ANTHROPIC:
        if not ANTHROPIC_API_KEY:
            raise ConfigurationError("ANTHROPIC_API_KEY is not set. Add it to your .env file.")
        return AnthropicProvider(
            ANTHROPIC_API_KEY,
            ANTHROPIC_MODEL,
            ANTHROPIC_INPUT_COST_PER_MILLION,
            ANTHROPIC_OUTPUT_COST_PER_MILLION,
        )
    if LLM_PROVIDER == ProviderName.OPENAI:
        if not OPENAI_API_KEY or not OPENAI_MODEL:
            raise ConfigurationError("OPENAI_API_KEY and OPENAI_MODEL must be set to use OpenAI.")
        return OpenAIProvider(
            OPENAI_API_KEY,
            OPENAI_MODEL,
            OPENAI_INPUT_COST_PER_MILLION,
            OPENAI_OUTPUT_COST_PER_MILLION,
        )
    raise ConfigurationError(f"Unknown LLM_PROVIDER '{LLM_PROVIDER}'. Use 'anthropic' or 'openai'.")