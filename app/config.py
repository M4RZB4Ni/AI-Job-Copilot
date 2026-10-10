import os
from decimal import Decimal

from dotenv import load_dotenv

from app.core.cost_logger import validate_price
from app.core.exceptions import ConfigurationError, UsageValidationError
from app.core.enums import ProviderName

load_dotenv()


def _optional_price(name: str, default: str | None = None) -> Decimal | None:
    raw = os.environ.get(name, default)
    if raw is None or not raw.strip():
        return None
    try:
        return validate_price(raw)
    except UsageValidationError:
        raise ConfigurationError(
            f"{name} must be a finite, non-negative decimal USD value."
        ) from None


raw_provider = os.environ.get("LLM_PROVIDER", "anthropic").strip().lower()

try:
    LLM_PROVIDER = ProviderName(raw_provider)
except ValueError:
    raise ConfigurationError(
        f"Unknown LLM_PROVIDER '{raw_provider}'."
    ) from None

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")
ANTHROPIC_INPUT_COST_PER_MILLION = _optional_price("ANTHROPIC_INPUT_COST_PER_MILLION", "2")
ANTHROPIC_OUTPUT_COST_PER_MILLION = _optional_price("ANTHROPIC_OUTPUT_COST_PER_MILLION", "10")

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL")
OPENAI_INPUT_COST_PER_MILLION = _optional_price("OPENAI_INPUT_COST_PER_MILLION")
OPENAI_OUTPUT_COST_PER_MILLION = _optional_price("OPENAI_OUTPUT_COST_PER_MILLION")

DATABASE_URL = os.environ.get("DATABASE_URL", "")