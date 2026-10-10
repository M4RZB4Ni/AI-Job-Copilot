from app.core.cost_logger import CostLogger, calculate_cost
from app.core.exceptions import JobAnalysisError
from app.models.schemas import JobPostingAnalysis
from app.services.providers.base import LLMProvider

ANALYSIS_TOOL_NAME = "extract_job_analysis"
ANALYSIS_TOOL_DESCRIPTION = "Extract structured information from a job posting."
ANALYSIS_SCHEMA = {
    "type": "object",
    "properties": {
        "role": {"type": "string", "description": "The job title or role"},
        "seniority": {"type": "string", "description": "Seniority level, e.g. Junior, Mid, Senior, Staff"},
        "key_requirements": {
            "type": "array",
            "items": {"type": "string"},
            "description": "The most important requirements listed in the posting",
        },
        "red_flags": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Concerning signals in the posting, e.g. vague pay, unrealistic scope. Empty list if none.",
        },
    },
    "required": ["role", "seniority", "key_requirements", "red_flags"],
}


async def analyze_job_posting(
    job_text: str, *, provider: LLMProvider, usage_logger: CostLogger
) -> JobPostingAnalysis:
    if not job_text or not job_text.strip():
        raise JobAnalysisError("Job posting text cannot be empty.", status_code=400)

    if len(job_text) > 50_000:
        raise JobAnalysisError("Job posting text exceeds maximum length of 50,000 characters.", status_code=400)

    response = await provider.extract_structured(
        f"Analyze this job posting:\n\n{job_text}",
        tool_name=ANALYSIS_TOOL_NAME,
        tool_description=ANALYSIS_TOOL_DESCRIPTION,
        schema=ANALYSIS_SCHEMA,
    )

    cost = None
    if (
        provider.input_price_per_million is not None
        and provider.output_price_per_million is not None
    ):
        cost = calculate_cost(
            response.input_tokens,
            response.output_tokens,
            provider.input_price_per_million,
            provider.output_price_per_million,
        )

    # The response is billable even if parsing/validation later fails.
    await usage_logger.log_usage(
        endpoint="/analyze",
        model=response.model,
        input_tokens=response.input_tokens,
        output_tokens=response.output_tokens,
        cost_usd=cost,
    )

    if response.output is None:
        raise JobAnalysisError("The model did not return structured data.", status_code=502)

    return JobPostingAnalysis.model_validate(response.output)