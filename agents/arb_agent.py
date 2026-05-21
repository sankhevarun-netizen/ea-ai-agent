import json
from services.claude_service import call_claude
from services.supabase_service import (
    fetch_recent_decisions,
    fetch_standards_rules,
    fetch_applications,
    store_decision,
)
from prompts.arb_prompt import ARB_SYSTEM_PROMPT


def run_arb(input_data: dict) -> dict:
    """
    Architecture Review Board agent.
    Evaluates architecture proposals against enterprise standards.
    """
    # 1. Fetch memory from Supabase
    past_decisions = fetch_recent_decisions(limit=5)
    standards = fetch_standards_rules()
    portfolio = fetch_applications()

    # 2. Enrich system prompt with memory
    enriched_prompt = ARB_SYSTEM_PROMPT + f"""

### Historical Architecture Decisions (learn from these):
{json.dumps(past_decisions, indent=2)}

### Enterprise Standards & Rules:
{json.dumps(standards, indent=2)}

### Current Application Portfolio (check for redundancy):
{json.dumps(portfolio, indent=2)}
"""

    # 3. Build user message
    user_message = (
        f"Evaluate this architecture proposal and return a JSON decision:\n"
        f"{json.dumps(input_data, indent=2)}"
    )

    # 4. Call Claude
    result_str = call_claude(enriched_prompt, user_message)

    # 5. Parse JSON — strip any accidental markdown fences
    result_str_clean = result_str.strip()
    if result_str_clean.startswith("```"):
        result_str_clean = result_str_clean.split("```")[-2] if "```" in result_str_clean else result_str_clean
        result_str_clean = result_str_clean.lstrip("json").strip()

    try:
        result = json.loads(result_str_clean)
    except json.JSONDecodeError:
        result = {"raw_response": result_str, "parse_error": "Response was not valid JSON"}

    # 6. Store decision to Supabase memory
    store_decision(input_data, json.dumps(result), agent="ARB")

    return result
