from fastapi import APIRouter, Request
from app.models.usage import UsageTotals

router = APIRouter()

@router.get("/usage", response_model=UsageTotals)
async def usage(request: Request):
    return await request.app.state.cost_logger.get_total_usage()