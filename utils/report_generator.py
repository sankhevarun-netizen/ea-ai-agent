import io
import math
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from fpdf import FPDF


# ── Safe string helper (fpdf2 Helvetica only supports Latin-1) ────────────────

_UNICODE_MAP = {
    '–': '-',    # en dash
    '--': '-',    # em dash
    '‘': "'",    # left single quote
    '’': "'",    # right single quote
    '“': '"',    # left double quote
    '”': '"',    # right double quote
    '•': '-',    # bullet
    '…': '...', # ellipsis
    '→': '->',  # right arrow
    '←': '<-',  # left arrow
    ' ': ' ',   # non-breaking space
    '−': '-',   # minus sign
    '×': 'x',   # multiplication sign
    '·': '.',   # middle dot
    '♥': '',    # heart (drop it)
    '✓': 'v',   # check mark
    '✕': 'x',   # cross mark
}


def _safe_str(val, maxlen: int = 0) -> str:
    """Convert any value to a Latin-1–safe string for fpdf2 built-in fonts."""
    if val is None:
        return '-'
    s = str(val)
    for orig, rep in _UNICODE_MAP.items():
        s = s.replace(orig, rep)
    # Final fallback: drop anything still outside Latin-1
    s = s.encode('latin-1', errors='replace').decode('latin-1')
    return s[:maxlen] if maxlen else s


