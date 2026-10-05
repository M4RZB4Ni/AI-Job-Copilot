from decimal import Decimal
import os
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import FastAPI
from httpx2 import Request as HTTPRequest
from psycopg import OperationalError
from psycopg_pool import PoolTimeout

# No provider calls or real credentials are needed for these tests.
with patch.dict(os.environ, {"ANTHROPIC_API_KEY": "test-key"}):
    from app.services import llm
    from app import main

from app.core.cost_logger import CostLogger
from app.core.exceptions import JobAnalysisError, UsageLogError


class AnalysisUsageTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.usage_logger = AsyncMock()
        self.response = SimpleNamespace(
            model="claude-sonnet-5",
            usage=SimpleNamespace(input_tokens=1000, output_tokens=100),
            content=[SimpleNamespace(type="tool_use", input={
                "role": "Engineer", "seniority": "Senior",
                "key_requirements": ["Python"], "red_flags": [],
            })],
        )
        self.create = AsyncMock(return_value=self.response)
        self.patches = [
            patch.object(llm.client.messages, "create", self.create),
            patch.object(llm, "ANTHROPIC_INPUT_COST_PER_MILLION", Decimal(2)),
            patch.object(llm, "ANTHROPIC_OUTPUT_COST_PER_MILLION", Decimal(10)),
        ]
        for mock_patch in self.patches:
            mock_patch.start()
            self.addCleanup(mock_patch.stop)

    async def test_success_logs_provider_model_tokens_and_cost(self):
        result = await llm.analyze_job_posting("Engineer posting", usage_logger=self.usage_logger)
        self.assertEqual(result.role, "Engineer")
        self.usage_logger.log_usage.assert_awaited_once_with(
            endpoint="/analyze", model="claude-sonnet-5",
            input_tokens=1000, output_tokens=100, cost_usd=Decimal("0.003"),
        )

    async def test_billable_response_is_logged_before_parse_failure(self):
        self.response.content = []
        with self.assertRaises(JobAnalysisError):
            await llm.analyze_job_posting("Engineer posting", usage_logger=self.usage_logger)
        self.usage_logger.log_usage.assert_awaited_once()

    async def test_database_failure_preserves_analysis(self):
        for failure in (OperationalError("secret-dsn"), PoolTimeout("secret-dsn")):
            with self.subTest(failure=failure):
                pool = MagicMock()
                connection = AsyncMock()
                connection.execute.side_effect = failure
                pool.connection.return_value.__aenter__.return_value = connection
                with patch("app.core.cost_logger.AsyncConnectionPool", return_value=pool):
                    usage_logger = CostLogger("postgresql://localhost/test")
                result = await llm.analyze_job_posting("Engineer posting", usage_logger=usage_logger)
                self.assertEqual(result.role, "Engineer")

    async def test_empty_input_does_not_call_provider_or_log_usage(self):
        with self.assertRaises(JobAnalysisError):
            await llm.analyze_job_posting(" ", usage_logger=self.usage_logger)
        self.create.assert_not_awaited()
        self.usage_logger.log_usage.assert_not_awaited()

    async def test_provider_connection_failure_is_not_logged_as_usage(self):
        self.create.side_effect = llm.APIConnectionError(
            request=HTTPRequest("POST", "https://example.test/messages")
        )
        with self.assertRaises(JobAnalysisError):
            await llm.analyze_job_posting("Engineer posting", usage_logger=self.usage_logger)
        self.usage_logger.log_usage.assert_not_awaited()


class ApplicationLifespanTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.pool = MagicMock()
        self.pool.open = AsyncMock()
        self.pool.close = AsyncMock()
        connection = AsyncMock()
        cursor = AsyncMock()
        cursor.fetchone.return_value = {"table_name": "usage_log"}
        connection.execute.return_value = cursor
        self.pool.connection.return_value.__aenter__.return_value = connection
        with patch("app.core.cost_logger.AsyncConnectionPool", return_value=self.pool):
            self.usage_logger = CostLogger("postgresql://localhost/test")

    async def test_startup_initializes_and_shutdown_closes_logger(self):
        application = FastAPI()
        with patch.object(main, "CostLogger", return_value=self.usage_logger):
            async with main.lifespan(application):
                self.pool.open.assert_awaited_once()
                self.assertIs(application.state.cost_logger, self.usage_logger)
                self.pool.close.assert_not_awaited()
        self.pool.close.assert_awaited_once()

    async def test_initialization_error_prevents_startup_and_closes_logger(self):
        self.pool.open.side_effect = OperationalError("unavailable")
        application = FastAPI()
        with patch.object(main, "CostLogger", return_value=self.usage_logger):
            with self.assertRaises(UsageLogError):
                async with main.lifespan(application):
                    self.fail("Application must not start without usage storage")
        self.pool.close.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
