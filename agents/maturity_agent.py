import json
from services.claude_service import call_claude
from services.supabase_service import (
    fetch_maturity_scores,
    fetch_applications,
    fetch_standards_rules,
    store_decision,
)
from prompts.maturity_prompt import MATURITY_SYSTEM_PROMPT
from prompts.industry_context import get_industry_context


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

    # Inject industry context
    industry = input_data.get("industry", "")
    sub_sector = input_data.get("sub_sector", "")
    if industry:
        enriched_prompt += get_industry_context(industry, sub_sector)

    # 2b. Inject structured assessment questionnaire results when available
    assessment_results = input_data.get("assessment_results") or {}
    if assessment_results and assessment_results.get("dimensions"):
        dims = assessment_results.get("dimensions", [])
        overall = assessment_results.get("overall_score")
        band = assessment_results.get("overall_band")
        respondents = assessment_results.get("respondent_count", 0)
        names = assessment_results.get("respondent_names", [])
        dim_lines = "\n".join(
            f"  - {d['label']}: score={d['score']}, band={d['band']}"
            for d in dims
        )
        enriched_prompt += f"""

### Human Assessment Results (PRIMARY EVIDENCE — 30-question structured questionnaire):
These scores come from {respondents} respondent(s) ({', '.join(names)}) who completed the
30-question EA Maturity Assessment covering 8 dimensions across 4 pillars (Vision, People,
Process, Technology). Use these as the PRIMARY basis for your scoring. Your 8
dimensions should be mapped to and anchored by these evidence-based scores.

Overall Score: {overall}/5 ({band})
Dimension Scores:
{dim_lines}

Pillar mapping guide (questionnaire dimension → framework dimension key):
  - vision_strategy       → vision_and_strategy        (Pillar: Vision & Strategy)
  - organization          → organization               (Pillar: People)
  - leadership_governance → leadership_and_governance  (Pillar: People)
  - behavior_culture      → behaviour_and_culture      (Pillar: People)
  - metrics_analysis      → metrics_and_analysis       (Pillar: Processes)
  - policy_standards      → policy_and_standards       (Pillar: Processes)
  - enabling_processes    → enabling_processes          (Pillar: Processes)
  - tools_technology      → tools_and_technology       (Pillar: Technology)

When generating gaps and improvements per dimension, reference the specific question areas
that scored low from the assessment data above.
"""
    else:
        enriched_prompt += "\n### Note: No structured questionnaire results provided. Assessment based on portfolio signals and context only. Accuracy is lower — recommend running the 30-question assessment for evidence-based scoring.\n"

    # 2c. Inject client-provided context
    ctx_fields = []
    for key, label in [
        ("governance",        "Governance structure"),
        ("ea_framework",      "EA framework in use"),
        ("ea_tools",          "EA tooling"),
        ("cloud_strategy",    "Cloud strategy"),
        ("cmdb_tool",         "CMDB / ITSM tool"),
        ("known_integrations","Known integration patterns"),
        ("additional_context","Additional context"),
        ("mapping_complexity","Dependency complexity (from MAPPING stage)"),
    ]:
        val = input_data.get(key, "")
        if val:
            ctx_fields.append(f"{label}: {val}")
    if ctx_fields:
        enriched_prompt += "\n### Client-Provided Organisational Context:\n" + "\n".join(ctx_fields) + "\n"

    # 3. User message
    has_assessment = bool(assessment_results and assessment_results.get("dimensions"))
    user_message = (
        f"Conduct a full 8-dimension EA maturity assessment. "
        f"{'Use the structured questionnaire results above as PRIMARY evidence for scoring.' if has_assessment else 'No questionnaire data available — base on portfolio signals only.'} "
        f"Return a structured JSON result:\n{json.dumps(input_data, indent=2)}"
    )

    # 4. Call Claude
    result_str = call_claude(enriched_prompt, user_message)

    # 5. Parse
    result_str_clean = result_str.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        result = json.loads(result_str_clean)
    except json.JSONDecodeError:
        result = {"raw_response": result_str, "parse_error": "Response was not valid JSON"}

    # 5b. Anchor dimension scores directly to questionnaire evidence (best-effort).
    # Claude generates textual findings; questionnaire scores are authoritative for numbers.
    try:
        if has_assessment and assessment_results.get("dimensions") and isinstance(result.get("dimensions"), dict):
            key_map = {
                "vision_strategy":       "vision_and_strategy",
                "organization":          "organization",
                "leadership_governance": "leadership_and_governance",
                "behavior_culture":      "behaviour_and_culture",
                "metrics_analysis":      "metrics_and_analysis",
                "policy_standards":      "policy_and_standards",
                "enabling_processes":    "enabling_processes",
                "tools_technology":      "tools_and_technology",
            }
            for dim in assessment_results["dimensions"]:
                dim_key = dim.get("id") or dim.get("key", "")  # stepper sends "key", inline sends "id"
                fw_key = key_map.get(dim_key, "")
                if not fw_key or fw_key not in result["dimensions"]:
                    continue
                if not isinstance(result["dimensions"][fw_key], dict):
                    result["dimensions"][fw_key] = {"positive_findings": [], "improvement_areas": []}
                if dim.get("score") is not None:
                    result["dimensions"][fw_key]["score"] = round(float(dim["score"]), 2)
                    result["dimensions"][fw_key]["band"] = dim.get("band", "Low")

            # Recalculate overall score from anchored dimension scores
            dim_scores = [
                v["score"] for v in result["dimensions"].values()
                if isinstance(v, dict) and v.get("score") is not None
            ]
            if dim_scores:
                overall = round(sum(dim_scores) / len(dim_scores), 2)
                result["overall_maturity_score"] = overall
                result["overall_band"] = "High" if overall > 3.5 else "Medium" if overall > 2 else "Low"

            # Recalculate pillar scores
            pillar_dim_map = {
                "Vision & Strategy": ["vision_and_strategy"],
                "People":            ["organization", "leadership_and_governance", "behaviour_and_culture"],
                "Processes":         ["metrics_and_analysis", "policy_and_standards", "enabling_processes"],
                "Technology":        ["tools_and_technology"],
            }
            if not isinstance(result.get("pillar_scores"), dict):
                result["pillar_scores"] = {}
            for pillar, keys in pillar_dim_map.items():
                pscores = [
                    result["dimensions"][k]["score"] for k in keys
                    if k in result["dimensions"] and isinstance(result["dimensions"][k], dict)
                    and result["dimensions"][k].get("score") is not None
                ]
                if pscores:
                    result["pillar_scores"][pillar] = round(sum(pscores) / len(pscores), 2)
    except Exception:
        pass  # anchoring is best-effort; keep Claude's original output if anything goes wrong

    # 6. Persist
    store_decision(input_data, json.dumps(result), agent="MATURITY")

    return result
