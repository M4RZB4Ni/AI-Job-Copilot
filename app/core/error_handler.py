from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from psycopg import Error as DatabaseError
from psycopg_pool import PoolClosed, PoolTimeout, TooManyRequests

from app.core.exceptions import AppError, UsageLogError


@asynccontextmanager
async def handle_usage_errors(
    operation: str, *, suppress: bool = False
) -> AsyncGenerator[None, None]:
    """Translate storage failures without exposing SQL, values, or credentials.

    Logging usage is best effort; initialization and reading totals must fail
    explicitly. Callers use CostLogger without handling driver exceptions.
    """
    try:
        yield
    except (DatabaseError, PoolClosed, PoolTimeout, TooManyRequests, UsageLogError):
        error = UsageLogError(f"Unable to {operation}: usage storage is unavailable.")
        if not suppress:
            raise error from None

def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.message},
        )
