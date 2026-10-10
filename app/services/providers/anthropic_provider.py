from decimal import Decimal
from typing import Any

from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)
from anthropic.types import ToolParam

from app.core.exceptions import LLMProviderError
from app.models.llm import ProviderResponse
from app.services.providers.errors import error_detail


class AnthropicProvider:
    name = "anthropic"

    def __init__(
        self,
        api_key: str,
        model: str,
        input_price_per_million: Decimal | None,
        output_price_per_million: Decimal | None,
    ):
        self._client = AsyncAnthropic(api_key=api_key)
        self.model = model
        self.input_price_per_million = input_price_per_million
        self.output_price_per_million = output_price_per_million

    async def extract_structured(
        self,
        prompt: str,
        *,
        tool_name: str,
        tool_description: str,
        schema: dict[str, Any],
    ) -> ProviderResponse:
        tool: ToolParam = {
            "name": tool_name,
            "description": tool_description,
            "input_schema": schema,
        }
        try:
            message = await self._client.messages.create(
                model=self.model,
                max_tokens=1024,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": prompt}],
            )
        except AuthenticationError:
            raise LLMProviderError("Claude API key is invalid or missing.", status_code=500)
        except RateLimitError:
            raise LLMProviderError("Rate limit exceeded for Claude API.", status_code=429)
        except APITimeoutError:
            raise LLMProviderError("Claude API timed out, try again.", status_code=504)
        except APIConnectionError:
            raise LLMProviderError("Could not reach the Claude API, check your connection.", status_code=503)
        except BadRequestError as e:
            raise LLMProviderError(f"Claude API rejected the request: {error_detail(e)}", status_code=400)
        except APIStatusError as e:
            raise LLMProviderError(f"Claude API error: {error_detail(e)}", status_code=502)

        block = next((b for b in message.content if b.type == "tool_use"), None)
        output = block.input if block is not None and isinstance(block.input, dict) else None

        return ProviderResponse(
            output=output,
            model=message.model,
            input_tokens=message.usage.input_tokens,
            output_tokens=message.usage.output_tokens,
        )