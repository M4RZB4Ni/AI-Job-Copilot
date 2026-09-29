from pydantic import BaseModel

class JobPostingRequest(BaseModel) : text: str

class JobPostingAnalysis(BaseModel): 
    role: str
    seniority: str
    key_requirements: list[str]
    red_flags: list[str]