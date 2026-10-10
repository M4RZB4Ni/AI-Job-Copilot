from decimal import Decimal
from typing import Any, Protocol

from app.models.llm import ProviderResponse


class LLMProvider(Protocol):
    name: str
    model: str
    input_price_per_million: Decimal | None
    output_price_per_million: Decimal | None

    async def extract_structured(
        self,
        prompt: str,
        *,
        tool_name: str,
        tool_description: str,
        schema: dict[str, Any],
    ) -> ProviderResponse: ...