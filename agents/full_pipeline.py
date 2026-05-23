"""
Full EA Intelligence Pipeline: TIME → MAPPING → MATURITY → INSIGHTS
Each agent receives the accumulated outputs of all prior agents as context.
Industry context (when provided) is threaded through every stage.
"""
import json
from agents.time_agent import run_time
from agents.mapping_agent import run_mapping_batch
from agents.maturity_agent import run_maturity
from agents.insights_agent import run_insights


def run_full_pipeline(input_data: dict) -> dict:
    """
    Executes the complete 4-agent EA pipeline in sequence.
    Each stage feeds its output into the next stage's context.

    Returns a structured dict with keys: TIME, MAPPING, MATURITY, INSIGHTS, pipeline_summary.
    """
    pipeline = {}
    errors = {}

    # Extract industry context to pass through all stages
    industry = input_data.get("industry", "")
    sub_sector = input_data.get("sub_sector", "")

    # ── STAGE 1: TIME — Portfolio Rationalization ─────────────────────────────
    print(f"[Pipeline] Stage 1/4 — TIME: Portfolio Rationalization... (industry={industry or 'general'})")
    try:
        time_input = {**input_data, "industry": industry, "sub_sector": sub_sector}
        time_result = run_time(time_input)
        pipeline["TIME"] = time_result
    except Exception as e:
        errors["TIME"] = str(e)
        pipeline["TIME"] = {}

    applications = pipeline["TIME"].get("applications", [])
    duplications = pipeline["TIME"].get("duplications", [])
    time_summary = pipeline["TIME"].get("portfolio_summary", {})
    time_assessment = pipeline["TIME"].get("assessment", {})

    # ── STAGE 2: MAPPING — Dependency & Impact Analysis ───────────────────────
    # Only analyze apps flagged for ELIMINATE or MIGRATE
    flagged = [
        a for a in applications
        if a.get("time_classification") in ("ELIMINATE", "MIGRATE")
    ]
    print(f"[Pipeline] Stage 2/4 — MAPPING: {len(flagged)} flagged apps...")
    if flagged:
        try:
            mapping_input = {
                "applications": flagged,
                "all_apps": applications,
                "context": "Full EA pipeline — dependency analysis for ELIMINATE/MIGRATE apps",
                "industry": industry,
                "sub_sector": sub_sector,
            }
            pipeline["MAPPING"] = run_mapping_batch(mapping_input)
        except Exception as e:
            errors["MAPPING"] = str(e)
            pipeline["MAPPING"] = {"skipped": "No flagged apps or error", "error": str(e)}
    else:
        pipeline["MAPPING"] = {
            "skipped": True,
            "reason": "No ELIMINATE/MIGRATE apps in portfolio — no dependency risk to analyse.",
        }

    # ── STAGE 3: MATURITY — EA Maturity Assessment ────────────────────────────
    print("[Pipeline] Stage 3/4 — MATURITY: EA Maturity Assessment...")
    try:
        # Derive organisational EA maturity signals from the TIME output
        avg_score = (
            sum(a.get("composite_score", 5) for a in applications) / max(len(applications), 1)
        )
        categories = list({a.get("category", "Other") for a in applications})
        eliminate_pct = round(
            time_summary.get("time_breakdown", {}).get("ELIMINATE", 0)
            / max(len(applications), 1) * 100
        )
        maturity_input = {
            "context": "EA maturity assessment derived from portfolio rationalization",
            "industry": industry,
            "sub_sector": sub_sector,
            "portfolio_size": len(applications),
            "avg_composite_score": round(avg_score, 2),
            "categories_covered": categories,
            "eliminate_percentage": eliminate_pct,
            "duplications_found": len(duplications),
            "total_annual_cost": time_summary.get("total_annual_cost", 0),
            "time_breakdown": time_summary.get("time_breakdown", {}),
            "has_cmdb_data": any(a.get("integrations") is not None for a in applications),
            "has_cost_data": any(a.get("annual_cost") is not None for a in applications),
            "has_risk_scores": any(a.get("scores") for a in applications),
            # Pass TIME assessment as evidence of EA governance maturity
            "portfolio_health": time_assessment.get("portfolio_overview", {}).get("portfolio_health", "Unknown"),
        }
        pipeline["MATURITY"] = run_maturity(maturity_input)
    except Exception as e:
        errors["MATURITY"] = str(e)
        pipeline["MATURITY"] = {}

    # ── STAGE 4: INSIGHTS — Executive Synthesis ───────────────────────────────
    print("[Pipeline] Stage 4/4 — INSIGHTS: Executive Synthesis...")
    try:
        # Feed ALL prior outputs to INSIGHTS for full synthesis
        insights_input = {
            "pipeline": "full_ea_intelligence",
            "industry": industry,
            "sub_sector": sub_sector,
            "time_output": {
                "portfolio_summary": time_summary,
                "assessment": time_assessment,
                "duplications_count": len(duplications),
                "top_recommendations": time_assessment.get("top_recommendations", [])[:5],
                "expected_outcomes": time_assessment.get("expected_outcomes", {}),
            },
            "mapping_output": pipeline.get("MAPPING", {}),
            "maturity_output": {
                "overall_score": pipeline.get("MATURITY", {}).get("overall_maturity_score"),
                "maturity_level": pipeline.get("MATURITY", {}).get("maturity_level"),
                "top_priorities": pipeline.get("MATURITY", {}).get("top_priorities", []),
                "dimensions": pipeline.get("MATURITY", {}).get("dimensions", {}),
            },
        }
        pipeline["INSIGHTS"] = run_insights(insights_input)
    except Exception as e:
        errors["INSIGHTS"] = str(e)
        pipeline["INSIGHTS"] = {}

    # ── Pipeline Summary ──────────────────────────────────────────────────────
    pipeline["pipeline_summary"] = {
        "industry": industry or "General",
        "sub_sector": sub_sector or "",
        "stages_completed": [s for s in ["TIME", "MAPPING", "MATURITY", "INSIGHTS"] if s not in errors],
        "stages_failed": list(errors.keys()),
        "errors": errors,
        "total_apps_assessed": len(applications),
        "flagged_for_action": len(flagged),
        "maturity_score": pipeline.get("MATURITY", {}).get("overall_maturity_score"),
        "overall_risk": pipeline.get("INSIGHTS", {}).get("risk_profile", {}).get("overall_risk"),
        "potential_savings": time_summary.get("potential_savings", 0),
        "total_annual_cost": time_summary.get("total_annual_cost", 0),
    }

    print(f"[Pipeline] Complete. Stages: {pipeline['pipeline_summary']['stages_completed']}")
    return pipeline
