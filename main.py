import base64
import os
import zlib
from pathlib import Path
from typing import Optional, Dict, Any

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
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

_ASSESSMENT_HTML = ""
for _ap in [
    Path(__file__).parent / "frontend" / "ea_assessment.html",
    Path("frontend") / "ea_assessment.html",
    Path("/var/task/frontend/ea_assessment.html"),
]:
    try:
        if _ap.exists():
            _ASSESSMENT_HTML = _ap.read_text(encoding="utf-8")
            break
    except Exception:
        continue

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

app.add_middleware(GZipMiddleware, minimum_size=1000)
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


@app.get("/assessment", response_class=HTMLResponse, include_in_schema=False)
def serve_assessment():
    if _ASSESSMENT_HTML:
        return HTMLResponse(content=_ASSESSMENT_HTML)
    return HTMLResponse(content="<h2>EA Maturity Assessment — file not found</h2>")


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

# ── ARB proposal extraction prompt ───────────────────────────────────────────
_ARB_EXTRACT_PROMPT = """You are an Enterprise Architecture governance expert.
Extract architecture proposal details from the provided document, image or text.
Return ONLY a valid JSON object with exactly these fields (use null for anything not found):
{
  "proposal_title": "...",
  "description": "...",
  "technology_stack": ["tech1", "tech2"],
  "timeline": "...",
  "estimated_cost": 0,
  "annual_running_cost": 0,
  "business_case": "...",
  "current_system": "...",
  "integration_points": "...",
  "security_compliance": "...",
  "data_sensitivity": "...",
  "alternatives_considered": "..."
}
Extract every detail you can find. Do not invent information that is not in the source."""


@app.post("/arb/ingest")
async def arb_ingest(
    file: Optional[UploadFile] = File(None),
    free_text: Optional[str] = Form(None),
):
    """
    Extract structured ARB proposal fields from an uploaded document or image.
    Supports: PDF, PPTX, DOCX, TXT, MD, PNG, JPG, JPEG, GIF, WEBP.
    Returns JSON with proposal_title, description, technology_stack, costs, etc.
    """
    from services.claude_service import call_claude, call_claude_vision
    import json as _json

    def _parse_result(raw: str) -> dict:
        clean = raw.strip().lstrip("```json").lstrip("```").rstrip("```").strip()
        return _json.loads(clean)

    # ── IMAGE / Vision path ───────────────────────────────────────────────────
    if file and file.filename:
        content = await file.read()
        ext = Path(file.filename).suffix.lower()
        media_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
                     ".gif": "image/gif", ".webp": "image/webp"}

        if ext in media_map:
            raw = call_claude_vision(
                _ARB_EXTRACT_PROMPT, content, media_map[ext],
                "Extract all architecture proposal details visible in this image. Return structured JSON."
            )
            try:
                return _parse_result(raw)
            except Exception:
                raise HTTPException(422, f"Could not parse image extraction: {raw[:300]}")

        # ── PDF ───────────────────────────────────────────────────────────────
        if ext == ".pdf":
            import pypdf, io as _io
            reader = pypdf.PdfReader(_io.BytesIO(content))
            extracted = "\n".join(page.extract_text() or "" for page in reader.pages)
            if not extracted.strip():
                # Scanned / image-based PDF — run vision on each page image
                for page in reader.pages:
                    for img_obj in page.images:
                        raw = call_claude_vision(
                            _ARB_EXTRACT_PROMPT, img_obj.data, "image/png",
                            "This is a page from an architecture proposal document. Extract all proposal details."
                        )
                        try:
                            return _parse_result(raw)
                        except Exception:
                            continue
                raise HTTPException(422, "PDF appears to be image-only and no page images could be read.")

        # ── PPTX / PPT ────────────────────────────────────────────────────────
        elif ext in (".pptx", ".ppt"):
            from pptx import Presentation
            import io as _io
            prs = Presentation(_io.BytesIO(content))
            texts = []
            for slide in prs.slides:
                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        texts.append(shape.text.strip())
            extracted = "\n".join(texts)

        # ── DOCX ─────────────────────────────────────────────────────────────
        elif ext in (".docx", ".doc"):
            try:
                import docx as _docx, io as _io
                doc = _docx.Document(_io.BytesIO(content))
                extracted = "\n".join(p.text for p in doc.paragraphs if p.text.strip())
            except Exception:
                extracted = content.decode("utf-8", errors="replace")

        # ── Plain text / Markdown ─────────────────────────────────────────────
        else:
            extracted = content.decode("utf-8", errors="replace")

    elif free_text:
        extracted = free_text
    else:
        raise HTTPException(400, "No file or text provided.")

    if not extracted.strip():
        raise HTTPException(422, "No readable content found in the uploaded file.")

    raw = call_claude(
        _ARB_EXTRACT_PROMPT,
        f"Extract the ARB proposal details from this document:\n\n{extracted[:8000]}"
    )
    try:
        return _parse_result(raw)
    except Exception:
        raise HTTPException(422, f"Could not structure the extracted content. Raw: {raw[:300]}")


