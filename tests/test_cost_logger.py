from decimal import Decimal
import unittest
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from psycopg import OperationalError

from app.core.cost_logger import CostLogger, MAX_TOKENS, calculate_cost
from app.core.exceptions import ConfigurationError, UsageLogError, UsageValidationError


class CostLoggerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.pool = MagicMock()
        self.pool.open = AsyncMock()
        self.pool.close = AsyncMock()
        self.connection = AsyncMock()
        self.pool.connection.return_value.__aenter__.return_value = self.connection
        self.cursor = AsyncMock()
        self.cursor.fetchone.return_value = {"id": 1}
        self.connection.execute.return_value = self.cursor
        with patch("app.core.cost_logger.AsyncConnectionPool", return_value=self.pool):
            self.logger = CostLogger("postgresql://localhost/test")

    async def test_sql_payload_is_bound_as_data_for_insert_and_filters(self):
        payload = "x'); DROP TABLE public.usage_log; --"
        await self.logger.log_usage(payload, payload, 10, 5, cost_usd="0.001")
        query, parameters = self.connection.execute.call_args.args
        self.assertNotIn(payload, query)
        self.assertEqual(parameters, (payload, payload, 10, 5, Decimal("0.001")))
        self.cursor.fetchone.return_value = {
            "requests": 1, "input_tokens": Decimal(10),
            "output_tokens": Decimal(5), "total_tokens": Decimal(15),
            "cost_usd": Decimal("0.001"), "unpriced_requests": 0,
        }
        totals = await self.logger.get_total_usage(endpoint=payload, model=payload)
        query, parameters = self.connection.execute.call_args.args
        self.assertNotIn(payload, query)
        self.assertEqual(parameters, (payload, payload, payload, payload))
        self.assertEqual(totals.total_tokens, 15)
        self.assertEqual(totals.cost_usd, Decimal("0.001"))

    async def test_labels_are_trimmed_and_unicode_normalized(self):
        await self.logger.log_usage(" /analyze ", " cafe\u0301 ", 0, 0)
        self.assertEqual(
            self.connection.execute.call_args.args[1],
            ("/analyze", "caf\u00e9", 0, 0, None),
        )

    async def test_invalid_values_are_rejected_before_accessing_database(self):
        invalid_records: list[dict[str, Any]] = [
            {"endpoint": " "}, {"endpoint": "x" * 256},
            {"endpoint": "/analyze\n"}, {"endpoint": "x\x00"},
            {"endpoint": "x\u202e"}, {"endpoint": 3},
            {"model": ""}, {"model": "x" * 129},
            {"input_tokens": -1}, {"input_tokens": MAX_TOKENS + 1},
            {"input_tokens": True}, {"output_tokens": 1.5},
            {"cost_usd": "NaN"}, {"cost_usd": "Infinity"},
            {"cost_usd": "-0.1"}, {"cost_usd": 0.1},
            {"cost_usd": "10000000000"}, {"cost_usd": True},
            {"cost_usd": "invalid"},
        ]
        for invalid in invalid_records:
            with self.subTest(invalid=invalid):
                record: dict[str, Any] = dict(
                    endpoint="/analyze", model="claude", input_tokens=1, output_tokens=1
                )
                record.update(invalid)
                with self.assertRaises(UsageValidationError):
                    await self.logger.log_usage(**record)
        for invalid in ("", "x\n", "x" * 256):
            with self.assertRaises(UsageValidationError):
                await self.logger.get_total_usage(endpoint=invalid)
        self.pool.connection.assert_not_called()

    async def test_missing_and_partial_costs_are_preserved(self):
        self.cursor.fetchone.return_value = {
            "requests": 2, "input_tokens": 10, "output_tokens": 5,
            "total_tokens": 15, "cost_usd": None, "unpriced_requests": 1,
        }
        totals = await self.logger.get_total_usage()
        self.assertIsNone(totals.cost_usd)
        self.assertEqual(totals.unpriced_requests, 1)

    async def test_empty_totals_are_zero(self):
        self.cursor.fetchone.return_value = {
            "requests": 0, "input_tokens": 0, "output_tokens": 0,
            "total_tokens": 0, "cost_usd": Decimal(0), "unpriced_requests": 0,
        }
        totals = await self.logger.get_total_usage()
        self.assertEqual(totals.requests, 0)
        self.assertEqual(totals.total_tokens, 0)
        self.assertEqual(totals.cost_usd, Decimal(0))

    async def test_database_write_failure_returns_none_without_raising(self):
        self.connection.execute.side_effect = OperationalError("secret-dsn")
        result = await self.logger.log_usage("/analyze", "claude", 1, 1)
        self.assertIsNone(result)
        self.assertIs(
            self.pool.connection.return_value.__aexit__.call_args.args[0],
            OperationalError,
        )

    async def test_initialization_failure_closes_pool(self):
        self.connection.execute.side_effect = OperationalError("database unavailable")
        with self.assertRaises(UsageLogError):
            await self.logger.init_db()
        self.pool.close.assert_awaited_once()

    async def test_connection_failure_closes_pool(self):
        self.pool.open.side_effect = OperationalError("database unavailable")
        with self.assertRaises(UsageLogError):
            await self.logger.init_db()
        self.pool.close.assert_awaited_once()

    async def test_existing_table_skips_ddl_for_runtime_role(self):
        self.cursor.fetchone.return_value = {"table_name": "usage_log"}
        await self.logger.init_db()
        queries = [call.args[0] for call in self.connection.execute.call_args_list]
        self.assertFalse(any("CREATE TABLE" in query for query in queries))

    async def test_missing_table_is_initialized(self):
        self.cursor.fetchone.return_value = {"table_name": None}
        await self.logger.init_db()
        queries = [call.args[0] for call in self.connection.execute.call_args_list]
        self.assertTrue(any("CREATE TABLE" in query for query in queries))

    async def test_totals_failure_uses_shared_application_exception(self):
        self.connection.execute.side_effect = OperationalError("secret-dsn")
        with self.assertRaises(UsageLogError) as caught:
            await self.logger.get_total_usage()
        self.assertEqual(caught.exception.status_code, 503)
        self.assertNotIn("secret-dsn", caught.exception.message)

    async def test_missing_rows_use_shared_errors_instead_of_type_errors(self):
        self.cursor.fetchone.return_value = None
        result = await self.logger.log_usage("/analyze", "claude", 1, 1)
        self.assertIsNone(result)
        with self.assertRaises(UsageLogError):
            await self.logger.get_total_usage()
        with self.assertRaises(UsageLogError):
            await self.logger.init_db()

    def test_missing_database_configuration_uses_shared_exception(self):
        with self.assertRaises(ConfigurationError):
            CostLogger("")


class CostCalculationTests(unittest.TestCase):
    def test_exact_cost_and_small_requests(self):
        self.assertEqual(calculate_cost(1000, 100, Decimal(2), Decimal(10)), Decimal("0.003"))
        self.assertEqual(calculate_cost(1, 1, Decimal(2), Decimal(10)), Decimal("0.000012"))
        self.assertEqual(calculate_cost(0, 0, Decimal(2), Decimal(10)), Decimal(0))
        self.assertEqual(calculate_cost(1000, 100, Decimal(0), Decimal(0)), Decimal(0))

    def test_invalid_rates_and_token_counts(self):
        invalid_rates: list[Any] = [Decimal("NaN"), Decimal("Infinity"), Decimal(-1), 0.1, True]
        for rate in invalid_rates:
            with self.subTest(rate=rate), self.assertRaises(UsageValidationError):
                calculate_cost(1, 1, rate, Decimal(10))
        invalid_tokens: list[Any] = [-1, True, 1.5, MAX_TOKENS + 1]
        for tokens in invalid_tokens:
            with self.subTest(tokens=tokens), self.assertRaises(UsageValidationError):
                calculate_cost(tokens, 1, Decimal(2), Decimal(10))


if __name__ == "__main__":
    unittest.main()
