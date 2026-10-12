from pydantic import BaseModel

class DocumentChunk(BaseModel):
    source: str  # file name, e.g. "cv.md"
    section: str  # heading path, e.g. "Project: Demo > Results"
    chunk_index: int  # position within its section, 0 if the section was not split
    text: str  # section path plus content, this is what gets embedded
    estimated_tokens: int