def _deep_sanitize(obj):
    """Recursively replace all strings in a dict/list with Latin-1-safe versions."""
    if isinstance(obj, str):
        return _safe_str(obj)
    if isinstance(obj, dict):
        return {k: _deep_sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_deep_sanitize(i) for i in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


# ── Colour palette ────────────────────────────────────────────────────────────
NAVY   = (10,  22,  40)
BLUE   = (0,   99,  220)
TEAL   = (0,   163, 161)
WHITE  = (255, 255, 255)
LGREY  = (248, 251, 255)
MGREY  = (232, 237, 248)
DGREY  = (100, 110, 130)
BLACK  = (26,  35,  64)
GREEN  = (21,  87,  36)
AMBER  = (133, 100, 4)
RED    = (114, 28,  36)
SLATE  = (56,  61,  65)

# ── Badge colour map ──────────────────────────────────────────────────────────
BADGE = {
    "invest":     (GREEN, (212, 237, 218)),
    "tolerate":   ((0,64,133), (204,229,255)),
    "migrate":    (AMBER, (255,243,205)),
    "eliminate":  (RED,   (248,215,218)),
    "retain":     (GREEN, (212,237,218)),
    "rehost":     ((0,64,133),(204,229,255)),
    "replatform": (AMBER, (255,243,205)),
    "refactor":   ((125,60,0),(253,232,216)),
    "replace":    (RED,   (248,215,218)),
    "retire":     (SLATE, (226,227,229)),
    "critical":   (WHITE, (192,57,43)),
    "high":       (RED,   (248,215,218)),
    "medium":     (AMBER, (255,243,205)),
    "low":        (GREEN, (212,237,218)),
    "approve":    (GREEN, (212,237,218)),
    "reject":     (RED,   (248,215,218)),
    "conditional":(AMBER, (255,243,205)),
    "tbd":        (SLATE, (226,227,229)),
}

TIME_DESC = {
    "INVEST":    "High strategic value -- continue and grow investment",
    "TOLERATE":  "Functional but not strategic -- maintain, no new investment",
    "MIGRATE":   "Move to a better platform, cloud, or replacement",
    "ELIMINATE": "Decommission -- retire or replace immediately",
}

ACTION_DESC = {
    "Retain":     "Strategic and healthy -- no immediate action required",
    "Rehost":     "Lift-and-shift to cloud infrastructure",
    "Replatform": "Minor modernisation leveraging cloud-native services",
    "Refactor":   "Significant redesign and re-architecture required",
    "Replace":    "Better market alternative exists -- plan migration",
    "Retire":     "Decommission -- low value, high cost, or redundant",
}


def _badge(key: str):
    k = key.lower().replace(" ", "-")
    return BADGE.get(k, BADGE["tbd"])


# ════════════════════════════════════════════════════════════════════════════
# EAPdf -- custom FPDF subclass
# ════════════════════════════════════════════════════════════════════════════

class EAPdf(FPDF):

    def header(self):
        pass  # handled manually

    def footer(self):
        self.set_y(-13)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*DGREY)
        self.set_draw_color(*MGREY)
        self.set_line_width(0.3)
        self.line(14, self.get_y() - 1, 196, self.get_y() - 1)
        self.cell(0, 8,
            f"EA AI Intelligence  |  Enterprise Architecture Advisory  |  CONFIDENTIAL  |  "
            f"{datetime.now().strftime('%d %B %Y')}  |  Page {self.page_no()}",
            align="C")

    # ── Cover page ────────────────────────────────────────────────────────────

    def cover_page(self, title: str, subtitle: str, meta_lines: list, stages: str = ""):
        self.set_fill_color(*NAVY)
        self.rect(0, 0, 210, 297, "F")

        # Blue accent bar top
        self.set_fill_color(*BLUE)
        self.rect(0, 0, 210, 6, "F")

        # Firm area (top-left)
        self.set_xy(14, 22)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*BLUE)
        self.cell(0, 6, "EA AI INTELLIGENCE", ln=True)
        self.set_x(14)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(140, 160, 200)
        self.cell(0, 5, "Enterprise Architecture Advisory Platform", ln=True)

        # Divider
        self.set_draw_color(*BLUE)
        self.set_line_width(0.4)
        self.line(14, 42, 196, 42)

        # Main title block
        self.set_xy(14, 90)
        self.set_font("Helvetica", "B", 26)
        self.set_text_color(*WHITE)
        self.multi_cell(182, 14, title, align="L")

        self.set_x(14)
        self.set_font("Helvetica", "", 12)
        self.set_text_color(160, 180, 220)
        self.multi_cell(182, 7, subtitle, align="L")

        # Blue accent line under title
        self.ln(6)
        self.set_draw_color(*BLUE)
        self.set_line_width(1.2)
        self.line(14, self.get_y(), 80, self.get_y())
        self.set_line_width(0.3)

        # Meta info block
        self.set_xy(14, 200)
        for line in meta_lines:
            self.set_font("Helvetica", "", 9)
            self.set_text_color(160, 180, 220)
            self.cell(0, 6, str(line), ln=True)
            self.set_x(14)

        if stages:
            self.set_xy(14, 240)
            self.set_font("Helvetica", "B", 8)
            self.set_text_color(*BLUE)
            self.cell(0, 5, "ANALYSIS STAGES COMPLETED", ln=True)
            self.set_x(14)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(160, 180, 220)
            self.cell(0, 5, stages, ln=True)

        # Confidential ribbon at bottom
        self.set_fill_color(*BLUE)
        self.rect(0, 278, 210, 19, "F")
        self.set_xy(0, 282)
        self.set_font("Helvetica", "B", 8)
        self.set_text_color(*WHITE)
        self.cell(210, 6, "STRICTLY CONFIDENTIAL  |  FOR ADDRESSEE ONLY  |  NOT FOR DISTRIBUTION", align="C")

    # ── Section title ─────────────────────────────────────────────────────────

    def section_title(self, num: str, text: str):
        if self.get_y() > 260:
            self.add_page()
        self.ln(6)
        # Left accent bar
        y = self.get_y()
        self.set_fill_color(*BLUE)
        self.rect(14, y, 2.5, 9, "F")
        self.set_xy(19, y)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*NAVY)
        self.cell(0, 9, f"{num}  {text}", ln=True)
        self.set_draw_color(*MGREY)
        self.set_line_width(0.3)
        self.line(14, self.get_y(), 196, self.get_y())
        self.ln(4)

    def sub_title(self, text: str):
        self.ln(3)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(*NAVY)
        self.set_x(14)
        self.cell(0, 6, text, ln=True)
        self.ln(1)

    # ── KPI row ───────────────────────────────────────────────────────────────

    def kpi_row(self, items: list):
        n = len(items)
        col_w = 182 / n
        x0 = 14
        y0 = self.get_y()
        for i, (val, lbl) in enumerate(items):
            x = x0 + i * col_w
            # card background
            self.set_fill_color(*LGREY)
            self.set_draw_color(*MGREY)
            self.set_line_width(0.3)
            self.rect(x, y0, col_w - 2, 26, "FD")
            # top accent
            self.set_fill_color(*BLUE)
            self.rect(x, y0, col_w - 2, 2, "F")
            # value
            self.set_xy(x, y0 + 5)
            self.set_font("Helvetica", "B", 15)
            self.set_text_color(*NAVY)
            self.cell(col_w - 2, 8, str(val), align="C")
            # label
            self.set_xy(x, y0 + 14)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(*DGREY)
            self.cell(col_w - 2, 5, str(lbl).upper(), align="C")
        self.set_y(y0 + 30)

    # ── Badge ─────────────────────────────────────────────────────────────────

    def badge(self, text: str, w: float = 0):
        fg, bg = _badge(text)
        if w == 0:
            w = self.get_string_width(str(text)) + 8
        self.set_fill_color(*bg)
        self.set_text_color(*fg)
        self.set_font("Helvetica", "B", 7)
        self.cell(w, 5, str(text).upper(), fill=True, align="C")
        self.set_text_color(*BLACK)

    # ── Table header ──────────────────────────────────────────────────────────

    def table_header(self, cols: list, widths: list):
        self.set_fill_color(*NAVY)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 8)
        self.set_x(14)
        for col, w in zip(cols, widths):
            self.cell(w, 8, str(col), border=0, fill=True)
        self.ln()
        self.set_text_color(*BLACK)

    def table_row(self, cells: list, widths: list, shade: bool = False):
        fill = LGREY if shade else WHITE
        self.set_fill_color(*fill)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*BLACK)
        if self.get_y() > 272:
            self.add_page()
        self.set_x(14)
        for cell, w in zip(cells, widths):
            self.cell(w, 6, str(cell)[:45], border=0, fill=True)
        self.ln()
        self.set_draw_color(*MGREY)
        self.line(14, self.get_y(), 196, self.get_y())

    # ── Executive summary box ─────────────────────────────────────────────────

    def exec_box(self, text: str, label: str = "EXECUTIVE SUMMARY"):
        if not text:
            return
        x, y = 14, self.get_y()
        # label tab
        self.set_fill_color(*NAVY)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 7)
        self.set_xy(x, y)
        self.cell(44, 5, f"  {label}", fill=True)
        self.ln(5)
        # body
        self.set_fill_color(*LGREY)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*BLACK)
        self.set_x(14)
        body_y = self.get_y()
        self.multi_cell(182, 5.5, str(text)[:2000], fill=True)
        box_h = self.get_y() - body_y
        # left accent
        self.set_fill_color(*BLUE)
        self.rect(14, body_y, 2, box_h, "F")
        self.ln(4)

    # ── Recommendation card ───────────────────────────────────────────────────

    def rec_card(self, rank: str, title: str, priority: str, effort: str,
                 timeline: str, desc: str, impact: str):
        if self.get_y() > 262:
            self.add_page()
        y = self.get_y()
        self.set_x(14)

        # Header row
        self.set_fill_color(*NAVY)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 8)
        self.cell(8, 7, str(rank), fill=True, align="C")
        self.set_fill_color(*LGREY)
        self.set_text_color(*NAVY)
        self.set_font("Helvetica", "B", 9)
        self.cell(122, 7, f"  {title[:70]}", fill=True)
        self.badge(priority, 22)
        self.set_fill_color(*LGREY)
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*DGREY)
        self.cell(28, 7, f"  {effort} effort", fill=True)
        self.ln()

        # Meta row
        self.set_x(22)
        self.set_fill_color(240, 244, 252)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*DGREY)
        self.cell(174, 5, f"  Timeline: {timeline}", fill=True)
        self.ln()

        # Description
        self.set_x(22)
        self.set_fill_color(*LGREY)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*BLACK)
        self.multi_cell(174, 5, str(desc)[:400], fill=True)

        # Impact
        if impact:
            self.set_x(22)
            self.set_fill_color(*LGREY)
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(*BLUE)
            self.multi_cell(174, 4.5, f"Impact: {str(impact)[:200]}", fill=True)

        # Bottom border
        card_h = self.get_y() - y
        self.set_draw_color(*MGREY)
        self.set_line_width(0.3)
        self.rect(14, y, 182, card_h)
        self.set_fill_color(*BLUE)
        self.rect(14, y, 2, card_h, "F")
        self.ln(3)

    # ── Roadmap ───────────────────────────────────────────────────────────────

    def roadmap_section(self, roadmap: dict):
        if not roadmap:
            return
        phases = [
            ("PHASE 1  |  0-6 MONTHS    Foundation",      roadmap.get("short_term", []),  TEAL),
            ("PHASE 2  |  6-18 MONTHS   Execution",       roadmap.get("medium_term", []), BLUE),
            ("PHASE 3  |  18-24 MONTHS  Optimisation",    roadmap.get("long_term", []),   (114,28,100)),
        ]
        col_w = 59
        y0 = self.get_y()
        for i, (label, items, colour) in enumerate(phases):
            if not items:
                continue
            if isinstance(items, str):
                items = [items]
            x = 14 + i * (col_w + 2)
            # header
            self.set_fill_color(*colour)
            self.set_text_color(*WHITE)
            self.set_font("Helvetica", "B", 7)
            self.set_xy(x, y0)
            self.cell(col_w, 8, label[:40], fill=True, align="C")
            # items
            cy = y0 + 9
            self.set_fill_color(*LGREY)
            self.set_text_color(*BLACK)
            for item in items[:6]:
                self.set_font("Helvetica", "", 7.5)
                self.set_xy(x, cy)
                self.multi_cell(col_w, 4.5, f"- {str(item)[:60]}", fill=True)
                cy = self.get_y()
        self.set_y(max(self.get_y(), y0 + 60))
        self.ln(4)


