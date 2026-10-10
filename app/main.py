from contextlib import asynccontextmanager

from fastapi import FastAPI
from app.api.routes import analyze, usage
from app.config import DATABASE_URL
from app.core.cost_logger import CostLogger
from app.core.error_handler import register_exception_handlers
from app.services.providers.factory import build_provider


@asynccontextmanager
async def lifespan(app: FastAPI):
    provider = build_provider()
    async with CostLogger(DATABASE_URL) as usage_logger:
        app.state.cost_logger = usage_logger
        app.state.llm_provider = provider
        yield


app = FastAPI(
    title="Ai Job Copilot Application",
    description="An application for assisting with job searching and applications.",
    version="0.0.1",
    lifespan=lifespan,
)

register_exception_handlers(app)
app.include_router(analyze.router)
app.include_router(usage.router)

@app.get("/")
def hi_root():
    return {"status": "ok", "message": "AI Job Copilot is alive"}