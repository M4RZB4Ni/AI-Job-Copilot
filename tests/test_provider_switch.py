import asyncio
from decimal import Decimal

from app.config import DATABASE_URL
from app.core.cost_logger import CostLogger
from app.models.llm import ProviderResponse
from app.services.llm import analyze_job_posting


class FakeProvider:
    def __init__(self, name: str, model: str):
        self.name = name
        self.model = model
        self.input_price_per_million: Decimal | None = Decimal("1")
        self.output_price_per_million: Decimal | None = Decimal("2")

    async def extract_structured(self, prompt, *, tool_name, tool_description, schema):
        return ProviderResponse(
            output={
                "role": "Test Engineer",
                "seniority": "Senior",
                "key_requirements": ["Python"],
                "red_flags": [],
            },
            model=self.model,
            input_tokens=100,
            output_tokens=50,
        )


async def main():
    async with CostLogger(DATABASE_URL) as logger:
        for provider in (FakeProvider("anthropic", "fake-claude"), FakeProvider("openai", "fake-gpt")):
            result = await analyze_job_posting(
                "Senior Python engineer wanted.", provider=provider, usage_logger=logger
            )
            print(provider.name, "->", result)
        print(await logger.get_total_usage(model="fake-claude"))
        print(await logger.get_total_usage(model="fake-gpt"))


asyncio.run(main())