# ════════════════════════════════════════════════════════════════════════════
# ReportGenerator
# ════════════════════════════════════════════════════════════════════════════

class ReportGenerator:

    def generate(self, tools, duplications, assessments,
                 report_type="full", output_dir="reports", fmt="pdf") -> str:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if fmt == "html":
            path = Path(output_dir) / f"ea_portfolio_report_{ts}.html"
            path.write_text(self._build_html(tools, duplications, assessments), encoding="utf-8")
        else:
            path = Path(output_dir) / f"ea_portfolio_report_{ts}.pdf"
            self._write_pdf(tools, duplications, assessments, str(path))
        return str(path)

    # ── Portfolio-only PDF ────────────────────────────────────────────────────

    def _write_pdf(self, tools, duplications, assessments, dest):
        tools        = _deep_sanitize(tools)
        duplications = _deep_sanitize(duplications)
        assessments  = _deep_sanitize(assessments)
        pdf = EAPdf()
        pdf.set_margins(14, 14, 14)
        pdf.set_auto_page_break(True, margin=18)

        gen_date = datetime.now().strftime("%d %B %Y  %H:%M")
        total_cost  = sum(t.get("annual_cost", 0) or 0 for t in tools)
        pot_savings = sum(d.get("potential_annual_savings", 0) or 0 for d in duplications)

        # Cover
        pdf.add_page()
        pdf.cover_page(
            "Portfolio Rationalization\nReport",
            "Enterprise Architecture  |  Application Portfolio Assessment  |  AI-Powered Advisory",
            [
                f"Date of Issue:  {gen_date}",
                f"Scope:          {len(tools)} Applications Assessed",
                f"Framework:      TIME + 6R Rationalization Model",
                f"Classification: CONFIDENTIAL",
            ],
        )

        # Executive Summary
        pdf.add_page()
        assessment = assessments[-1] if assessments else {}
        exec_sum = assessment.get("executive_summary", "")

        pdf.section_title("1.", "Executive Summary")
        if exec_sum:
            pdf.exec_box(exec_sum)

        # KPIs
        pdf.section_title("2.", "Portfolio Overview")
        pdf.kpi_row([
            (str(len(tools)),          "Applications Assessed"),
            (f"${total_cost:,.0f}",    "Total Annual Spend"),
            (str(len(duplications)),   "Overlap Pairs"),
            (f"${pot_savings:,.0f}",   "Est. Annual Savings"),
        ])

        # TIME + 6R breakdown
        action_counts: Dict[str, int] = {}
        time_counts:   Dict[str, int] = {}
        for t in tools:
            a  = t.get("rationalization_action", "TBD")
            action_counts[a] = action_counts.get(a, 0) + 1
            tc = t.get("time_classification", "TOLERATE")
            time_counts[tc]  = time_counts.get(tc, 0) + 1

        pdf.sub_title("TIME Classification Breakdown")
        self._pdf_time_table(pdf, time_counts, len(tools))

        pdf.sub_title("6R Action Breakdown")
        self._pdf_action_table(pdf, action_counts, len(tools))

        # Recommendations
        recs = assessment.get("top_recommendations", [])
        if recs:
            pdf.section_title("3.", "Strategic Recommendations")
            for r in recs[:5]:
                pdf.rec_card(
                    str(r.get("rank", "-")),
                    r.get("title", ""),
                    r.get("priority", "Medium"),
                    r.get("effort", "-"),
                    r.get("timeline", "-"),
                    r.get("description", ""),
                    r.get("impact", ""),
                )

        # Roadmap
        roadmap = assessment.get("roadmap", {})
        if roadmap:
            pdf.section_title("4.", "Transformation Roadmap")
            pdf.roadmap_section(roadmap)

        # Application detail
        pdf.section_title("5.", "Application Portfolio Detail")
        self._pdf_tool_table(pdf, tools)

        # Duplications
        if duplications:
            pdf.section_title("6.", "Duplication & Consolidation Opportunities")
            self._pdf_dup_table(pdf, duplications)

        # Outcomes
        outcomes = assessment.get("expected_outcomes", {})
        if outcomes:
            pdf.section_title("7.", "Expected Business Outcomes")
            pdf.table_header(["Outcome", "Detail"], [70, 112])
            for i, (k, v) in enumerate(outcomes.items()):
                pdf.table_row([k.replace("_", " ").title(), str(v)], [70, 112], shade=i%2==0)

        # Methodology appendix
        pdf.add_page()
        self._pdf_methodology(pdf)

        pdf.output(dest)

    # ── Full pipeline PDF ─────────────────────────────────────────────────────

    def generate_pipeline_pdf(self, pipeline: Dict, output_dir: str = "reports") -> str:
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        pipeline = _deep_sanitize(pipeline)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path(output_dir) / f"ea_full_intelligence_report_{ts}.pdf"

        pdf = EAPdf()
        pdf.set_margins(14, 14, 14)
        pdf.set_auto_page_break(True, margin=18)

        gen_date      = datetime.now().strftime("%d %B %Y  %H:%M")
        summary       = pipeline.get("pipeline_summary", {})
        time_data     = pipeline.get("TIME", {})
        mapping_data  = pipeline.get("MAPPING", {})
        maturity_data = pipeline.get("MATURITY", {})
        insights_data = pipeline.get("INSIGHTS", {})

        apps          = time_data.get("applications", [])
        dups          = time_data.get("duplications", [])
        time_summary  = time_data.get("portfolio_summary", {})
        time_assess   = time_data.get("assessment", {})

        total_cost    = time_summary.get("total_annual_cost", 0)
        pot_savings   = time_summary.get("potential_savings", 0)
        mat_score     = maturity_data.get("overall_maturity_score", "-")
        overall_risk  = insights_data.get("risk_profile", {}).get("overall_risk", "-")
        stages        = "  >  ".join(summary.get("stages_completed", []))

        # ── Cover ────────────────────────────────────────────────────────────
        pdf.add_page()
        pdf.cover_page(
            "Full Enterprise Architecture\nIntelligence Report",
            "Portfolio Rationalization  |  Dependency Analysis  |  Maturity Assessment  |  Executive Intelligence",
            [
                f"Date of Issue:      {gen_date}",
                f"Applications:       {len(apps)} assessed",
                f"Annual Portfolio:   ${total_cost:,.0f}",
                f"Potential Savings:  ${pot_savings:,.0f}",
                f"EA Maturity Score:  {mat_score} / 5",
                f"Overall Risk:       {overall_risk}",
                f"Classification:     CONFIDENTIAL",
            ],
            stages=stages,
        )

        # ── Section 1 -- Executive Intelligence Summary ────────────────────────
        pdf.add_page()
        ins_exec = insights_data.get("executive_summary", "")
        time_exec = time_assess.get("executive_summary", "")
        pdf.section_title("1.", "Executive Intelligence Summary")
        if ins_exec:
            pdf.exec_box(ins_exec, label="INSIGHTS -- EXECUTIVE SUMMARY")
        elif time_exec:
            pdf.exec_box(time_exec, label="PORTFOLIO -- EXECUTIVE SUMMARY")

        # KPI overview
        pdf.kpi_row([
            (str(len(apps)),                                 "Apps Assessed"),
            (f"${total_cost:,.0f}",                         "Annual Portfolio Spend"),
            (f"${pot_savings:,.0f}",                        "Potential Annual Savings"),
            (str(summary.get("flagged_for_action", 0)),     "Apps Flagged for Action"),
            (f"{mat_score}/5",                              "EA Maturity Score"),
            (str(overall_risk),                             "Overall Risk Level"),
        ])

        # Financial impact
        fin = insights_data.get("financial_impact", {})
        if fin:
            pdf.sub_title("Financial Impact Analysis")
            pdf.table_header(["Metric", "Value"], [80, 102])
            for i, (k, v) in enumerate(fin.items()):
                if v:
                    pdf.table_row([k.replace("_", " ").title(), str(v)], [80, 102], shade=i%2==0)

        # ── Section 2 -- Portfolio Rationalization (TIME) ──────────────────────
        pdf.section_title("2.", "Portfolio Rationalization -- TIME Analysis")
        if time_exec:
            pdf.exec_box(time_exec, label="TIME AGENT -- EXECUTIVE SUMMARY")

        action_counts: Dict[str, int] = {}
        time_counts:   Dict[str, int] = {}
        for t in apps:
            a  = t.get("rationalization_action", "TBD")
            action_counts[a] = action_counts.get(a, 0) + 1
            tc = t.get("time_classification", "TOLERATE")
            time_counts[tc]  = time_counts.get(tc, 0) + 1

        pdf.sub_title("TIME Classification Breakdown")
        self._pdf_time_table(pdf, time_counts, len(apps))

        pdf.sub_title("6R Action Breakdown")
        self._pdf_action_table(pdf, action_counts, len(apps))

        pdf.sub_title("Application Portfolio Detail")
        self._pdf_tool_table_compact(pdf, apps)

        if dups:
            pdf.sub_title("Duplication & Consolidation Opportunities")
            self._pdf_dup_table(pdf, dups)

        roadmap_t = time_assess.get("roadmap", {})
        if roadmap_t:
            pdf.sub_title("Portfolio Transformation Roadmap")
            pdf.roadmap_section(roadmap_t)

        # ── Section 3 -- Dependency Analysis (MAPPING) ────────────────────────
        pdf.section_title("3.", "Dependency & Impact Analysis -- MAPPING")
        self._pdf_mapping_section(pdf, mapping_data)

        # ── Section 4 -- EA Maturity Assessment ───────────────────────────────
        pdf.section_title("4.", "EA Maturity Assessment -- MATURITY")
        self._pdf_maturity_section(pdf, maturity_data)

        # ── Section 5 -- Strategic Recommendations (INSIGHTS) ─────────────────
        pdf.section_title("5.", "Strategic Recommendations -- INSIGHTS")
        self._pdf_insights_recs(pdf, insights_data)

        # Risk profile
        risks = insights_data.get("risk_profile", {}).get("top_risks", [])
        if risks:
            pdf.sub_title("Risk Register")
            pdf.table_header(["Risk", "Impact", "Mitigation"], [54, 54, 74])
            for i, r in enumerate(risks[:5]):
                pdf.table_row(
                    [r.get("risk","")[:32], r.get("impact","")[:32], r.get("mitigation","")[:44]],
                    [54, 54, 74], shade=i%2==0)

        # KPIs
        kpis = insights_data.get("kpis", [])
        if kpis:
            pdf.sub_title("Key Performance Indicators")
            pdf.table_header(["KPI", "Current", "Target", "Timeframe"], [62, 36, 36, 48])
            for i, k in enumerate(kpis[:6]):
                pdf.table_row(
                    [k.get("metric","")[:36], str(k.get("current",""))[:18],
                     str(k.get("target",""))[:18], str(k.get("timeframe",""))[:26]],
                    [62, 36, 36, 48], shade=i%2==0)

        # Expected outcomes
        outcomes = time_assess.get("expected_outcomes", {})
        if outcomes:
            pdf.sub_title("Expected Business Outcomes")
            pdf.table_header(["Outcome", "Detail"], [70, 112])
            for i, (k, v) in enumerate(outcomes.items()):
                pdf.table_row([k.replace("_"," ").title(), str(v)], [70, 112], shade=i%2==0)

        # ── Appendix -- Methodology ────────────────────────────────────────────
        pdf.add_page()
        self._pdf_methodology(pdf)

        pdf.output(str(path))
        return str(path)

    # ── Shared section helpers ────────────────────────────────────────────────

    def _pdf_time_table(self, pdf, counts, total):
        pdf.table_header(["TIME Classification", "Count", "% Portfolio", "Strategic Meaning"], [38, 16, 20, 108])
        for i, cat in enumerate(["INVEST", "TOLERATE", "MIGRATE", "ELIMINATE"]):
            c = counts.get(cat, 0)
            if c == 0:
                continue
            pct = round(c / max(total, 1) * 100)
            pdf.set_x(14)
            pdf.set_fill_color(*(LGREY if i%2==0 else WHITE))
            pdf.badge(cat, 36)
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(16, 6, str(c), fill=False)
            pdf.cell(20, 6, f"{pct}%", fill=False)
            pdf.cell(108, 6, TIME_DESC.get(cat, "")[:70], fill=False)
            pdf.ln()
            pdf.set_draw_color(*MGREY)
            pdf.line(14, pdf.get_y(), 196, pdf.get_y())

    def _pdf_action_table(self, pdf, counts, total):
        pdf.table_header(["6R Action", "Count", "% Portfolio", "Description"], [30, 16, 20, 116])
        for i, action in enumerate(["Retain","Rehost","Replatform","Refactor","Replace","Retire"]):
            c = counts.get(action, 0)
            if c == 0:
                continue
            pct = round(c / max(total, 1) * 100)
            pdf.set_x(14)
            pdf.badge(action, 28)
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(18, 6, str(c))
            pdf.cell(20, 6, f"{pct}%")
            pdf.cell(116, 6, ACTION_DESC.get(action, "")[:72])
            pdf.ln()
            pdf.set_draw_color(*MGREY)
            pdf.line(14, pdf.get_y(), 196, pdf.get_y())

    def _pdf_tool_table(self, pdf, tools):
        cols   = ["Application", "Vendor", "Category", "Annual Cost", "Users", "Score", "TIME", "6R Action", "Confidence"]
        widths = [34, 22, 20, 20, 12, 12, 20, 22, 20]
        pdf.table_header(cols, widths)
        for i, t in enumerate(tools):
            if pdf.get_y() > 268:
                pdf.add_page(); pdf.table_header(cols, widths)
            cost  = f"${t.get('annual_cost',0):,.0f}" if t.get("annual_cost") else "-"
            score = t.get("composite_score", "-")
            tc    = t.get("time_classification", "TOLERATE")
            act   = t.get("rationalization_action", "TBD")
            conf  = t.get("confidence_level", "Low")
            fill  = LGREY if i%2==0 else WHITE
            pdf.set_fill_color(*fill)
            pdf.set_x(14)
            pdf.set_font("Helvetica", "B", 7)
            pdf.cell(34, 6, (t.get("name") or "-")[:22], fill=True)
            pdf.set_font("Helvetica", "", 7)
            pdf.cell(22, 6, (t.get("vendor") or "-")[:14], fill=True)
            pdf.cell(20, 6, (t.get("category") or "-")[:13], fill=True)
            pdf.cell(20, 6, cost, fill=True)
            pdf.cell(12, 6, str(t.get("user_count") or "-"), fill=True)
            pdf.cell(12, 6, f"{score}/10", fill=True)
            pdf.badge(tc, 20); pdf.badge(act, 22); pdf.badge(conf, 20)
            pdf.ln()
            pdf.set_draw_color(*MGREY); pdf.line(14, pdf.get_y(), 196, pdf.get_y())

    def _pdf_tool_table_compact(self, pdf, tools):
        cols   = ["Application", "Category", "Annual Cost", "Users", "Score", "TIME", "6R Action"]
        widths = [42, 26, 22, 14, 14, 26, 26]
        pdf.table_header(cols, widths)
        for i, t in enumerate(tools):
            if pdf.get_y() > 268:
                pdf.add_page(); pdf.table_header(cols, widths)
            cost = f"${t.get('annual_cost',0):,.0f}" if t.get("annual_cost") else "-"
            fill = LGREY if i%2==0 else WHITE
            pdf.set_fill_color(*fill)
            pdf.set_x(14)
            pdf.set_font("Helvetica", "B", 7)
            pdf.cell(42, 6, (t.get("name") or "-")[:26], fill=True)
            pdf.set_font("Helvetica", "", 7)
            pdf.cell(26, 6, (t.get("category") or "-")[:16], fill=True)
            pdf.cell(22, 6, cost, fill=True)
            pdf.cell(14, 6, str(t.get("user_count") or "-"), fill=True)
            pdf.cell(14, 6, f"{t.get('composite_score','-')}/10", fill=True)
            pdf.badge(t.get("time_classification","TOLERATE"), 26)
            pdf.badge(t.get("rationalization_action","TBD"), 26)
            pdf.ln()
            pdf.set_draw_color(*MGREY); pdf.line(14, pdf.get_y(), 196, pdf.get_y())

    def _pdf_dup_table(self, pdf, dups):
        cols   = ["Category", "Tool A", "Tool B", "Overlap", "Recommend Retain", "Est. Savings", "Priority"]
        widths = [22, 28, 28, 14, 38, 26, 18]
        pdf.table_header(cols, widths)
        for i, d in enumerate(dups[:15]):
            savings = f"${d.get('potential_annual_savings',0):,.0f}"
            prio    = d.get("priority", "Low")
            fill    = LGREY if i%2==0 else WHITE
            pdf.set_fill_color(*fill)
            pdf.set_x(14)
            pdf.set_font("Helvetica", "", 7)
            pdf.cell(22, 6, (d.get("category") or "-")[:13], fill=True)
            pdf.cell(28, 6, (d.get("tool_a") or "-")[:16], fill=True)
            pdf.cell(28, 6, (d.get("tool_b") or "-")[:16], fill=True)
            pdf.cell(14, 6, f"{d.get('overlap_percentage',0)}%", fill=True)
            pdf.cell(38, 6, (d.get("retain_candidate") or "-")[:22], fill=True)
            pdf.cell(26, 6, savings, fill=True)
            pdf.badge(prio, 18)
            pdf.ln()
            pdf.set_draw_color(*MGREY); pdf.line(14, pdf.get_y(), 196, pdf.get_y())

    def _pdf_mapping_section(self, pdf, mapping):
        if not mapping or mapping.get("skipped"):
            reason = mapping.get("reason", "No apps flagged for ELIMINATE or MIGRATE.")
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*DGREY)
            pdf.set_x(14)
            pdf.multi_cell(182, 5, reason)
            return

        overall = mapping.get("overall_impact_level", "-")
        pdf.set_x(14)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*NAVY)
        pdf.cell(0, 6, f"Overall Portfolio Impact Level: {overall}", ln=True)
        pdf.ln(2)

        ctx = mapping.get("pipeline_context", "")
        if ctx:
            pdf.exec_box(ctx, label="MAPPING CONTEXT")

        app_analyses = mapping.get("app_analyses", [])
        if app_analyses:
            pdf.sub_title("Per-Application Dependency Analysis")
            pdf.table_header(["Application","TIME","Impact Level","Coupling","Direct Dependencies"],
                             [40, 24, 22, 18, 78])
            for i, a in enumerate(app_analyses):
                deps = ", ".join((a.get("direct_dependencies") or [])[:3])
                if pdf.get_y() > 268:
                    pdf.add_page()
                fill = LGREY if i%2==0 else WHITE
                pdf.set_fill_color(*fill)
                pdf.set_x(14)
                pdf.set_font("Helvetica", "B", 7)
                pdf.cell(40, 6, (a.get("app_name") or "-")[:24], fill=True)
                pdf.badge(a.get("time_classification","-"), 24)
                pdf.badge(a.get("impact_level","-"), 22)
                pdf.set_font("Helvetica", "", 7)
                pdf.cell(18, 6, f"{a.get('coupling_score','-')}/10", fill=True)
                pdf.cell(78, 6, deps[:48], fill=True)
                pdf.ln()
                pdf.set_draw_color(*MGREY); pdf.line(14, pdf.get_y(), 196, pdf.get_y())

        order = mapping.get("recommended_migration_order", [])
        if order:
            pdf.sub_title("Recommended Migration Sequence")
            for i, app in enumerate(order):
                pdf.set_x(14)
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*BLACK)
                pdf.cell(10, 5, f"{i+1}.")
                pdf.cell(0, 5, str(app)[:100], ln=True)

    def _pdf_maturity_section(self, pdf, maturity):
        if not maturity:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*DGREY)
            pdf.set_x(14)
            pdf.cell(0, 6, "Maturity assessment not available.", ln=True)
            return

        score = maturity.get("overall_maturity_score", "-")
        level = maturity.get("maturity_level", "-")

        # Score banner
        pdf.set_fill_color(*NAVY)
        pdf.set_x(14)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(*WHITE)
        pdf.cell(60, 10, f"  Overall Score: {score} / 5", fill=True)
        pdf.set_fill_color(*BLUE)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(50, 10, f"  {level}", fill=True)
        pdf.ln(14)

        dims = maturity.get("dimensions", {})
        if dims:
            pdf.sub_title("Dimension Scores")
            pdf.table_header(["Dimension", "Score", "Key Gaps"], [58, 18, 106])
            for i, (dk, dv) in enumerate(dims.items()):
                if not isinstance(dv, dict):
                    continue
                gaps = ", ".join(dv.get("gaps", [])[:2]) or "-"
                pdf.table_row(
                    [dk.replace("_"," ").title(), f"{dv.get('score','-')}/5", gaps[:64]],
                    [58, 18, 106], shade=i%2==0)

        priorities = maturity.get("top_priorities", [])
        if priorities:
            pdf.sub_title("Top Improvement Priorities")
            for p in priorities[:5]:
                pdf.set_x(18)
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*BLACK)
                pdf.cell(4, 5, "-")
                pdf.multi_cell(174, 5, str(p)[:110])

        roadmap = maturity.get("roadmap", [])
        if roadmap:
            pdf.sub_title("Maturity Improvement Roadmap")
            pdf.table_header(["Phase", "Key Actions"], [54, 128])
            for i, phase in enumerate(roadmap[:3]):
                acts = "; ".join(phase.get("actions", [])[:3]) if isinstance(phase, dict) else str(phase)
                pdf.table_row(
                    [phase.get("phase","")[:30] if isinstance(phase,dict) else f"Phase {i+1}", acts[:76]],
                    [54, 128], shade=i%2==0)

    def _pdf_insights_recs(self, pdf, insights):
        if not insights:
            return
        recs = insights.get("strategic_recommendations", [])
        for r in recs[:6]:
            pdf.rec_card(
                rank=str(r.get("priority","-")),
                title=str(r.get("recommendation",""))[:80],
                priority=str(r.get("effort","Medium")),
                effort=str(r.get("effort","-")),
                timeline=str(r.get("timeline","-")),
                desc=str(r.get("business_value",""))[:400],
                impact="",
            )
        quick_wins = insights.get("quick_wins", [])
        if quick_wins:
            pdf.sub_title("Quick Wins")
            for w in quick_wins[:5]:
                pdf.set_x(18)
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*BLACK)
                pdf.cell(4, 5, "-")
                pdf.multi_cell(174, 5, str(w)[:110])

    def _pdf_methodology(self, pdf):
        pdf.section_title("A.", "Appendix -- Methodology & Scoring Framework")

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*NAVY)
        pdf.set_x(14)
        pdf.cell(0, 6, "TIME Framework", ln=True)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*BLACK)
        pdf.set_x(14)
        pdf.multi_cell(182, 5,
            "Tolerate: Application is functional but not strategic -- maintain without new investment.\n"
            "Invest: High business value and strategic alignment -- continue and grow.\n"
            "Migrate: Move to a better platform, cloud service, or modern replacement.\n"
            "Eliminate: Decommission -- application is redundant, end-of-life, or low value.")
        pdf.ln(3)

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*NAVY)
        pdf.set_x(14)
        pdf.cell(0, 6, "Scoring Engine -- 7 Dimensions", ln=True)
        dims_info = [
            ("Business Value",    "Category importance multiplied by criticality modifier."),
            ("Adoption Rate",     "User count mapped to a 0-10 utilisation score."),
            ("Integration Depth", "Number of integrations; highly integrated apps score higher."),
            ("Vendor Support",    "Tier-1 vendor recognition and end-of-life status."),
            ("Cost Efficiency",   "Annual cost divided by user count (cost per user)."),
            ("Technical Health",  "Application age in years; penalised for end-of-life flag."),
            ("Risk Score",        "Composite of EOL status, compliance requirements, age, and integrations."),
        ]
        pdf.table_header(["Dimension", "Description"], [50, 132])
        for i, (d, desc) in enumerate(dims_info):
            pdf.table_row([d, desc], [50, 132], shade=i%2==0)
        pdf.ln(4)

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*NAVY)
        pdf.set_x(14)
        pdf.cell(0, 6, "6R Cloud Migration Model", ln=True)
        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(*BLACK)
        pdf.set_x(14)
        pdf.multi_cell(182, 5,
            "Retain: No change required -- application is strategic and healthy.\n"
            "Rehost: Lift-and-shift to cloud infrastructure with minimal code changes.\n"
            "Replatform: Targeted optimisations to leverage managed cloud services.\n"
            "Refactor: Significant redesign to cloud-native architecture.\n"
            "Replace: Retire current application and adopt a SaaS or market alternative.\n"
            "Retire: Decommission with no replacement required.")

    # ── HTML builder (for fmt='html') ─────────────────────────────────────────

    def _build_html(self, tools, duplications, assessments):
        total_cost  = sum(t.get("annual_cost", 0) or 0 for t in tools)
        pot_savings = sum(d.get("potential_annual_savings", 0) or 0 for d in duplications)
        gen_date    = datetime.now().strftime("%d %B %Y  %H:%M")

        action_counts: Dict[str, int] = {}
        time_counts:   Dict[str, int] = {}
        for t in tools:
            a  = t.get("rationalization_action", "TBD")
            action_counts[a] = action_counts.get(a, 0) + 1
            tc = t.get("time_classification", "TOLERATE")
            time_counts[tc]  = time_counts.get(tc, 0) + 1

        assessment        = assessments[-1] if assessments else {}
        assessment_section = self._assessment_section([assessment] if assessment else [])
        tool_rows         = self._tool_rows(tools)
        dup_rows          = self._dup_rows(duplications)
        action_rows       = self._action_summary_rows(action_counts)
        time_rows         = self._time_summary_rows(time_counts)

        return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<title>EA Portfolio Rationalization Report</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',Arial,sans-serif;background:#f0f4fa;color:#1a2340;font-size:14px}}
