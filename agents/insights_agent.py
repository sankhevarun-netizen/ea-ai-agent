import json
import math
from services.claude_service import call_claude


def _json_default(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    try:
        return obj.item()
    except AttributeError:
        pass
    return str(obj)
from services.supabase_service import (
    fetch_recent_decisions,
    fetch_applications,
    store_decision,
)
from prompts.insights_prompt import INSIGHTS_SYSTEM_PROMPT
from prompts.industry_context import get_industry_context


def run_insights(input_data: dict) -> dict:
    """
    Executive Insights agent.
    Aggregates multi-agent outputs into CIO/CTO-level strategic intelligence.
    """
    # 1. Fetch memory
    past_decisions = fetch_recent_decisions(limit=10)
    portfolio = fetch_applications()

    # 2. Enrich prompt
    enriched_prompt = INSIGHTS_SYSTEM_PROMPT + f"""

### Recent Architecture Decisions (full context):
{json.dumps(past_decisions, indent=2)}

### Current Application Portfolio:
{json.dumps(portfolio, indent=2)}
"""

    # Inject industry context
    industry = input_data.get("industry", "")
    sub_sector = input_data.get("sub_sector", "")
    if industry:
        enriched_prompt += get_industry_context(industry, sub_sector)

    # 3. Build user message — input_data may contain outputs from other agents
    user_message = (
        f"Generate executive-level strategic insights and recommendations based on "
        f"the following EA agent outputs and data. Return a structured JSON result:\n"
        f"{json.dumps(input_data, indent=2, default=_json_default)}"
    )

    # 4. Call Claude
    result_str = call_claude(enriched_prompt, user_message)

    # 5. Parse
    result_str_clean = result_str.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        result = json.loads(result_str_clean)
    except json.JSONDecodeError:
        result = {"raw_response": result_str, "parse_error": "Response was not valid JSON"}

    # 6. Persist
    store_decision(input_data, json.dumps(result, default=_json_default), agent="INSIGHTS")

    return result
