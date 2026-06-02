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
    fetch_applications,
    fetch_dependencies,
    fetch_integration_patterns,
    store_decision,
)
from prompts.mapping_prompt import MAPPING_SYSTEM_PROMPT
from prompts.industry_context import get_industry_context

BATCH_MAPPING_PROMPT = """
You are an EA Dependency Impact Analysis AI Agent.

IMPORTANT: You MUST only use data explicitly provided in the input. Do NOT infer, assume, or
fabricate dependencies, integration links, or business process connections that are not stated
in the input data. If a field is absent or unknown, set it to null or an empty list and note
it as "Not provided" rather than guessing.

You are given a list of ELIMINATE/MIGRATE applications and any context explicitly supplied by
the client (known integrations, planned changes, CMDB details, etc.).

For each application, report ONLY on:
- Integration count (from the 'integrations' field if present — otherwise null)
- Dependencies explicitly named in the client context
- Criticality and business impact derivable from the provided fields (name, category, criticality, annual_cost)
- Migration risk based on the rationalization_action and composite_score provided

data_confidence reflects how complete the input data is:
- HIGH: integrations count + criticality + cost + deployment all present
- MEDIUM: some fields present
- LOW: only name/category/criticality available

Output ONLY valid JSON with this exact structure (no markdown, no preamble):
{
  "pipeline_context": "Summary based strictly on provided data. Note any data gaps.",
  "data_basis": "Explicitly state what data was provided vs. what was absent",
  "app_analyses": [
    {
      "app_name": "name",
      "time_classification": "ELIMINATE | MIGRATE",
      "integration_count": null,
      "known_dependencies": [],
      "impact_level": "LOW | MEDIUM | HIGH | CRITICAL",
      "affected_business_processes": [],
      "coupling_score": null,
      "single_points_of_failure": [],
      "removal_risk": "Based on provided data only — or 'Insufficient data to assess'",
      "recommended_sequence": "early | mid | late — or 'Cannot determine without dependency data'",
      "migration_prerequisites": [],
      "data_confidence": "HIGH | MEDIUM | LOW",
      "data_gaps": ["List of fields that were absent and would improve this analysis"]
    }
  ],
  "overall_impact_level": "LOW | MEDIUM | HIGH | CRITICAL",
  "recommended_migration_order": [],
  "cross_app_risks": [],
  "quick_wins": [],
  "data_limitations": "Overall statement on what data is missing and how it limits the analysis"
}

Always output valid JSON only — no prose before or after.
"""


def run_mapping(input_data: dict) -> dict:
    """
    Dependency Mapping & Impact Analysis agent.
    Identifies direct/indirect dependencies and change impact.
    """
    # 1. Fetch memory
    app_id = input_data.get("app_id") or input_data.get("target_system")
    dependencies = fetch_dependencies(app_id=str(app_id) if app_id else None)
    portfolio = fetch_applications()
    integration_patterns = fetch_integration_patterns()

    # 2. Enrich prompt
    enriched_prompt = MAPPING_SYSTEM_PROMPT + f"""

### Known Dependencies (from CMDB/Supabase):
{json.dumps(dependencies, indent=2)}

### Application Portfolio (full context):
{json.dumps(portfolio, indent=2)}

### Known Integration Patterns:
{json.dumps(integration_patterns, indent=2)}
"""

    # 3. User message
    # Inject industry context
    industry = input_data.get("industry", "")
    sub_sector = input_data.get("sub_sector", "")
    if industry:
        enriched_prompt += get_industry_context(industry, sub_sector)

    user_message = (
        f"Analyze the dependencies and impact for the following system/change request. "
        f"Return a structured JSON result:\n{json.dumps(input_data, indent=2, default=_json_default)}"
    )

    # 4. Call Claude
    result_str = call_claude(enriched_prompt, user_message, max_tokens=8192)

    # 5. Parse
    result_str_clean = result_str.strip()
    # Strip markdown fences
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
        import re as _re
        m = _re.search(r'\{[\s\S]*\}', result_str_clean)
        if m:
            try:
                result = json.loads(m.group())
            except Exception:
                result = {"raw_response": result_str, "parse_error": "Response was not valid JSON"}
        else:
            result = {"raw_response": result_str, "parse_error": "Response was not valid JSON"}

    # 6. Persist
    store_decision(input_data, json.dumps(result, default=_json_default), agent="MAPPING")

    return result


