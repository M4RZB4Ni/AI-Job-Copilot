import unittest

from fastapi import FastAPI
from httpx2 import ASGITransport, AsyncClient

from app.core.error_handler import register_exception_handlers
from app.core.exceptions import JobAnalysisError, UsageLogError, UsageValidationError


class ErrorHandlerTests(unittest.IsolatedAsyncioTestCase):
    async def test_usage_errors_use_existing_app_error_http_handler(self):
        errors = [
            UsageLogError("Usage storage is unavailable."),
            UsageValidationError("input_tokens must be an integer."),
            JobAnalysisError("Job text cannot be empty.", status_code=400),
        ]
        for error in errors:
            with self.subTest(error=error):
                app = FastAPI()
                register_exception_handlers(app)

                @app.get("/test-error")
                async def fail():
                    raise error

                async with AsyncClient(
                    transport=ASGITransport(app=app), base_url="http://test"
                ) as client:
                    response = await client.get("/test-error")
                self.assertEqual(response.status_code, error.status_code)
                self.assertEqual(response.json(), {"detail": error.message})
