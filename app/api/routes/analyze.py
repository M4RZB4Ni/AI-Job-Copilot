from fastapi import APIRouter
from app.models.schemas import JobPostingRequest, JobPostingResponse

router = APIRouter()

@router.post("/analyze", response_model=JobPostingResponse)
async def analyze_job_posting(request: JobPostingRequest):
    return JobPostingResponse(text=request.text)