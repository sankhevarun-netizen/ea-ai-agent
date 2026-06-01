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

    # ── Extract all context fields passed from the frontend ───────────────────
    industry     = input_data.get("industry", "")
    sub_sector   = input_data.get("sub_sector", "")

    # EA context (from the Additional Context wizard on EA Analysis page)
    ea_ctx = input_data.get("ea_context", {}) or {}
    if not industry:
        industry   = ea_ctx.get("industry", "")
    if not sub_sector:
        sub_sector = ea_ctx.get("sub_sector", "")
    governance       = ea_ctx.get("governance", "")
    ea_framework     = ea_ctx.get("ea_framework", "")
    ea_tools         = ea_ctx.get("ea_tools", "")
    cloud_strategy   = ea_ctx.get("cloud_strategy", "")
    additional_ctx   = ea_ctx.get("additional_context", "")

    # Mapping context (from the Additional Context section on Mapping page)
    map_ctx = input_data.get("mapping_context", {}) or {}
    known_integrations       = map_ctx.get("known_integrations", "")
    planned_changes          = map_ctx.get("planned_changes", "")
    cloud_target             = map_ctx.get("cloud_target", "")
    data_sensitivity         = map_ctx.get("data_sensitivity", "")
    integration_complexity   = map_ctx.get("integration_complexity", "")
    cmdb_tool                = map_ctx.get("cmdb_tool", "")
    map_notes                = map_ctx.get("additional_notes", "")

    # Combine for a unified context block threaded through all stages
    unified_context = {
        "industry":               industry,
        "sub_sector":             sub_sector,
        "governance":             governance,
        "ea_framework":           ea_framework,
        "ea_tools":               ea_tools,
        "cloud_strategy":         cloud_strategy or cloud_target,
        "additional_context":     additional_ctx,
        "known_integrations":     known_integrations,
        "planned_changes":        planned_changes,
        "data_sensitivity":       data_sensitivity,
        "integration_complexity": integration_complexity,
        "cmdb_tool":              cmdb_tool,
        "mapping_notes":          map_notes,
    }

    # ── STAGE 1: TIME — Portfolio Rationalization ─────────────────────────────
    print(f"[Pipeline] Stage 1/4 — TIME (industry={industry or 'general'}, governance={governance or 'unknown'})")
    try:
        time_input = {
            **input_data,
            **unified_context,
        }
        time_result = run_time(time_input)
        pipeline["TIME"] = time_result
    except Exception as e:
        errors["TIME"] = str(e)
        pipeline["TIME"] = {}

    applications    = pipeline["TIME"].get("applications", [])
    duplications    = pipeline["TIME"].get("duplications", [])
    time_summary    = pipeline["TIME"].get("portfolio_summary", {})
    time_assessment = pipeline["TIME"].get("assessment", {})

    # ── ARB result (pre-computed by the stepper before this pipeline call) ────────
    arb_result = input_data.get("arb_result") or {}
    arb_decision    = arb_result.get("decision", "NOT_RUN")
    arb_conditions  = arb_result.get("conditions", [])
    arb_risks       = arb_result.get("risks", [])
    arb_compliance  = arb_result.get("compliance_score", 0)
    arb_summary = (
        f"ARB Decision: {arb_decision}. "
        f"Compliance score: {arb_compliance}. "
        f"Conditions: {'; '.join(arb_conditions[:3]) if arb_conditions else 'None'}. "
        f"Key risks: {'; '.join(arb_risks[:3]) if arb_risks else 'None'}."
    ) if arb_result else ""
    if arb_summary:
        unified_context["arb_governance"] = arb_summary
        if additional_ctx:
            unified_context["additional_context"] = f"{additional_ctx}\n{arb_summary}"
        else:
            unified_context["additional_context"] = arb_summary

    # ── STAGE 2: MAPPING — Dependency Impact Analysis (flagged apps only) ───────
    # Only analyse apps flagged ELIMINATE or MIGRATE — others don't need migration impact
    flagged = [
        a for a in applications
        if a.get("time_classification") in ("ELIMINATE", "MIGRATE")
    ]
    print(f"[Pipeline] Stage 2/4 — MAPPING: {len(flagged)} flagged apps (ELIMINATE/MIGRATE)...")
    if flagged:
        try:
            mapping_input = {
                "applications": flagged,
                "all_apps":               applications,
                "industry":               industry,
                "sub_sector":             sub_sector,
                "governance":             governance,
                "ea_framework":           ea_framework,
                "cloud_target":           unified_context["cloud_strategy"],
                "known_integrations":     known_integrations,
                "planned_changes":        planned_changes,
                "data_sensitivity":       data_sensitivity,
                "integration_complexity": integration_complexity,
                "cmdb_tool":              cmdb_tool,
                "additional_context":     f"{additional_ctx}\n{map_notes}".strip(),
            }
            pipeline["MAPPING"] = run_mapping_batch(mapping_input)
        except Exception as e:
            errors["MAPPING"] = str(e)
            pipeline["MAPPING"] = {"error": str(e)}
    else:
        pipeline["MAPPING"] = {
            "skipped": True,
            "reason": "No ELIMINATE/MIGRATE applications in portfolio — no dependency risk to analyse.",
        }

    # ── STAGE 3: MATURITY — EA Maturity Assessment ────────────────────────────
    print("[Pipeline] Stage 3/4 — MATURITY: EA Maturity Assessment...")
    assessment_results = input_data.get("assessment_results") or {}
    try:
        avg_score = sum(a.get("composite_score", 5) for a in applications) / max(len(applications), 1)
        categories = list({a.get("category", "Other") for a in applications})
        eliminate_pct = round(
            time_summary.get("time_breakdown", {}).get("ELIMINATE", 0) / max(len(applications), 1) * 100
        )
        maturity_input = {
            "industry":               industry,
            "sub_sector":             sub_sector,
            "governance":             governance,
            "ea_framework":           ea_framework,
            "ea_tools":               ea_tools,
            "cloud_strategy":         unified_context["cloud_strategy"],
            "additional_context":     additional_ctx,
            "known_integrations":     known_integrations,
            "cmdb_tool":              cmdb_tool,
            "portfolio_size":         len(applications),
            "avg_composite_score":    round(avg_score, 2),
            "categories_covered":     categories,
            "eliminate_percentage":   eliminate_pct,
            "duplications_found":     len(duplications),
            "total_annual_cost":      time_summary.get("total_annual_cost", 0),
            "time_breakdown":         time_summary.get("time_breakdown", {}),
            "has_cmdb_data":          bool(cmdb_tool) or any(a.get("integrations") is not None for a in applications),
            "has_cost_data":          any(a.get("annual_cost") is not None for a in applications),
            "portfolio_health":       time_assessment.get("portfolio_overview", {}).get("portfolio_health", "Unknown"),
            "mapping_complexity":     pipeline.get("MAPPING", {}).get("overall_impact_level", "UNKNOWN"),
            # Human assessment questionnaire results (30Q, up to 15 respondents)
            "assessment_results":     assessment_results,
        }
        pipeline["MATURITY"] = run_maturity(maturity_input)
    except Exception as e:
        errors["MATURITY"] = str(e)
        pipeline["MATURITY"] = {}

    # ── STAGE 4: INSIGHTS — Executive Synthesis ───────────────────────────────
    print("[Pipeline] Stage 4/4 — INSIGHTS: Executive Synthesis...")
    try:
        insights_input = {
            "pipeline":    "full_ea_intelligence",
            "industry":    industry,
            "sub_sector":  sub_sector,
            "governance":  governance,
            "ea_framework": ea_framework,
            "additional_context": additional_ctx,
            "cloud_strategy": unified_context["cloud_strategy"],
            "time_output": {
                "portfolio_summary":     time_summary,
                "assessment":            time_assessment,
                "duplications_count":    len(duplications),
                "top_recommendations":   time_assessment.get("top_recommendations", [])[:5],
                "expected_outcomes":     time_assessment.get("expected_outcomes", {}),
            },
            "mapping_output": pipeline.get("MAPPING", {}),
            "arb_output": {
                "decision":          arb_decision,
                "compliance_score":  arb_compliance,
                "conditions":        arb_conditions[:5],
                "risks":             arb_risks[:5],
                "recommendations":   arb_result.get("recommendations", [])[:5],
                "integration_complexity": arb_result.get("integration_complexity", ""),
            } if arb_result else {},
            "maturity_output": {
                "overall_score":    pipeline.get("MATURITY", {}).get("overall_maturity_score"),
                "maturity_level":   pipeline.get("MATURITY", {}).get("maturity_level"),
                "top_priorities":   pipeline.get("MATURITY", {}).get("top_priorities", []),
                "dimensions":       pipeline.get("MATURITY", {}).get("dimensions", {}),
            },
        }
        pipeline["INSIGHTS"] = run_insights(insights_input)
    except Exception as e:
        errors["INSIGHTS"] = str(e)
        pipeline["INSIGHTS"] = {}

    # ── Pipeline Summary ──────────────────────────────────────────────────────
    pipeline["pipeline_summary"] = {
        "industry":             industry or "General",
        "sub_sector":           sub_sector or "",
        "governance":           governance or "",
        "ea_framework":         ea_framework or "",
        "cloud_strategy":       unified_context["cloud_strategy"] or "",
        "stages_completed":     [s for s in ["TIME","MAPPING","MATURITY","INSIGHTS"] if s not in errors],
        "stages_failed":        list(errors.keys()),
        "errors":               errors,
        "total_apps_assessed":  len(applications),
        "flagged_for_action":   len(flagged),
        "maturity_score":       pipeline.get("MATURITY", {}).get("overall_maturity_score"),
        "overall_risk":         pipeline.get("INSIGHTS", {}).get("risk_profile", {}).get("overall_risk"),
        "potential_savings":    time_summary.get("potential_savings", 0),
        "total_annual_cost":    time_summary.get("total_annual_cost", 0),
    }

    print(f"[Pipeline] Complete. Stages: {pipeline['pipeline_summary']['stages_completed']}")
    return pipeline


