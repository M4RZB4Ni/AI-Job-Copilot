from anthropic import (
    AsyncAnthropic,
    APIConnectionError,
    RateLimitError,
    AuthenticationError,
    BadRequestError,
    APIStatusError,
)
from anthropic import AsyncAnthropic
from anthropic.types import ToolParam
from app.config import ANTHROPIC_API_KEY
from app.models.schemas import JobPostingAnalysis
from app.core.exceptions import JobAnalysisError

client = AsyncAnthropic(api_key=ANTHROPIC_API_KEY)

ANALYSIS_TOOL: ToolParam = {
    "name": "extract_job_analysis",
    "description": "Extract structured information from a job posting.",
    "input_schema": {
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
    },
}

async def analyze_job_posting(job_text: str) -> JobPostingAnalysis:
    if not job_text or not job_text.strip():
        raise JobAnalysisError("Job posting text cannot be empty.", status_code=400)
    
    if len(job_text) > 50_000:
        raise JobAnalysisError("Job posting text exceeds maximum length of 50,000 characters.", status_code=400)
    
    try:
        message = await client.messages.create(
            model="claude-sonnet-5",
            max_tokens=1024,
            tools=[ANALYSIS_TOOL],
            tool_choice={"type": "tool", "name": "extract_job_analysis"},
            messages=[
                {"role": "user", "content": f"Analyze this job posting:\n\n{job_text}"}
            ],
        )
    except AuthenticationError:
        raise JobAnalysisError("Claude API key is invalid or missing.", status_code=500)
    except APIConnectionError:
        raise JobAnalysisError("Could not reach the Claude API, check your connection.", status_code=503)
    except RateLimitError:
        raise JobAnalysisError("Rate limit exceeded for Claude API.", status_code=429)
    except BadRequestError as e:
        raise JobAnalysisError(f"Invalid request sent to Claude API: {e.message}", status_code=400)
    except APIStatusError as e:
        raise JobAnalysisError(f"Claude API error: {e.message}", status_code=502)

    try:
        tool_use_block = next(
            block for block in message.content if block.type == "tool_use"
        )
    except StopIteration:
        raise JobAnalysisError("Claude API did not return a tool_use block.", status_code=502)
    
    return JobPostingAnalysis.model_validate(tool_use_block.input)