@app.post("/time/ingest")
async def time_ingest(
    file: Optional[UploadFile] = File(None),
    free_text: Optional[str] = Form(None),
    applications: Optional[str] = Form(None),  # JSON string of tool list
    industry: Optional[str] = Form(None),
    sub_sector: Optional[str] = Form(None),
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
            import tempfile, pandas as pd, json as _json
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(content)
                tmp_path = tmp.name
            df = pd.read_excel(tmp_path)
            os.unlink(tmp_path)
            # Use pandas JSON round-trip to convert numpy types and NaN → None
            tools_raw = _json.loads(df.to_json(orient="records"))

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
        "industry": industry or "",
        "sub_sector": sub_sector or "",
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
    try:
        pipeline = run_full_pipeline(body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Pipeline execution failed: {str(e)}")

    try:
        report_path = _reporter.generate_pipeline_pdf(
            pipeline=pipeline,
            output_dir=str(REPORTS_DIR),
        )
        pipeline["report_path"] = report_path
        pipeline["report_filename"] = Path(report_path).name
        # Embed PDF as base64 so the browser can download it directly
        # without a second request (Vercel /tmp is not shared across invocations)
        with open(report_path, "rb") as f:
            pdf_bytes = f.read()
        # Compress before base64 to stay within Vercel's 4.5 MB response limit
        compressed = zlib.compress(pdf_bytes, level=9)
        pipeline["report_b64"] = base64.b64encode(compressed).decode("ascii")
        pipeline["report_compressed"] = True
        pipeline["report_size_kb"] = round(len(pdf_bytes) / 1024, 1)
    except Exception as e:
        pipeline["report_error"] = str(e)
        pipeline["report_filename"] = None
        pipeline["report_b64"] = None

    return pipeline


@app.post("/ea-pipeline/step")
async def pipeline_wizard_step(body: Dict[str, Any]):
    """
    Step-by-step wizard endpoint: accepts pre-computed TIME + MAPPING results,
    runs MATURITY → INSIGHTS, generates PDF.  Called from the frontend wizard
    after Steps 1 (TIME) and 2 (MAPPING) are already shown to the user.

    Body keys:
      time_result        — output from /time/ingest (full JSON)
      mapping_result     — output from MAPPING agent (or null)
      assessment_results — questionnaire answers from inline questionnaire
      industry, sub_sector, governance, ea_framework, ea_tools,
      cloud_strategy, additional_context
    """
    from agents.full_pipeline import run_pipeline_from_step3
    try:
        pipeline = run_pipeline_from_step3(body)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Wizard pipeline failed: {str(e)}")

    try:
        report_path = _reporter.generate_pipeline_pdf(
            pipeline=pipeline,
            output_dir=str(REPORTS_DIR),
        )
        pipeline["report_filename"] = Path(report_path).name
        with open(report_path, "rb") as f:
            pdf_bytes = f.read()
        compressed = zlib.compress(pdf_bytes, level=9)
        pipeline["report_b64"] = base64.b64encode(compressed).decode("ascii")
        pipeline["report_compressed"] = True
        pipeline["report_size_kb"] = round(len(pdf_bytes) / 1024, 1)
    except Exception as e:
        pipeline["report_error"] = str(e)
        pipeline["report_filename"] = None
        pipeline["report_b64"] = None

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


# ─── AI Assistant Chat ────────────────────────────────────────────────────────

_EA_CHAT_PROMPT = """You are the EA Intelligence Assistant — a step-by-step guide embedded in the EA AI Intelligence platform. You work like GPS turn-by-turn navigation: always tell the user EXACTLY what to do next — which page to go to, which button to click, what to type or upload.

GUIDANCE STYLE RULES (mandatory):
- Always respond with a numbered current step, then a clear "NEXT: [exact action]" instruction.
- Never give generic advice. Always name the exact page, button label, or field.
- After each user message, tell them what the NEXT concrete action is.
- If they say "next", "done", "what now", or similar, immediately give the next step.
- Keep responses short (3-6 lines max). No long paragraphs.

STEP-BY-STEP FLOW:
STEP 1 — Go to AI Agents (left sidebar) to run individual agent queries, or go to Reports for the full pipeline.
STEP 2 — In AI Agents: select an agent (ARB, TIME, MAPPING, MATURITY), enter your query, and click Run.
STEP 3 — For the full 4-agent pipeline: go to Reports → click "Run Full Pipeline" or "Run Pipeline →".
STEP 4 — Review TIME classifications on screen (INVEST / TOLERATE / MIGRATE / ELIMINATE).
STEP 5 — The full pipeline runs all 4 agents: TIME > MAPPING > MATURITY > INSIGHTS (~60-90 sec).
STEP 6 — Review the on-screen EA Intelligence report preview.
STEP 7 — Click "Download PDF Report" to get the full consulting-grade PDF.

PLATFORM AGENTS:
- ARB: Architecture Review Board — reviews proposals, returns APPROVE/REJECT/CONDITIONAL + compliance score + risks.
- TIME: Portfolio Rationalization — scores apps 0-10 on 7 dimensions, classifies as INVEST/TOLERATE/MIGRATE/ELIMINATE, assigns 6R action (Retain/Rehost/Replatform/Refactor/Replace/Retire).
- MAPPING: Dependency Analysis — maps upstream/downstream dependencies, coupling scores, migration risk.
- MATURITY: EA Maturity Assessment — scores EA practice 1-5 across 6 dimensions.
- INSIGHTS: Executive Synthesis — C-suite summary, financial impact, KPIs, quick wins.

CSV format: name, vendor, category, annual_cost, user_count, criticality, deployment, integrations, age_years, end_of_life, compliance_required, business_unit
Valid criticality: Critical, High, Medium, Low
Valid categories: Monitoring, Logging, APM, Security, ITSM, Collaboration, CRM, ERP, BSS, OSS, Cloud, Analytics, DevOps, Network, Storage, Database, Other

TIME score: >= 7.5 + low risk = INVEST. 5-7.5 = TOLERATE. On-prem + debt = MIGRATE. EOL or < 3.5 = ELIMINATE.

Always end your reply with: "NEXT: [exact action the user should take now]" """


@app.post("/chat")
async def chat_assistant(body: Dict[str, Any]):
    """EA Intelligence floating assistant chatbot."""
    from services.claude_service import call_claude_with_history
    messages = body.get("messages", [])
    if not messages:
        raise HTTPException(400, "messages required")
    response = call_claude_with_history(_EA_CHAT_PROMPT, messages)
    return {"response": response}


# ─── Helper ──────────────────────────────────────────────────────────────────

def _time_counts(tools: list) -> dict:
    counts: dict = {}
    for t in tools:
        tc = t.get("time_classification", "TOLERATE")
        counts[tc] = counts.get(tc, 0) + 1
    return counts
