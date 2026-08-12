import json
import math
import re as _re

from services.claude_service import call_claude
from services.supabase_service import fetch_applications, store_decision
from prompts.compliance_prompt import COMPLIANCE_SYSTEM_PROMPT
from prompts.industry_context import get_industry_context


def _json_default(obj):
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    try:
        return obj.item()
    except AttributeError:
        pass
    return str(obj)


def run_compliance(input_data: dict) -> dict:
    """
    Compliance Mapping agent.
    Maps each application against user-selected regulations, flags gaps,
    and returns a per-app compliance assessment with overall score.
    """
    regulations  = input_data.get("regulations", [])
    applications = input_data.get("applications", [])
    industry     = input_data.get("industry", "")
    sub_sector   = input_data.get("sub_sector", "")
    mapping_output = input_data.get("mapping_output", {})
    governance   = input_data.get("governance", "")
    additional_ctx = input_data.get("additional_context", "")

    if not regulations:
        return {
            "skipped": True,
            "reason": "No regulations selected — compliance check was skipped.",
        }

    # Fetch portfolio for any apps not passed directly
    portfolio = fetch_applications()

    # Build enriched prompt
    enriched_prompt = COMPLIANCE_SYSTEM_PROMPT

    context_lines = []
    if governance:
        context_lines.append(f"Governance structure: {governance}")
    if additional_ctx:
        context_lines.append(f"Additional context: {additional_ctx}")
    if context_lines:
        enriched_prompt += "\n### Client Context:\n" + "\n".join(context_lines) + "\n"

    # Include mapping risk signals to help infer data sensitivity
    if mapping_output and not mapping_output.get("skipped"):
        app_risks = {
            a.get("app_name", ""): {
                "impact_level": a.get("impact_level"),
                "coupling_score": a.get("coupling_score"),
                "single_points_of_failure": a.get("single_points_of_failure", []),
            }
            for a in mapping_output.get("app_analyses", [])
        }
        if app_risks:
            enriched_prompt += f"\n### Mapping Risk Signals (use for data sensitivity inference):\n{json.dumps(app_risks, indent=2)}\n"

    if industry:
        enriched_prompt += get_industry_context(industry, sub_sector)

    # Summarise portfolio for Claude — include fields most useful for compliance inference
    app_summary = [
        {
            "name":                   a.get("name"),
            "category":               a.get("category"),
            "criticality":            a.get("criticality"),
            "deployment":             a.get("deployment"),
            "vendor":                 a.get("vendor"),
            "annual_cost":            a.get("annual_cost"),
            "user_count":             a.get("user_count"),
            "compliance_required":    a.get("compliance_required"),
            "rationalization_action": a.get("rationalization_action"),
            "time_classification":    a.get("time_classification"),
            "end_of_life":            a.get("end_of_life"),
            "integrations":           a.get("integrations"),
        }
        for a in applications
    ]

    user_message = (
        f"Assess the following {len(applications)}-app portfolio against these regulations: "
        f"{', '.join(regulations)}.\n\n"
        f"Return a comprehensive compliance gap analysis JSON:\n"
        f"{json.dumps(app_summary, indent=2, default=_json_default)}"
    )

    result_str = call_claude(enriched_prompt, user_message, max_tokens=8192)

    # Parse — strip markdown fences robustly
    result_str_clean = result_str.strip()
    if result_str_clean.startswith("```"):
        lines = result_str_clean.split("\n")
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        result_str_clean = "\n".join(lines).strip()

    try:
        result = json.loads(result_str_clean)
    except json.JSONDecodeError:
        m = _re.search(r'\{[\s\S]*\}', result_str_clean)
        if m:
            try:
                result = json.loads(m.group())
            except Exception:
                result = {"raw_response": result_str, "parse_error": "Response was not valid JSON"}
        else:
            result = {"raw_response": result_str, "parse_error": "Response was not valid JSON"}

    store_decision(
        {"regulations": regulations, "app_count": len(applications)},
        json.dumps(result, default=_json_default),
        agent="COMPLIANCE",
    )

    return result
