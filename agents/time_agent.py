import json
import uuid
from typing import List, Dict, Any

from services.claude_service import call_claude
from services.supabase_service import (
    fetch_applications,
    fetch_recent_decisions,
    store_decision,
)
from prompts.time_prompt import TIME_SYSTEM_PROMPT
from utils.scoring_engine import ScoringEngine
from utils.duplication_detector import DuplicationDetector

_scoring = ScoringEngine()
_detector = DuplicationDetector()

# ─── Free-text tool extraction prompt ────────────────────────────────────────

EXTRACT_TOOLS_PROMPT = """You are a data extraction agent. Extract all application / tool entries from the text below.
Return ONLY a valid JSON object with a "tools" array. Each item must include:
  name, vendor (or null), category, description (brief or null),
  annual_cost (number or null), user_count (number or null),
  criticality ("Critical"|"High"|"Medium"|"Low"|null),
  deployment ("Cloud"|"On-Prem"|"Hybrid"|null),
  integrations (number or null), age_years (number or null),
  end_of_life (true|false), compliance_required (true|false),
  business_unit (string or null)

Valid categories: Monitoring, Logging, APM, Security, ITSM, Collaboration,
CRM, ERP, BSS, OSS, Cloud, Analytics, DevOps, Network, Storage, Database, Other

Return ONLY JSON — no markdown, no explanation."""

# ─── Narrative assessment prompt ──────────────────────────────────────────────

ASSESSMENT_NARRATIVE_PROMPT = """You are an Enterprise Technology Strategy AI advisor.

Given the scored application portfolio below (pre-scored by a quantitative engine), generate a comprehensive executive-level rationalization assessment.

Return ONLY valid JSON with these exact keys:
{
  "executive_summary": "3-5 paragraph narrative: portfolio health, key findings, strategic direction",
  "portfolio_overview": {
    "total_tools": 0,
    "total_annual_cost": 0.0,
    "portfolio_health": "Healthy|At Risk|Critical",
    "health_rationale": "brief explanation"
  },
  "top_recommendations": [
    {
      "rank": 1,
      "title": "concise action title",
      "description": "detailed recommendation",
      "impact": "business/cost/risk impact",
      "effort": "Low|Medium|High",
      "priority": "Critical|High|Medium",
      "confidence": "High|Medium|Low",
      "timeline": "0-3 months|3-12 months|12-24 months"
    }
  ],
  "roadmap": {
    "short_term": ["0-3 month action 1"],
    "medium_term": ["3-12 month action 1"],
    "long_term": ["12-24 month action 1"]
  },
  "expected_outcomes": {
    "cost_savings_annual": 0.0,
    "risk_reduction": "qualitative or %",
    "tool_reduction": "from X to Y",
    "operational_simplification": "key benefits",
    "strategic_gains": "business value"
  }
}

Be specific, reference tool names, use consultant-grade language. Return ONLY JSON."""


def _normalize_tool(raw: Dict) -> Dict:
    """Ensure every tool has an id and clean fields."""
    tool = dict(raw)
    if not tool.get("id"):
        tool["id"] = str(uuid.uuid4())
    # Accept both "name" and "tool_name" / "app_name"
    if not tool.get("name"):
        tool["name"] = tool.get("tool_name") or tool.get("app_name") or "Unknown"
    # Coerce numeric fields
    for field in ("annual_cost", "age_years"):
        val = tool.get(field)
        if val is not None:
            try:
                tool[field] = float(str(val).replace(",", "").replace("$", "").strip())
            except (ValueError, TypeError):
                tool[field] = None
    for field in ("user_count", "integrations"):
        val = tool.get(field)
        if val is not None:
            try:
                tool[field] = int(float(str(val).replace(",", "").strip()))
            except (ValueError, TypeError):
                tool[field] = None
    return tool


def _score_tools(tools: List[Dict]) -> List[Dict]:
    """Run ScoringEngine over every tool and attach scores + TIME/6R classification."""
    scored = []
    for t in tools:
        tool = _normalize_tool(t)
        scores = _scoring.score_tool(tool)
        composite = _scoring.composite_score(scores)
        action_6r = _scoring.determine_6r_action(scores, tool)
        time_cls = _scoring.determine_time_classification(scores, tool)
        confidence = _scoring.confidence_level(tool)
        tool.update(
            scores=scores,
            composite_score=composite,
            rationalization_action=action_6r,
            time_classification=time_cls,
            confidence_level=confidence,
        )
        scored.append(tool)
    return scored


