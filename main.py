import os
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

# Load frontend HTML at startup so Vercel Lambda can serve it from memory
_FRONTEND_HTML = ""
try:
    _frontend_path = Path(__file__).parent / "frontend" / "index.html"
    if _frontend_path.exists():
        _FRONTEND_HTML = _frontend_path.read_text(encoding="utf-8")
except Exception:
    pass

from models.schemas import EARequest, EAResponse
from orchestrator import route_request, resolve_agents
from agents.arb_agent import run_arb
from agents.time_agent import run_time, _score_tools, _extract_tools_from_text, _extract_tools_from_image
from agents.mapping_agent import run_mapping
from agents.maturity_agent import run_maturity
from agents.insights_agent import run_insights
from agents.full_pipeline import run_full_pipeline
from utils.duplication_detector import DuplicationDetector
from utils.report_generator import ReportGenerator

_on_vercel = os.getenv("VERCEL") == "1"
REPORTS_DIR = Path("/tmp/ea-reports") if _on_vercel else Path(__file__).parent / "reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

_detector = DuplicationDetector()
_reporter = ReportGenerator()

app = FastAPI(
    title="EA AI Intelligence",
    description="Multi-agent Enterprise Architecture AI platform — ARB, TIME, Mapping, Maturity, Insights",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

AGENT_MAP = {
    "ARB": run_arb,
    "TIME": run_time,
    "MAPPING": run_mapping,
    "MATURITY": run_maturity,
    "INSIGHTS": run_insights,
}

_FRONTEND_DIR = Path(__file__).parent / "frontend"
if _FRONTEND_DIR.exists() and not _on_vercel:
    app.mount("/ui", StaticFiles(directory=str(_FRONTEND_DIR), html=True), name="frontend")


# ─── Root — serve frontend ────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def serve_ui():
    if _FRONTEND_HTML:
        return HTMLResponse(content=_FRONTEND_HTML)
    return HTMLResponse(content="<h2>EA AI Intelligence — <a href='/docs'>See API Docs</a></h2>")


# ─── Core EA Agent endpoint ───────────────────────────────────────────────────

@app.get("/health")
def health():
    return {
        "status": "EA AI Intelligence running",
        "version": "1.0.0",
        "agents": list(AGENT_MAP.keys()),
    }


@app.post("/ea-agent", response_model=EAResponse)
def handle_request(request: EARequest):
    try:
        if request.agent_override:
            override = request.agent_override.upper()
            if override not in AGENT_MAP:
                raise HTTPException(
                    status_code=400,
                    detail=f"Unknown agent '{override}'. Valid: {list(AGENT_MAP.keys())}",
                )
            agents_to_run = [override]
        else:
            intent = route_request(request.query)
            agents_to_run = resolve_agents(intent, request.query)

        results: dict = {}
        for agent_name in agents_to_run:
            if agent_name in AGENT_MAP:
                results[agent_name] = AGENT_MAP[agent_name](request.data or {})

        if len(agents_to_run) > 1 and "INSIGHTS" not in agents_to_run:
            results["INSIGHTS"] = run_insights(results)
            agents_to_run = agents_to_run + ["INSIGHTS"]

        return EAResponse(
            agent_used=agents_to_run[0] if len(agents_to_run) == 1 else "MULTI",
            result=results,
            agents_chain=agents_to_run,
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ─── TIME / Portfolio endpoints ───────────────────────────────────────────────

@app.post("/time/ingest")
async def time_ingest(
    file: Optional[UploadFile] = File(None),
    free_text: Optional[str] = Form(None),
    applications: Optional[str] = Form(None),  # JSON string of tool list
):
    """
    Ingest portfolio data (file upload, free text, or JSON body),
    score every tool with the ScoringEngine, detect duplications,
    and return the enriched portfolio ready for report generation.
    """
    tools_raw = []

    if file and file.filename:
        content = await file.read()
        ext = Path(file.filename).suffix.lower()

        if ext == ".json":
            import json
            data = json.loads(content)
            tools_raw = data if isinstance(data, list) else list(data.values())[0] if data else []

        elif ext in (".csv",):
            import csv, io
            reader = csv.DictReader(io.StringIO(content.decode("utf-8", errors="replace")))
            tools_raw = list(reader)

        elif ext in (".xlsx", ".xls"):
            import tempfile, pandas as pd
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            df = pd.read_excel(tmp_path)
            tools_raw = df.to_dict("records")
            os.unlink(tmp_path)

        elif ext == ".pdf":
            import pypdf, io as _io
            reader = pypdf.PdfReader(_io.BytesIO(content))
            extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
            if extracted.strip():
                tools_raw = _extract_tools_from_text(extracted)
            else:
                # Scanned/image-only PDF — use vision on each page image
                page_tools: list = []
                for page in reader.pages:
                    for img_obj in page.images:
                        page_tools.extend(_extract_tools_from_image(img_obj.data, "image/png"))
                tools_raw = page_tools

        elif ext in (".pptx", ".ppt"):
            from pptx import Presentation
            import io as _io
            prs = Presentation(_io.BytesIO(content))
            slide_texts = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        slide_texts.append(shape.text)
            tools_raw = _extract_tools_from_text("\n".join(slide_texts))

        elif ext in (".png", ".jpg", ".jpeg", ".gif", ".webp"):
            media_map = {
                ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                ".gif": "image/gif", ".webp": "image/webp",
            }
            tools_raw = _extract_tools_from_image(content, media_map[ext])

        else:
            # Plain text fallback
            tools_raw = _extract_tools_from_text(content.decode("utf-8", errors="replace"))

    elif free_text:
        tools_raw = _extract_tools_from_text(free_text)

    elif applications:
        import json
        tools_raw = json.loads(applications)

    if not tools_raw:
        raise HTTPException(400, "No portfolio data provided. Send a file, free_text, or applications JSON.")

    scored = _score_tools(tools_raw)
    duplications = _detector.detect_duplications(scored)

    return {
        "success": True,
        "tools_scored": len(scored),
        "applications": scored,
        "duplications": duplications,
        "summary": {
            "total_apps": len(scored),
            "total_annual_cost": sum(t.get("annual_cost") or 0 for t in scored),
            "duplications_found": len(duplications),
            "potential_savings": sum(d.get("potential_annual_savings", 0) for d in duplications),
            "time_breakdown": _time_counts(scored),
        },
    }


@app.post("/time/report")
async def time_report(body: Dict[str, Any]):
    """
    Generate a PDF portfolio rationalization report.

    Body:
      applications  — list of scored tool dicts (from /time/ingest)
      duplications  — list of duplication records  (from /time/ingest)
      assessments   — optional list of Claude narrative assessments
    """
    tools = body.get("applications", [])
    duplications = body.get("duplications", [])
    assessments = body.get("assessments", [])

    if not tools:
        raise HTTPException(400, "applications list is required.")

    report_path = _reporter.generate(
        tools=tools,
        duplications=duplications,
        assessments=assessments,
        output_dir=str(REPORTS_DIR),
        fmt="pdf",
    )

    return FileResponse(
        path=report_path,
        filename=Path(report_path).name,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{Path(report_path).name}"'},
    )


@app.post("/time/full")
async def time_full(body: Dict[str, Any]):
    """
    One-shot: score portfolio + Claude TIME narrative. Returns JSON only (no PDF).
    Body: { applications: [...] } or { free_text: "..." }
    """
    result = run_time(body)
    return result


# ─── Full EA Pipeline ─────────────────────────────────────────────────────────

@app.post("/ea-full")
async def ea_full(body: Dict[str, Any]):
    """
    Full 4-stage EA Intelligence pipeline:
      TIME → MAPPING → MATURITY → INSIGHTS → PDF report

    Body: { applications: [...] }  or  { free_text: "..." }

    Returns:
      - pipeline JSON with all 4 agent outputs
      - report_url: path to the downloadable PDF report
    """
    pipeline = run_full_pipeline(body)

    report_path = _reporter.generate_pipeline_pdf(
        pipeline=pipeline,
        output_dir=str(REPORTS_DIR),
    )

    pipeline["report_path"] = report_path
    pipeline["report_filename"] = Path(report_path).name
    return pipeline


@app.get("/ea-full/report/{filename}")
async def download_pipeline_report(filename: str):
    """Download a previously generated full-pipeline PDF report."""
    report_path = REPORTS_DIR / filename
    if not report_path.exists():
        raise HTTPException(404, f"Report '{filename}' not found.")
    return FileResponse(
        path=str(report_path),
        filename=filename,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# ─── Helper ──────────────────────────────────────────────────────────────────

def _time_counts(tools: list) -> dict:
    counts: dict = {}
    for t in tools:
        tc = t.get("time_classification", "TOLERATE")
        counts[tc] = counts.get(tc, 0) + 1
    return counts