.report{{max-width:1340px;margin:0 auto;background:#fff;box-shadow:0 0 40px rgba(0,0,0,.1)}}
.cover{{background:#0a1628;color:#fff;padding:60px 40px;border-top:6px solid #0063DC}}
.cover h1{{font-size:30px;font-weight:700;line-height:1.3}}
.cover .sub{{opacity:.7;font-size:13px;margin-top:8px}}
.cover .meta{{font-size:12px;opacity:.55;margin-top:16px;line-height:1.8}}
.kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#e0e7f0}}
.kpi{{background:#fff;padding:28px 20px;text-align:center;border-top:3px solid #0063DC}}
.kpi .val{{font-size:32px;font-weight:700;color:#0a1628}}
.kpi .lbl{{font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.8px;margin-top:6px}}
.section{{padding:40px;border-bottom:1px solid #eef1f8}}
h2{{font-size:18px;font-weight:700;color:#0a1628;margin-bottom:20px;padding-bottom:12px;border-bottom:2px solid #0063DC;display:flex;align-items:center;gap:8px}}
h2 .num{{background:#0a1628;color:#fff;width:28px;height:28px;border-radius:4px;display:inline-flex;align-items:center;justify-content:center;font-size:13px}}
.two-col{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}
table{{width:100%;border-collapse:collapse;font-size:13px}}
thead th{{background:#0a1628;color:#fff;padding:12px 14px;text-align:left;font-weight:600;font-size:12px;letter-spacing:.3px}}
tbody td{{padding:10px 14px;border-bottom:1px solid #f0f3fa}}
tbody tr:nth-child(even){{background:#f8fbff}}
.badge{{display:inline-block;padding:3px 10px;border-radius:3px;font-size:11px;font-weight:700;letter-spacing:.3px}}
.badge-retain,.badge-invest{{color:#155724;background:#d4edda}}
.badge-rehost,.badge-tolerate{{color:#004085;background:#cce5ff}}
.badge-replatform,.badge-migrate{{color:#856404;background:#fff3cd}}
.badge-refactor{{color:#7d3c00;background:#fde8d8}}
.badge-replace,.badge-eliminate{{color:#721c24;background:#f8d7da}}
.badge-retire{{color:#383d41;background:#e2e3e5}}
.badge-high{{color:#721c24;background:#f8d7da}}
.badge-medium{{color:#856404;background:#fff3cd}}
.badge-low{{color:#155724;background:#d4edda}}
.exec-box{{background:#f8fbff;border-left:4px solid #0063DC;padding:24px 28px;line-height:1.8;white-space:pre-wrap;font-size:13px}}
.rec-card{{border:1px solid #dde4f0;border-left:4px solid #0063DC;padding:20px;margin-bottom:12px;background:#f8fbff}}
.rec-card h4{{color:#0a1628;font-size:14px;margin-bottom:6px}}
.footer{{background:#0a1628;color:#8899bb;padding:20px 40px;font-size:12px;text-align:center}}
</style></head><body>
<div class="report">
<div class="cover">
  <h1>EA AI Intelligence<br>Portfolio Rationalization Report</h1>
  <div class="sub">Enterprise Architecture  |  Application Portfolio Assessment  |  AI-Powered Advisory</div>
  <div class="meta">Date of Issue: {gen_date}<br>Applications Assessed: {len(tools)}<br>Framework: TIME + 6R Rationalization Model<br>Classification: CONFIDENTIAL</div>
</div>
<div class="kpi-grid">
  <div class="kpi"><div class="val">{len(tools)}</div><div class="lbl">Applications Assessed</div></div>
  <div class="kpi"><div class="val">${total_cost:,.0f}</div><div class="lbl">Total Annual Spend</div></div>
  <div class="kpi"><div class="val">{len(duplications)}</div><div class="lbl">Overlap Pairs Found</div></div>
  <div class="kpi"><div class="val">${pot_savings:,.0f}</div><div class="lbl">Est. Annual Savings</div></div>
</div>
{assessment_section}
<div class="section">
  <h2><span class="num">2</span> Portfolio Classification Summary</h2>
  <div class="two-col">
    <table><thead><tr><th>TIME</th><th>Count</th><th>Portfolio %</th><th>Strategic Meaning</th></tr></thead><tbody>{time_rows}</tbody></table>
    <table><thead><tr><th>6R Action</th><th>Count</th><th>Portfolio %</th><th>Description</th></tr></thead><tbody>{action_rows}</tbody></table>
  </div>
</div>
<div class="section">
  <h2><span class="num">3</span> Application Portfolio Detail</h2>
  <table><thead><tr><th>Application</th><th>Vendor</th><th>Category</th><th>Annual Cost</th><th>Users</th><th>Score</th><th>TIME</th><th>6R Action</th></tr></thead><tbody>{tool_rows}</tbody></table>
</div>
{self._dup_section(dup_rows) if duplications else ""}
<div class="footer">EA AI Intelligence  |  CONFIDENTIAL  |  {datetime.now().strftime('%Y')}</div>
</div></body></html>"""

    def _assessment_section(self, assessments):
        if not assessments:
            return ""
        latest = assessments[-1]
        parts  = []
        exec_sum = latest.get("executive_summary", "")
        if exec_sum:
            parts.append(f'<div class="section"><h2><span class="num">1</span> Executive Summary</h2><div class="exec-box">{exec_sum}</div></div>')
        recs = latest.get("top_recommendations", [])
        if recs:
            cards = ""
            for r in recs[:5]:
                prio = r.get("priority","Medium")
                cards += (f'<div class="rec-card"><h4>#{r.get("rank","")} {r.get("title","")}'
                          f' <span class="badge badge-{prio.lower()}">{prio}</span></h4>'
                          f'<p style="color:#444;margin:8px 0">{r.get("description","")}</p>'
                          f'<p style="color:#0063DC;font-size:12px">Impact: {r.get("impact","")} &nbsp;|&nbsp; Timeline: {r.get("timeline","")}</p></div>')
            parts.append(f'<div class="section"><h2>Strategic Recommendations</h2>{cards}</div>')
        roadmap = latest.get("roadmap", {})
        if roadmap:
            def pi(key):
                items = roadmap.get(key, [])
                if isinstance(items, str): items = [items]
                return "".join(f"<li style='margin-bottom:4px'>{i}</li>" for i in items)
            parts.append(
                f'<div class="section"><h2>Transformation Roadmap</h2>'
                f'<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px">'
                f'<div style="border-top:4px solid #00A651;padding:16px;background:#f8fbff"><strong>Phase 1 -- 0–6 Months</strong><br><small style="color:#666">Foundation &amp; Quick Wins</small><ul style="margin-top:10px;padding-left:18px;font-size:13px">{pi("short_term")}</ul></div>'
                f'<div style="border-top:4px solid #0063DC;padding:16px;background:#f8fbff"><strong>Phase 2 -- 6–18 Months</strong><br><small style="color:#666">Execution &amp; Migration</small><ul style="margin-top:10px;padding-left:18px;font-size:13px">{pi("medium_term")}</ul></div>'
                f'<div style="border-top:4px solid #7B2FBE;padding:16px;background:#f8fbff"><strong>Phase 3 -- 18–24 Months</strong><br><small style="color:#666">Optimisation &amp; Embedding</small><ul style="margin-top:10px;padding-left:18px;font-size:13px">{pi("long_term")}</ul></div>'
                f'</div></div>')
        return "\n".join(parts)

    def _time_summary_rows(self, counts):
        total = max(sum(counts.values()), 1)
        rows  = ""
        for cat in ["INVEST","TOLERATE","MIGRATE","ELIMINATE"]:
            c = counts.get(cat, 0)
            if c == 0: continue
            rows += (f'<tr><td><span class="badge badge-{cat.lower()}">{cat}</span></td>'
                     f'<td><strong>{c}</strong></td><td>{round(c/total*100)}%</td>'
                     f'<td>{TIME_DESC.get(cat,"")}</td></tr>')
        return rows

    def _action_summary_rows(self, counts):
        total = max(sum(counts.values()), 1)
        rows  = ""
        for a in ["Retain","Rehost","Replatform","Refactor","Replace","Retire"]:
            c = counts.get(a, 0)
            if c == 0: continue
            rows += (f'<tr><td><span class="badge badge-{a.lower()}">{a}</span></td>'
                     f'<td><strong>{c}</strong></td><td>{round(c/total*100)}%</td>'
                     f'<td>{ACTION_DESC.get(a,"")}</td></tr>')
        return rows

    def _tool_rows(self, tools):
        rows = ""
        for t in tools:
            act  = t.get("rationalization_action","TBD")
            tc   = t.get("time_classification","TOLERATE")
            cost = f"${t.get('annual_cost',0):,.0f}" if t.get("annual_cost") else "-"
            rows += (f'<tr><td><strong>{t.get("name","-")}</strong></td>'
                     f'<td>{t.get("vendor") or "-"}</td><td>{t.get("category","-")}</td>'
                     f'<td>{cost}</td><td>{t.get("user_count","-")}</td>'
                     f'<td><strong>{t.get("composite_score","-")}</strong>/10</td>'
                     f'<td><span class="badge badge-{tc.lower()}">{tc}</span></td>'
                     f'<td><span class="badge badge-{act.lower()}">{act}</span></td></tr>')
        return rows

    def _dup_rows(self, duplications):
        rows = ""
        for d in duplications[:15]:
            prio = d.get("priority","Low")
            rows += (f'<tr><td>{d.get("category","-")}</td><td>{d.get("tool_a","-")}</td>'
                     f'<td>{d.get("tool_b","-")}</td><td><strong>{d.get("overlap_percentage",0)}%</strong></td>'
                     f'<td><strong>{d.get("retain_candidate","-")}</strong></td>'
                     f'<td>{d.get("consolidate_candidate","-")}</td>'
                     f'<td>${d.get("potential_annual_savings",0):,.0f}</td>'
                     f'<td><span class="badge badge-{prio.lower()}">{prio}</span></td></tr>')
        return rows

    def _dup_section(self, rows):
        return (f'<div class="section"><h2>Duplication & Consolidation Opportunities</h2>'
                f'<table><thead><tr><th>Category</th><th>Tool A</th><th>Tool B</th>'
                f'<th>Overlap</th><th>Retain</th><th>Consolidate</th><th>Est. Savings</th>'
                f'<th>Priority</th></tr></thead><tbody>{rows}</tbody></table></div>')
