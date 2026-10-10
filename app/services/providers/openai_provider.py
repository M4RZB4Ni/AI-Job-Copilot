import json
from decimal import Decimal
from typing import Any

from openai import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncOpenAI,
    AuthenticationError,
    BadRequestError,
    RateLimitError,
)

from app.core.exceptions import LLMProviderError
from app.models.llm import ProviderResponse
from app.services.providers.errors import error_detail


class OpenAIProvider:
    name = "openai"

    def __init__(
        self,
        api_key: str,
        model: str,
        input_price_per_million: Decimal | None,
        output_price_per_million: Decimal | None,
    ):
        self._client = AsyncOpenAI(api_key=api_key)
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
        try:
            completion = await self._client.chat.completions.create(
                model=self.model,
                # Reasoning models spend part of this budget on hidden reasoning,
                # so 1024 could leave no room for the actual answer.
                max_completion_tokens=4096,
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": tool_name,
                            "description": tool_description,
                            "parameters": schema,
                        },
                    }
                ],
                tool_choice={"type": "function", "function": {"name": tool_name}},
                messages=[{"role": "user", "content": prompt}],
            )
        except AuthenticationError:
            raise LLMProviderError("OpenAI API key is invalid or missing.", status_code=500)
        except RateLimitError as e:
            # OpenAI also uses 429 for "out of credit", so show the real reason.
            raise LLMProviderError(f"OpenAI rate limit or quota error: {error_detail(e)}", status_code=429)
        except APITimeoutError:
            raise LLMProviderError("OpenAI API timed out, try again.", status_code=504)
        except APIConnectionError:
            raise LLMProviderError("Could not reach the OpenAI API, check your connection.", status_code=503)
        except BadRequestError as e:
            raise LLMProviderError(f"OpenAI API rejected the request: {error_detail(e)}", status_code=400)
        except APIStatusError as e:
            raise LLMProviderError(f"OpenAI API error: {error_detail(e)}", status_code=502)

        output: dict[str, Any] | None = None
        message = completion.choices[0].message if completion.choices else None
        if message is not None and message.tool_calls:
            call = message.tool_calls[0]
            if call.type == "function":
                try:
                    parsed = json.loads(call.function.arguments)
                except json.JSONDecodeError:
                    parsed = None
                if isinstance(parsed, dict):
                    output = parsed

        usage = completion.usage
        return ProviderResponse(
            output=output,
            model=completion.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
        )