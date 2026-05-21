import json
from services.claude_service import call_claude
from services.supabase_service import (
    fetch_applications,
    fetch_dependencies,
    fetch_integration_patterns,
    store_decision,
)
from prompts.mapping_prompt import MAPPING_SYSTEM_PROMPT

BATCH_MAPPING_PROMPT = """
You are an EA Mapping and Dependency Analysis AI Agent.

You are given a LIST of applications that have been flagged for ELIMINATION or MIGRATION.
For each application, analyze its dependency risk and migration impact across the full portfolio.

Output ONLY valid JSON with this exact structure (no markdown, no preamble):
{
  "pipeline_context": "brief summary of overall dependency complexity",
  "app_analyses": [
    {
      "app_name": "name",
      "time_classification": "ELIMINATE | MIGRATE",
      "direct_dependencies": ["dep1"],
      "indirect_dependencies": ["dep2"],
      "impact_level": "LOW | MEDIUM | HIGH | CRITICAL",
      "affected_business_processes": ["process1"],
      "coupling_score": 0-10,
      "single_points_of_failure": ["spof1"],
      "removal_risk": "what breaks if this app is removed/migrated",
      "recommended_sequence": "when in the migration sequence to act on this app",
      "migration_prerequisites": ["prerequisite1"]
    }
  ],
  "overall_impact_level": "LOW | MEDIUM | HIGH | CRITICAL",
  "recommended_migration_order": ["app1", "app2"],
  "cross_app_risks": ["risk1"],
  "quick_wins": ["app with lowest coupling that can be eliminated first"]
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
    user_message = (
        f"Analyze the dependencies and impact for the following system/change request. "
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

    # 6. Persist
    store_decision(input_data, json.dumps(result), agent="MAPPING")

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

    enriched_prompt = BATCH_MAPPING_PROMPT + f"""

### Known Dependencies (from CMDB/Supabase):
{json.dumps(dependencies, indent=2)}

### Full Application Portfolio (for context on what these apps connect to):
{json.dumps([{"name": a.get("name"), "category": a.get("category"),
              "integrations": a.get("integrations"), "criticality": a.get("criticality")}
             for a in all_apps], indent=2)}

### Known Integration Patterns:
{json.dumps(integration_patterns, indent=2)}
"""

    flagged_summary = [
        {
            "name": a.get("name"),
            "category": a.get("category"),
            "time_classification": a.get("time_classification"),
            "rationalization_action": a.get("rationalization_action"),
            "composite_score": a.get("composite_score"),
            "integrations": a.get("integrations"),
            "annual_cost": a.get("annual_cost"),
            "criticality": a.get("criticality"),
        }
        for a in flagged_apps
    ]

    user_message = (
        f"Analyze migration risk and dependencies for these {len(flagged_apps)} "
        f"ELIMINATE/MIGRATE applications. Return a batch JSON analysis:\n"
        f"{json.dumps(flagged_summary, indent=2)}"
    )

    result_str = call_claude(enriched_prompt, user_message)
    result_str_clean = result_str.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        result = json.loads(result_str_clean)
    except json.JSONDecodeError:
        result = {"raw_response": result_str, "parse_error": "Response was not valid JSON"}

    store_decision({"flagged_apps": len(flagged_apps)}, json.dumps(result), agent="MAPPING_BATCH")
    return result
