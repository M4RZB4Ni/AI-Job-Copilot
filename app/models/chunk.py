from pydantic import BaseModel
from pydantic import BaseModel, Field

class DocumentChunk(BaseModel):
    source: str  # file name, e.g. "cv.md"
    section: str  # heading path, e.g. "Project: Demo > Results"
    chunk_index: int  # position within its section, 0 if the section was not split
    text: str  # section path plus content, this is what gets embedded
    estimated_tokens: int
    
class SearchResult(BaseModel):
    source: str
    section: str
    text: str
    score: float  # cosine similarity: closer to 1 means closer in meaning    
    
    
class SearchRequest(BaseModel):
    # Field(...) adds validation rules. If a request breaks them, FastAPI
    # answers with a 422 error by itself, and our code never runs.
    query: str = Field(min_length=1, max_length=500)
    # ge = "greater than or equal", le = "less than or equal": limit must be 1 to 10.
    limit: int = Field(default=3, ge=1, le=10)    