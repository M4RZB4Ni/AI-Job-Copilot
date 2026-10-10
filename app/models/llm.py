from typing import Any
from pydantic import BaseModel

class ProviderResponse(BaseModel):
    output: dict[str, Any] | None
    model: str
    input_tokens: int
    output_tokens: int