def _extract_tools_from_text(text: str) -> List[Dict]:
    """Ask Claude to parse free-text descriptions into structured tool records."""
    user_msg = f"Extract all applications and tools from this text:\n\n{text[:6000]}"
    result_str = call_claude(EXTRACT_TOOLS_PROMPT, user_msg)
    result_str = result_str.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        data = json.loads(result_str)
        if isinstance(data, list):
            return data
        for v in data.values():
            if isinstance(v, list):
                return v
    except (json.JSONDecodeError, AttributeError):
        pass
    return []


def _generate_narrative(scored_tools: List[Dict], duplications: List[Dict]) -> Dict:
    """Call Claude for the executive narrative and recommendations."""
    # Build a compact summary to stay within token limits
    tool_summary = [
        {
            "name": t.get("name"),
            "category": t.get("category"),
            "annual_cost": t.get("annual_cost"),
            "user_count": t.get("user_count"),
            "composite_score": t.get("composite_score"),
            "time_classification": t.get("time_classification"),
            "rationalization_action": t.get("rationalization_action"),
            "confidence_level": t.get("confidence_level"),
            "risk_score": t.get("scores", {}).get("risk_score"),
        }
        for t in scored_tools
    ]

    user_msg = (
        f"Portfolio (pre-scored):\n{json.dumps(tool_summary, indent=2)}\n\n"
        f"Duplication overlaps:\n{json.dumps(duplications[:10], indent=2)}"
    )
    result_str = call_claude(ASSESSMENT_NARRATIVE_PROMPT, user_msg)
    result_str = result_str.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        return json.loads(result_str)
    except json.JSONDecodeError:
        return {"executive_summary": result_str, "parse_error": True}


# ─── Public entry point ───────────────────────────────────────────────────────

def run_time(input_data: dict) -> dict:
    """
    Full TIME portfolio rationalization.

    Accepts:
      input_data.applications  — list of tool/app dicts (structured)
      input_data.free_text     — raw text to extract tools from
      input_data.<any fields>  — treated as a single-tool query (legacy)

    Returns scored tools, TIME/6R classifications, duplications, and
    Claude-generated executive narrative.
    """
    # 1. Fetch Supabase memory for context
    portfolio_db = fetch_applications()
    past_decisions = fetch_recent_decisions(limit=5)

    # 2. Determine source tools
    apps_in = input_data.get("applications", [])
    free_text = input_data.get("free_text", "")

    if not apps_in and free_text:
        apps_in = _extract_tools_from_text(free_text)

    # Merge DB portfolio if no tools supplied
    if not apps_in:
        apps_in = portfolio_db if portfolio_db else [input_data]

    # 3. Score every tool
    scored_tools = _score_tools(apps_in)

    # 4. Detect duplications
    duplications = _detector.detect_duplications(scored_tools)

    # 5. Ask Claude for narrative + recommendations (memory-enriched)
    enriched_prompt = (
        TIME_SYSTEM_PROMPT
        + f"\n\n### Recent Decisions (memory):\n{json.dumps(past_decisions, indent=2)}"
    )
    tool_summary = [
        {k: t.get(k) for k in (
            "name", "category", "annual_cost", "user_count",
            "composite_score", "time_classification", "rationalization_action",
            "confidence_level", "scores"
        )}
        for t in scored_tools
    ]
    user_msg = (
        f"Portfolio (pre-scored by ScoringEngine):\n{json.dumps(tool_summary, indent=2)}\n\n"
        f"Duplications found:\n{json.dumps(duplications[:10], indent=2)}"
    )
    narrative_str = call_claude(enriched_prompt, user_msg)
    narrative_str_clean = narrative_str.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
    try:
        narrative = json.loads(narrative_str_clean)
    except json.JSONDecodeError:
        narrative = {"raw_response": narrative_str}

    # 6. Build TIME summary counts
    time_counts: Dict[str, int] = {}
    for t in scored_tools:
        tc = t.get("time_classification", "TOLERATE")
        time_counts[tc] = time_counts.get(tc, 0) + 1

    result = {
        "applications": scored_tools,
        "portfolio_summary": {
            "total_apps": len(scored_tools),
            "total_annual_cost": sum(t.get("annual_cost") or 0 for t in scored_tools),
            "time_breakdown": time_counts,
            "duplications_found": len(duplications),
            "potential_savings": sum(d.get("potential_annual_savings", 0) for d in duplications),
        },
        "duplications": duplications,
        "assessment": narrative,
    }

    # 7. Store to Supabase memory
    store_decision(
        {"apps_count": len(apps_in)},
        json.dumps({
            "portfolio_summary": result["portfolio_summary"],
            "time_breakdown": time_counts,
        }),
        agent="TIME",
    )

    return result
