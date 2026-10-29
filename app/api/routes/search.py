from fastapi import APIRouter

from app.models.chunk import SearchRequest, SearchResult
from app.services import vector_service
from app.services.embeddings import embed_query

router = APIRouter()


# This is "def", NOT "async def", on purpose. embed_query (CPU work) and the database
# call are BLOCKING: they hold the thread until they finish. FastAPI runs a plain "def"
# endpoint in a worker thread, so the server keeps answering other requests meanwhile.
# An "async def" here would freeze the whole server while the model runs.
@router.post("/search", response_model=list[SearchResult])
def search_endpoint(request: SearchRequest) -> list[SearchResult]:
    return vector_service.search(embed_query(request.query), limit=request.limit)