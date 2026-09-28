from fastapi import FastAPI

app = FastAPI(title="Ai Job Copilot Application", description="An application for assisting with job searching and applications.", version="0.0.1")

@app.get("/")
def hi_root():
    return {"status": "ok", "message": "AI Job Copilot is alive"}