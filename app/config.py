import os
from dotenv import load_dotenv
from app.core.cost_logger import validate_price
from app.core.exceptions import ConfigurationError, UsageValidationError

load_dotenv()

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

if not ANTHROPIC_API_KEY:
    raise ConfigurationError("ANTHROPIC_API_KEY is not set. Add it to your .env file.")

DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not DATABASE_URL:
    raise ConfigurationError("DATABASE_URL is not set. Add it to your .env file.")

# Standard Claude Sonnet 5 USD rates. Override these for your account/model.
try:
    ANTHROPIC_INPUT_COST_PER_MILLION = validate_price(
        os.environ.get("ANTHROPIC_INPUT_COST_PER_MILLION", "2")
    )
    ANTHROPIC_OUTPUT_COST_PER_MILLION = validate_price(
        os.environ.get("ANTHROPIC_OUTPUT_COST_PER_MILLION", "10")
    )
except UsageValidationError:
    raise ConfigurationError(
        "Anthropic token prices must be finite, non-negative decimal USD values."
    ) from None
