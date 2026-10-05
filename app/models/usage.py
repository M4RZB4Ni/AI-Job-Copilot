from pydantic import BaseModel
from decimal import Decimal


class UsageTotals(BaseModel):
    requests: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    # None means at least one request has an unknown price.
    cost_usd: Decimal | None
    unpriced_requests: int