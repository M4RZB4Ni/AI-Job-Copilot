"""Run against a dedicated PostgreSQL DB by setting TEST_DATABASE_URL.

Only this test's uniquely tagged rows are deleted; no tables are dropped.
"""

from decimal import Decimal
import os
import unittest
from uuid import uuid4

from psycopg import errors

from app.core.cost_logger import CostLogger, MAX_TOKENS


@unittest.skipUnless(os.environ.get("TEST_DATABASE_URL"), "TEST_DATABASE_URL is not set")
class PostgreSQLUsageTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.logger = CostLogger(os.environ["TEST_DATABASE_URL"])
        await self.logger.init_db()
        self.endpoint = f"/test/{uuid4().hex}'; DROP TABLE public.usage_log; --"
        self.addAsyncCleanup(self.cleanup)

    async def cleanup(self):
        try:
            async with self.logger._pool.connection() as connection:
                await connection.execute(
                    "DELETE FROM public.usage_log WHERE endpoint = %s", (self.endpoint,)
                )
        finally:
            await self.logger.close()

    async def test_round_trip_injection_filtering_and_unknown_costs(self):
        totals = await self.logger.get_total_usage(endpoint=self.endpoint)
        self.assertEqual(totals.requests, 0)
        self.assertEqual(totals.cost_usd, Decimal(0))
        await self.logger.log_usage(self.endpoint, "model-a", 1000, 100, cost_usd="0.003")
        await self.logger.log_usage(self.endpoint, "model-b", 10, 2)
        totals = await self.logger.get_total_usage(endpoint=self.endpoint)
        self.assertEqual((totals.requests, totals.total_tokens), (2, 1112))
        self.assertIsNone(totals.cost_usd)
        self.assertEqual(totals.unpriced_requests, 1)
        priced = await self.logger.get_total_usage(endpoint=self.endpoint, model="model-a")
        self.assertEqual(priced.cost_usd, Decimal("0.003"))
        self.assertEqual(priced.input_tokens, 1000)

    async def test_transaction_rollback_and_database_constraints(self):
        for invalid_cost in ("-1", "NaN"):
            with self.assertRaises(errors.CheckViolation):
                async with self.logger._pool.connection() as connection:
                    await connection.execute(
                        "INSERT INTO public.usage_log "
                        "(endpoint, model, input_tokens, output_tokens, cost_usd) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (self.endpoint, "model-a", 1, 1, Decimal(invalid_cost)),
                    )
        with self.assertRaises(errors.CheckViolation):
            async with self.logger._pool.connection() as connection:
                await connection.execute(
                    "INSERT INTO public.usage_log "
                    "(endpoint, model, input_tokens, output_tokens) VALUES (%s, %s, %s, %s)",
                    (self.endpoint, "model-a", -1, 1),
                )
        await self.logger.log_usage(self.endpoint, "model-a", MAX_TOKENS, MAX_TOKENS)
        totals = await self.logger.get_total_usage(endpoint=self.endpoint)
        self.assertEqual(totals.requests, 1)
        self.assertEqual(totals.total_tokens, MAX_TOKENS * 2)

    async def test_repeated_initialization_preserves_data(self):
        await self.logger.log_usage(self.endpoint, "model-a", 1, 2, cost_usd=0)
        await self.logger.init_db()
        totals = await self.logger.get_total_usage(endpoint=self.endpoint)
        self.assertEqual(totals.requests, 1)
        self.assertEqual(totals.total_tokens, 3)
