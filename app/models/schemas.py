from pydantic import BaseModel

class JobPostingRequest(BaseModel) : text: str

class JobPostingResponse(BaseModel) : text: str