from fastapi import APIRouter, Request
from app.models.schemas import JobPostingRequest, JobPostingAnalysis
from app.services.llm import analyze_job_posting

router = APIRouter()

@router.post("/analyze", response_model=JobPostingAnalysis)
async def analyze(request: JobPostingRequest, http_request: Request):
    return await analyze_job_posting(
        request.text,
        provider=http_request.app.state.llm_provider,
        usage_logger=http_request.app.state.cost_logger,
    )
