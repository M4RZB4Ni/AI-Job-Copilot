"""Asynchronous PostgreSQL storage for LLM usage and USD costs."""

from app.models.usage import UsageTotals
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP, localcontext
from types import TracebackType
import unicodedata

from psycopg import AsyncConnection
from psycopg.rows import DictRow, dict_row
from psycopg_pool import AsyncConnectionPool

from app.core.error_handler import handle_usage_errors
from app.core.exceptions import ConfigurationError, UsageLogError, UsageValidationError


MAX_TOKENS = 2**63 - 1
COST_PRECISION = Decimal("0.0000000001")
MAX_COST = Decimal("9999999999.9999999999")


def _clean_label(value: object, name: str, max_length: int) -> str:
    if not isinstance(value, str):
        raise UsageValidationError(f"{name} must be a string.")
    # Reject control characters before stripping so embedded/newline log data
    # cannot be silently accepted. Quotes remain valid data, bound by Psycopg.
    if any(unicodedata.category(char).startswith("C") for char in value):
        raise UsageValidationError(f"{name} must not contain control characters.")
    value = unicodedata.normalize("NFC", value).strip()
    if not value or len(value) > max_length:
        raise UsageValidationError(f"{name} must contain 1 to {max_length} characters.")
    return value


def _validate_tokens(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise UsageValidationError(f"{name} must be an integer.")
    if not 0 <= value <= MAX_TOKENS:
        raise UsageValidationError(f"{name} must be a non-negative PostgreSQL BIGINT.")
    return value


def validate_price(value: object) -> Decimal:
    """Validate an exact USD value; floats and non-finite values are rejected."""
    if isinstance(value, bool) or not isinstance(value, (Decimal, str, int)):
        raise UsageValidationError("Prices must be Decimal, string, or integer values.")
    try:
        price = Decimal(value)
    except InvalidOperation:
        raise UsageValidationError("Prices must be valid decimal values.") from None
    if not price.is_finite() or not 0 <= price <= MAX_COST:
        raise UsageValidationError("Prices must be finite, non-negative, and within range.")
    return price


def _round_cost(value: Decimal | str | int) -> Decimal:
    with localcontext() as context:
        context.prec = 60
        rounded = validate_price(value).quantize(
            COST_PRECISION, rounding=ROUND_HALF_UP
        )
    # Rounding must not carry a value past the NUMERIC(20, 10) limit.
    return validate_price(rounded)


def calculate_cost(
    input_tokens: int,
    output_tokens: int,
    input_price_per_million: Decimal,
    output_price_per_million: Decimal,
) -> Decimal:
    """Calculate standard (uncached) token costs using exact decimal rates."""
    _validate_tokens(input_tokens, "input_tokens")
    _validate_tokens(output_tokens, "output_tokens")
    input_price = validate_price(input_price_per_million)
    output_price = validate_price(output_price_per_million)
    with localcontext() as context:
        context.prec = 60
        cost = (
            input_tokens * input_price + output_tokens * output_price
        ) / Decimal(1_000_000)
        return _round_cost(cost)


class CostLogger:
    """One connection pool per application, opened and closed in its lifespan.

    init_db creates the usage table in an existing database, not the database
    itself. The shared error handler translates storage errors. Usage writes
    are best effort; startup and totals raise AppError subclasses. Pool contexts
    commit on success and roll back on failure.
    """

    def __init__(self, database_url: object):
        if not isinstance(database_url, str) or not database_url.strip():
            raise ConfigurationError("DATABASE_URL must be configured.")
        self._pool = AsyncConnectionPool(
            conninfo=database_url,
            connection_class=AsyncConnection[DictRow],
            min_size=1,
            max_size=5,
            timeout=5,
            max_waiting=20,
            open=False,
            kwargs={
                "row_factory": dict_row,
                "connect_timeout": 5,
                "options": "-c statement_timeout=5000 -c lock_timeout=5000",
            },
        )

    async def init_db(self) -> None:
        """Open the pool and create usage_log if it does not already exist."""
        try:
            async with handle_usage_errors("initialize the usage database"):
                await self._pool.open(wait=True, timeout=5)
                await self._create_table()
        except BaseException:
            # Cleanup includes cancellation during startup. Re-raise the
            # translated error; consumers do not handle driver exceptions.
            await self.close()
            raise

    async def _create_table(self) -> None:
        async with self._pool.connection() as connection:
            # Serialize schema setup across workers. The transaction-scoped
            # lock is released automatically on commit or rollback.
            await connection.execute(
                "SELECT pg_advisory_xact_lock("
                "hashtextextended('job-copilot:usage-log:init', 0))"
            )
            cursor = await connection.execute(
                "SELECT to_regclass('public.usage_log') AS table_name"
            )
            existing = await cursor.fetchone()
            if existing is None:
                raise UsageLogError("Usage table lookup returned no result.")
            if existing["table_name"] is not None:
                return
            # Skip DDL when the table exists so runtime roles only need
            # schema USAGE, table INSERT/SELECT, and sequence USAGE.
            await connection.execute(
                """
                CREATE TABLE IF NOT EXISTS public.usage_log (
                    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
                    endpoint VARCHAR(255) NOT NULL
                        CHECK (length(btrim(endpoint)) > 0),
                    model VARCHAR(128) NOT NULL
                        CHECK (length(btrim(model)) > 0),
                    input_tokens BIGINT NOT NULL CHECK (input_tokens >= 0),
                    output_tokens BIGINT NOT NULL CHECK (output_tokens >= 0),
                    cost_usd NUMERIC(20, 10)
                        CHECK (cost_usd >= 0 AND cost_usd <> 'NaN'::numeric),
                    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    async def close(self) -> None:
        async with handle_usage_errors("close usage storage"):
            await self._pool.close()

    async def __aenter__(self) -> "CostLogger":
        await self.init_db()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        await self.close()

    async def log_usage(
        self,
        endpoint: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        *,
        cost_usd: Decimal | str | int | None = None,
    ) -> int | None:
        """Return the inserted ID, or None if usage storage fails."""
        endpoint = _clean_label(endpoint, "endpoint", 255)
        model = _clean_label(model, "model", 128)
        input_tokens = _validate_tokens(input_tokens, "input_tokens")
        output_tokens = _validate_tokens(output_tokens, "output_tokens")
        if cost_usd is not None:
            cost_usd = _round_cost(cost_usd)
        async with handle_usage_errors("record LLM usage", suppress=True):
            return await self._insert_usage(
                endpoint, model, input_tokens, output_tokens, cost_usd
            )
        return None

    async def _insert_usage(
        self,
        endpoint: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        cost_usd: Decimal | None,
    ) -> int:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                """
                INSERT INTO public.usage_log
                    (endpoint, model, input_tokens, output_tokens, cost_usd)
                VALUES (%s, %s, %s, %s, %s)
                RETURNING id
                """,
                (endpoint, model, input_tokens, output_tokens, cost_usd),
            )
            row = await cursor.fetchone()
            if row is None:
                raise UsageLogError("Usage insert returned no ID.")
            return row["id"]

    async def get_total_usage(
        self, *, endpoint: str | None = None, model: str | None = None
    ) -> UsageTotals:
        """Get global totals or exact endpoint/model totals, including costs.

        Empty results return zero. If any matching cost is NULL, cost_usd is
        None and unpriced_requests identifies the incomplete cost accounting.
        """
        if endpoint is not None:
            endpoint = _clean_label(endpoint, "endpoint", 255)
        if model is not None:
            model = _clean_label(model, "model", 128)
        async with handle_usage_errors("read usage totals"):
            return await self._read_totals(endpoint, model)
        # The error handler always raises when suppress=False.
        raise UsageLogError("Usage totals are unavailable.")

    async def _read_totals(
        self, endpoint: str | None, model: str | None
    ) -> UsageTotals:
        async with self._pool.connection() as connection:
            cursor = await connection.execute(
                """
                SELECT COUNT(*) AS requests,
                       COALESCE(SUM(input_tokens), 0) AS input_tokens,
                       COALESCE(SUM(output_tokens), 0) AS output_tokens,
                       COALESCE(SUM(input_tokens::numeric + output_tokens), 0)
                           AS total_tokens,
                       CASE WHEN COUNT(*) FILTER (WHERE cost_usd IS NULL) > 0
                            THEN NULL ELSE COALESCE(SUM(cost_usd), 0)
                       END AS cost_usd,
                       COUNT(*) FILTER (WHERE cost_usd IS NULL)
                           AS unpriced_requests
                FROM public.usage_log
                WHERE (%s::text IS NULL OR endpoint = %s)
                  AND (%s::text IS NULL OR model = %s)
                """,
                (endpoint, endpoint, model, model),
            )
            row = await cursor.fetchone()
            if row is None:
                raise UsageLogError("Usage totals query returned no result.")
        return UsageTotals(
            requests=row["requests"],
            input_tokens=int(row["input_tokens"]),
            output_tokens=int(row["output_tokens"]),
            total_tokens=int(row["total_tokens"]),
            cost_usd=row["cost_usd"],
            unpriced_requests=row["unpriced_requests"],
        )
