import json
from services.claude_service import call_claude
from services.supabase_service import (
    fetch_maturity_scores,
    fetch_applications,
    fetch_standards_rules,
    store_decision,
)
from prompts.maturity_prompt import MATURITY_SYSTEM_PROMPT


def run_maturity(input_data: dict) -> dict:
    """
    EA Maturity Assessment agent.
    Scores the organisation across 6 EA dimensions and generates a roadmap.
    """
    # 1. Fetch memory
    historical_scores = fetch_maturity_scores()
    portfolio = fetch_applications()
    standards = fetch_standards_rules()

    # 2. Enrich prompt
    enriched_prompt = MATURITY_SYSTEM_PROMPT + f"""

### Historical Maturity Scores (trend reference):
{json.dumps(historical_scores, indent=2)}

### Application Portfolio (portfolio breadth indicator):
{json.dumps(portfolio, indent=2)}

### Existing Standards & Governance Rules (maturity indicator):
{json.dumps(standards, indent=2)}
"""

    # 3. User message
    user_message = (
        f"Conduct a full EA maturity assessment for the following organisation context "
        f"and return a structured JSON result:\n{json.dumps(input_data, indent=2)}"
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
    store_decision(input_data, json.dumps(result), agent="MATURITY")

    return result