def run_mapping_batch(input_data: dict) -> dict:
    """
    Batch dependency analysis for multiple ELIMINATE/MIGRATE apps.
    Used by the full EA pipeline to assess migration risk across all flagged apps.
    """
    flagged_apps = input_data.get("applications", [])
    all_apps = input_data.get("all_apps", [])

    # Fetch memory
    dependencies = fetch_dependencies()
    integration_patterns = fetch_integration_patterns()

    # Extract all context fields
    industry              = input_data.get("industry", "")
    sub_sector            = input_data.get("sub_sector", "")
    governance            = input_data.get("governance", "")
    ea_framework          = input_data.get("ea_framework", "")
    cloud_target          = input_data.get("cloud_target", "") or input_data.get("cloud_strategy", "")
    known_integrations    = input_data.get("known_integrations", "")
    planned_changes       = input_data.get("planned_changes", "")
    data_sensitivity      = input_data.get("data_sensitivity", "")
    integration_complexity= input_data.get("integration_complexity", "")
    cmdb_tool             = input_data.get("cmdb_tool", "")
    additional_context    = input_data.get("additional_context", "") or input_data.get("context", "")

    enriched_prompt = BATCH_MAPPING_PROMPT + f"""

### Known Dependencies (from CMDB/Supabase):
{json.dumps(dependencies, indent=2)}

### Full Application Portfolio ({len(all_apps)} apps — use for dependency context):
{json.dumps([{"name": a.get("name"), "category": a.get("category"),
              "time_classification": a.get("time_classification"),
              "integrations": a.get("integrations"), "criticality": a.get("criticality"),
              "deployment": a.get("deployment"), "annual_cost": a.get("annual_cost")}
             for a in all_apps], indent=2)}

### Known Integration Patterns (system-wide):
{json.dumps(integration_patterns, indent=2)}
"""

    # Inject user-provided context
    context_block = []
    if governance:            context_block.append(f"Governance structure: {governance}")
    if ea_framework:          context_block.append(f"EA framework: {ea_framework}")
    if cloud_target:          context_block.append(f"Cloud migration target: {cloud_target}")
    if cmdb_tool:             context_block.append(f"CMDB/ITSM tool: {cmdb_tool}")
    if data_sensitivity:      context_block.append(f"Data sensitivity: {data_sensitivity}")
    if integration_complexity:context_block.append(f"Integration complexity: {integration_complexity}")
    if known_integrations:    context_block.append(f"Known integrations provided by client:\n{known_integrations}")
    if planned_changes:       context_block.append(f"Planned changes/decommissions:\n{planned_changes}")
    if additional_context:    context_block.append(f"Additional context: {additional_context}")
    if context_block:
        enriched_prompt += "\n### Client-Provided Context:\n" + "\n".join(context_block) + "\n"

    if industry:
        enriched_prompt += get_industry_context(industry, sub_sector)

    app_summary = [
        {
            "name":                   a.get("name"),
            "category":               a.get("category"),
            "time_classification":    a.get("time_classification"),
            "rationalization_action": a.get("rationalization_action"),
            "composite_score":        a.get("composite_score"),
            "integrations":           a.get("integrations"),
            "annual_cost":            a.get("annual_cost"),
            "criticality":            a.get("criticality"),
            "deployment":             a.get("deployment"),
            "end_of_life":            a.get("end_of_life"),
        }
        for a in flagged_apps
    ]

    user_message = (
        f"Analyse dependencies for these {len(flagged_apps)} applications "
        f"(from a portfolio of {len(all_apps)} total). "
        f"Return a comprehensive batch JSON dependency analysis:\n"
        f"{json.dumps(app_summary, indent=2, default=_json_default)}"
    )

    result_str = call_claude(enriched_prompt, user_message, max_tokens=8192)
    result_str_clean = result_str.strip()
    # Strip markdown fences
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
        import re as _re
        m = _re.search(r'\{[\s\S]*\}', result_str_clean)
        if m:
            try:
                result = json.loads(m.group())
            except Exception:
                result = {"raw_response": result_str, "parse_error": "Response was not valid JSON"}
        else:
            result = {"raw_response": result_str, "parse_error": "Response was not valid JSON"}

    store_decision({"flagged_apps": len(flagged_apps)}, json.dumps(result, default=_json_default), agent="MAPPING_BATCH")
    return result
