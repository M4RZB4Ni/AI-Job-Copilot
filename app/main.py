from fastapi import FastAPI
from app.api.routes import analyze
from app.core.error_handler import register_exception_handlers

app = FastAPI(title="Ai Job Copilot Application", description="An application for assisting with job searching and applications.", version="0.0.1")

register_exception_handlers(app)
app.include_router(analyze.router)

@app.get("/")
def hi_root():
    return {"status": "ok", "message": "AI Job Copilot is alive"}