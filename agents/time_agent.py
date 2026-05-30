import json
import math
import uuid
from typing import List, Dict, Any


def _json_default(obj):
    """JSON encoder fallback: handle NaN, Inf, and numpy scalars."""
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    try:
        return obj.item()   # numpy scalar → Python native
    except AttributeError:
        pass
    return str(obj)

from services.claude_service import call_claude, call_claude_vision
from services.supabase_service import (
    fetch_applications,
    fetch_recent_decisions,
    store_decision,
)
from prompts.time_prompt import TIME_SYSTEM_PROMPT
from prompts.industry_context import get_industry_context
from utils.scoring_engine import ScoringEngine
from utils.duplication_detector import DuplicationDetector

_scoring = ScoringEngine()
_detector = DuplicationDetector()

# ─── Free-text tool extraction prompt ────────────────────────────────────────

EXTRACT_TOOLS_PROMPT = """You are an Enterprise Architecture data extraction specialist.

Extract EVERY application, tool, system, platform, or technology mentioned in the text — including:
- Business applications (CRM, ERP, ITSM, HR systems, finance tools)
- IT infrastructure tools (monitoring, logging, APM, security, network)
- Cloud services and SaaS platforms
- Legacy or on-premises systems
- Development tools and DevOps platforms
- Data and analytics platforms
- Any software, service, or technology with a recognisable name

For EACH item extract as much of the following as possible from context:
  name          — exact product/tool/system name (REQUIRED — never leave blank)
  vendor        — company that makes it (infer from known products if not stated)
  category      — one of: CRM, ERP, ITSM, Monitoring, Logging, APM, Security,
                  Collaboration, BSS, OSS, Cloud, Analytics, DevOps, Network,
                  Storage, Database, Other
  annual_cost   — annual cost in USD as a number (null if not mentioned)
  user_count    — number of users as integer (null if not mentioned)
  criticality   — "Critical", "High", "Medium", or "Low" (infer from context if possible)
  deployment    — "cloud", "on-prem", or "hybrid" (infer from context if possible)
  integrations  — number of integrations as integer (null if not mentioned)
  age_years     — age of the system in years as number (null if not mentioned)
  end_of_life   — true if described as EOL, legacy, retiring, outdated; false otherwise
  compliance_required — true if HIPAA/GDPR/SOX/PCI or regulated data is mentioned; false otherwise
  business_unit — owning department or business unit (null if not mentioned)

IMPORTANT:
- Extract EVERY named tool/application/system — do not skip any
- Use your knowledge of vendors: e.g. Salesforce → CRM, ServiceNow → ITSM, AWS → Cloud
- If a tool is mentioned multiple times, include it only once
- Do NOT invent data not present or inferable — set to null if unknown

Return ONLY a valid JSON object: {"tools": [...]}
No markdown, no explanation, no preamble."""

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
    """Ensure every tool has an id and clean fields.
    Handles many common column-name variations so uploads don't silently return 'Unknown'.
    """
    # ── Case-insensitive key lookup ──────────────────────────────────────────
    def _get(*keys):
        for k in keys:
            for rk, rv in raw.items():
                if str(rk).strip().lower() == k.lower() and rv not in (None, "", "nan", "NaN"):
                    return rv
        return None

    tool = dict(raw)
    if not tool.get("id"):
        tool["id"] = str(uuid.uuid4())

    # ── Name aliases ─────────────────────────────────────────────────────────
    if not tool.get("name") or str(tool.get("name","")).strip().lower() in ("", "nan", "unknown"):
        tool["name"] = (
            _get("name","application name","application","app name","app",
                 "tool name","tool","system name","system","software name",
                 "software","product name","product","service name","service",
                 "solution name","solution","platform name","platform") or "Unknown"
        )

    # ── Category aliases ─────────────────────────────────────────────────────
    if not tool.get("category") or str(tool.get("category","")).strip().lower() in ("","nan"):
        tool["category"] = (
            _get("category","app category","application category","tool category",
                 "type","app type","application type","tool type","system type",
                 "function","functionality","domain","module type") or "Other"
        )

    # ── Criticality aliases ──────────────────────────────────────────────────
    if not tool.get("criticality") or str(tool.get("criticality","")).strip().lower() in ("","nan"):
        tool["criticality"] = (
            _get("criticality","business criticality","priority","importance",
                 "impact","risk level","risk","tier","business tier",
                 "strategic importance","business importance") or None
        )

    # ── Vendor aliases ───────────────────────────────────────────────────────
    if not tool.get("vendor") or str(tool.get("vendor","")).strip().lower() in ("","nan"):
        tool["vendor"] = (
            _get("vendor","vendor name","supplier","manufacturer",
                 "provider","software vendor","tech vendor","publisher") or None
        )

    # ── Annual cost aliases ──────────────────────────────────────────────────
    if not tool.get("annual_cost"):
        raw_cost = _get(
            "annual_cost","annual cost","yearly cost","annual license",
            "annual licence","annual fee","cost","total cost","license cost",
            "licence cost","contract value","annual contract value","acv",
            "annual spend","yearly spend","cost per year","cost (usd)",
            "cost ($)","annual cost ($)","annual cost (usd)","budget")
        if raw_cost is not None:
            try:
                tool["annual_cost"] = float(
                    str(raw_cost).replace(",","").replace("$","")
                    .replace("£","").replace("€","").replace("k","000")
                    .replace("K","000").replace("m","000000").strip()
                )
            except (ValueError, TypeError):
                tool["annual_cost"] = None

    # ── User count aliases ───────────────────────────────────────────────────
    if not tool.get("user_count"):
        raw_uc = _get(
            "user_count","user count","users","no of users","number of users",
            "# users","num users","active users","licensed users","seats",
            "headcount","user base","user volume")
        if raw_uc is not None:
            try:
                tool["user_count"] = int(float(str(raw_uc).replace(",","").strip()))
            except (ValueError, TypeError):
                tool["user_count"] = None

    # ── Age aliases ──────────────────────────────────────────────────────────
    if not tool.get("age_years"):
        raw_age = _get(
            "age_years","age","age (years)","app age","system age",
            "years in use","years old","years","age in years","application age")
        if raw_age is not None:
            try:
                tool["age_years"] = float(str(raw_age).replace(",","").strip())
            except (ValueError, TypeError):
                tool["age_years"] = None

    # ── Deployment aliases ───────────────────────────────────────────────────
    if not tool.get("deployment") or str(tool.get("deployment","")).strip().lower() in ("","nan"):
        tool["deployment"] = (
            _get("deployment","deployment model","hosting","hosting model",
                 "infrastructure","environment","cloud or on-prem",
                 "cloud/on-prem","deployment type","hosted") or None
        )

    # ── Integrations aliases ─────────────────────────────────────────────────
    if not tool.get("integrations"):
        raw_int = _get(
            "integrations","integration count","no of integrations",
            "number of integrations","# integrations","interfaces",
            "no of interfaces","connected systems","api connections")
        if raw_int is not None:
            try:
                tool["integrations"] = int(float(str(raw_int).replace(",","").strip()))
            except (ValueError, TypeError):
                tool["integrations"] = None

    # ── End of life aliases ──────────────────────────────────────────────────
    if not tool.get("end_of_life"):
        raw_eol = _get(
            "end_of_life","end of life","eol","end-of-life","retired",
            "sunset","decommissioned","legacy","is eol","eol flag")
        if raw_eol is not None:
            v = str(raw_eol).strip().lower()
            tool["end_of_life"] = v in ("yes","y","true","1","eol","sunset","legacy")

    # ── Compliance aliases ───────────────────────────────────────────────────
    if not tool.get("compliance_required"):
        raw_comp = _get(
            "compliance_required","compliance required","compliance","regulated",
            "regulatory","hipaa","gdpr","sox","pci","compliance flag",
            "needs compliance","compliance needed")
        if raw_comp is not None:
            v = str(raw_comp).strip().lower()
            tool["compliance_required"] = v in ("yes","y","true","1","required","regulated")

    # ── Business unit aliases ────────────────────────────────────────────────
    if not tool.get("business_unit") or str(tool.get("business_unit","")).strip().lower() in ("","nan"):
        tool["business_unit"] = (
            _get("business_unit","business unit","department","dept",
                 "division","team","org","organisation","organization",
                 "owner","business owner","cost centre","cost center") or None
        )

    # ── Coerce numeric fields robustly ────────────────────────────────────────
    for field in ("annual_cost", "age_years"):
        val = tool.get(field)
        if val is not None and not isinstance(val, (int, float)):
            try:
                tool[field] = float(
                    str(val).replace(",","").replace("$","").replace("£","")
                    .replace("€","").strip()
                )
            except (ValueError, TypeError):
                tool[field] = None
    for field in ("user_count", "integrations"):
        val = tool.get(field)
        if val is not None and not isinstance(val, int):
            try:
                tool[field] = int(float(str(val).replace(",","").strip()))
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


def _extract_tools_from_image(image_data: bytes, media_type: str) -> List[Dict]:
    """Use Claude vision to extract tool records from an image or slide screenshot."""
    prompt_text = (
        "This image may contain an architecture diagram, portfolio slide, technology landscape, "
        "or list of enterprise applications. Extract every application, tool, or system you can identify. "
        "Return ONLY a valid JSON object with a 'tools' array."
    )
    result_str = call_claude_vision(EXTRACT_TOOLS_PROMPT, image_data, media_type, prompt_text)
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
        ASSESSMENT_NARRATIVE_PROMPT
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
        f"Portfolio (pre-scored by ScoringEngine):\n{json.dumps(tool_summary, indent=2, default=_json_default)}\n\n"
        f"Duplications found:\n{json.dumps(duplications[:10], indent=2, default=_json_default)}"
    )
    # Inject industry context if provided
    industry = input_data.get("industry", "")
    sub_sector = input_data.get("sub_sector", "")
    if industry:
        enriched_prompt += get_industry_context(industry, sub_sector)

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
        }, default=_json_default),
        agent="TIME",
    )

    return result