def run_pipeline_from_step3(input_data: dict) -> dict:
    """
    Step-by-step wizard: run MATURITY + INSIGHTS using pre-computed TIME + MAPPING results.
    Called after the UI has already completed stages 1 (TIME) and 2 (MAPPING).
    """
    pipeline: dict = {}
    errors:   dict = {}

    time_result        = input_data.get("time_result", {})
    mapping_result     = input_data.get("mapping_result") or {}
    assessment_results = input_data.get("assessment_results") or {}

    industry       = input_data.get("industry", "")
    sub_sector     = input_data.get("sub_sector", "")
    governance     = input_data.get("governance", "")
    ea_framework   = input_data.get("ea_framework", "")
    ea_tools       = input_data.get("ea_tools", "")
    cloud_strategy = input_data.get("cloud_strategy", "")
    additional_ctx = input_data.get("additional_context", "")

    pipeline["TIME"]    = time_result
    pipeline["MAPPING"] = mapping_result if mapping_result else {
        "skipped": True, "reason": "Pre-computed in wizard step 2"
    }

    applications    = time_result.get("applications", [])
    duplications    = time_result.get("duplications", [])
    time_summary    = time_result.get("portfolio_summary") or time_result.get("summary") or {}
    time_assessment = time_result.get("assessment", {})

    # ── STAGE 3: MATURITY ────────────────────────────────────────
    print("[WizardPipeline] Stage 3 — MATURITY...")
    try:
        avg_score = sum(a.get("composite_score", 5) for a in applications) / max(len(applications), 1)
        categories = list({a.get("category", "Other") for a in applications})
        eliminate_pct = round(
            time_summary.get("time_breakdown", {}).get("ELIMINATE", 0)
            / max(len(applications), 1) * 100
        )
        maturity_input = {
            "industry":             industry,
            "sub_sector":           sub_sector,
            "governance":           governance,
            "ea_framework":         ea_framework,
            "ea_tools":             ea_tools,
            "cloud_strategy":       cloud_strategy,
            "additional_context":   additional_ctx,
            "portfolio_size":       len(applications),
            "avg_composite_score":  round(avg_score, 2),
            "categories_covered":   categories,
            "eliminate_percentage": eliminate_pct,
            "duplications_found":   len(duplications),
            "total_annual_cost":    time_summary.get("total_annual_cost", 0),
            "time_breakdown":       time_summary.get("time_breakdown", {}),
            "has_cmdb_data":        any(a.get("integrations") is not None for a in applications),
            "has_cost_data":        any(a.get("annual_cost") is not None for a in applications),
            "portfolio_health":     time_assessment.get("portfolio_overview", {}).get("portfolio_health", "Unknown"),
            "mapping_complexity":   (mapping_result.get("overall_impact_level", "UNKNOWN")
                                     if isinstance(mapping_result, dict) else "UNKNOWN"),
            "assessment_results":   assessment_results,
        }
        pipeline["MATURITY"] = run_maturity(maturity_input)
    except Exception as e:
        errors["MATURITY"] = str(e)
        pipeline["MATURITY"] = {}

    # ── STAGE 4: INSIGHTS ────────────────────────────────────────
    print("[WizardPipeline] Stage 4 — INSIGHTS...")
    try:
        insights_input = {
            "pipeline":           "full_ea_intelligence",
            "industry":           industry,
            "sub_sector":         sub_sector,
            "governance":         governance,
            "ea_framework":       ea_framework,
            "additional_context": additional_ctx,
            "cloud_strategy":     cloud_strategy,
            "time_output": {
                "portfolio_summary":   time_summary,
                "assessment":          time_assessment,
                "duplications_count":  len(duplications),
                "top_recommendations": time_assessment.get("top_recommendations", [])[:5],
                "expected_outcomes":   time_assessment.get("expected_outcomes", {}),
            },
            "mapping_output":  pipeline.get("MAPPING", {}),
            "maturity_output": {
                "overall_score":  pipeline.get("MATURITY", {}).get("overall_maturity_score"),
                "maturity_level": pipeline.get("MATURITY", {}).get("maturity_level"),
                "top_priorities": pipeline.get("MATURITY", {}).get("top_priorities", []),
                "dimensions":     pipeline.get("MATURITY", {}).get("dimensions", {}),
            },
        }
        pipeline["INSIGHTS"] = run_insights(insights_input)
    except Exception as e:
        errors["INSIGHTS"] = str(e)
        pipeline["INSIGHTS"] = {}

    # ── Pipeline Summary ─────────────────────────────────────────
    flagged = [a for a in applications if a.get("time_classification") in ("ELIMINATE", "MIGRATE")]
    pipeline["pipeline_summary"] = {
        "industry":            industry or "General",
        "sub_sector":          sub_sector or "",
        "governance":          governance or "",
        "ea_framework":        ea_framework or "",
        "cloud_strategy":      cloud_strategy or "",
        "stages_completed":    [s for s in ["TIME", "MAPPING", "MATURITY", "INSIGHTS"] if s not in errors],
        "stages_failed":       list(errors.keys()),
        "errors":              errors,
        "total_apps_assessed": len(applications),
        "flagged_for_action":  len(flagged),
        "maturity_score":      pipeline.get("MATURITY", {}).get("overall_maturity_score"),
        "overall_risk":        pipeline.get("INSIGHTS", {}).get("risk_profile", {}).get("overall_risk"),
        "potential_savings":   time_summary.get("potential_savings", 0),
        "total_annual_cost":   time_summary.get("total_annual_cost", 0),
    }

    print(f"[WizardPipeline] Done. Stages: {pipeline['pipeline_summary']['stages_completed']}")
    return pipeline
