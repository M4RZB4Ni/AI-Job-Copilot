from fastapi import APIRouter
from app.models.schemas import JobPostingRequest, JobPostingAnalysis
from app.services.llm import analyze_job_posting

router = APIRouter()

@router.post("/analyze", response_model=JobPostingAnalysis)
async def analyze(request: JobPostingRequest):
    return await analyze_job_posting(request.text)  