from anthropic import AsyncAnthropic
from anthropic.types import ToolParam
from app.config import ANTHROPIC_API_KEY
from app.models.schemas import JobPostingAnalysis

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
    message = await client.messages.create(
        model="claude-sonnet-5",
        max_tokens=1024,
        tools=[ANALYSIS_TOOL],
        tool_choice={"type": "tool", "name": "extract_job_analysis"},
        messages=[
            {"role": "user", "content": f"Analyze this job posting:\n\n{job_text}"}
        ],
    )
    
    tool_use_block = next(
        block for block in message.content if block.type == "tool_use"
    )
    
    return JobPostingAnalysis.model_validate(tool_use_block.input)