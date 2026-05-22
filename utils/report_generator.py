import io
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any
from fpdf import FPDF
 
 
ACTION_COLORS = {
    "Retain":     ("#155724", "#d4edda"),
    "Rehost":     ("#004085", "#cce5ff"),
    "Replatform": ("#856404", "#fff3cd"),
    "Refactor":   ("#7d3c00", "#fde8d8"),
    "Replace":    ("#721c24", "#f8d7da"),
    "Retire":     ("#383d41", "#e2e3e5"),
}
 
ACTION_DESCRIPTIONS = {
    "Retain":     "Strategic, healthy, high-value - no immediate action required",
    "Rehost":     "Lift-and-shift to cloud infrastructure with minimal changes",
    "Replatform": "Minor modernization leveraging managed / cloud-native services",
    "Refactor":   "Significant redesign and re-architecture required",
    "Replace":    "Better market alternative exists - plan migration",
    "Retire":     "Decommission - low value, high cost, or redundant",
}
 
TIME_COLORS = {
    "INVEST":    ("#155724", "#d4edda"),
    "TOLERATE":  ("#004085", "#cce5ff"),
    "MIGRATE":   ("#856404", "#fff3cd"),
    "ELIMINATE": ("#721c24", "#f8d7da"),
}
 
TIME_DESCRIPTIONS = {
    "INVEST":    "High strategic value - continue and grow investment",
    "TOLERATE":  "Functional but not strategic - maintain, no new investment",
    "MIGRATE":   "Move to a better platform, cloud, or replacement",
    "ELIMINATE": "Decommission - retire or replace immediately",
}
 
# ── Badge colours (R, G, B tuples) ──────────────────────────────────────────
BADGE_COLORS = {
    "invest":      ((21, 87, 36),    (212, 237, 218)),
    "tolerate":    ((0, 64, 133),    (204, 229, 255)),
    "migrate":     ((133, 100, 4),   (255, 243, 205)),
    "eliminate":   ((114, 28, 36),   (248, 215, 218)),
    "retain":      ((21, 87, 36),    (212, 237, 218)),
    "rehost":      ((0, 64, 133),    (204, 229, 255)),
    "replatform":  ((133, 100, 4),   (255, 243, 205)),
    "refactor":    ((125, 60, 0),    (253, 232, 216)),
    "replace":     ((114, 28, 36),   (248, 215, 218)),
    "retire":      ((56, 61, 65),    (226, 227, 229)),
    "high":        ((114, 28, 36),   (248, 215, 218)),
    "medium":      ((133, 100, 4),   (255, 243, 205)),
    "low":         ((21, 87, 36),    (212, 237, 218)),
    "critical":    ((255, 255, 255), (192, 57, 43)),
    "tbd":         ((56, 61, 65),    (226, 227, 229)),
}
 
NAVY  = (10, 22, 40)
BLUE  = (0, 99, 220)
WHITE = (255, 255, 255)
LGREY = (248, 251, 255)
DGREY = (100, 110, 130)
BLACK = (26, 35, 64)
 
 
def _hex_to_rgb(h: str):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
 
 
def _badge_colors(key: str):
    k = key.lower().replace(" ", "-")
    return BADGE_COLORS.get(k, BADGE_COLORS["tbd"])
 
 
class EAPdf(FPDF):
    """Custom FPDF subclass with EA branding helpers."""
 
    def header(self):
        pass  # handled manually per section
 
    def footer(self):
        self.set_y(-12)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*DGREY)
        self.cell(0, 8,
                  f"EA AI Intelligence  |  CONFIDENTIAL  |  {datetime.now().strftime('%Y')}  |  Page {self.page_no()}",
                  align="C")
 
    # ── Helpers ──────────────────────────────────────────────────────────────
 
    def cover_header(self, title: str, subtitle: str, meta: str):
        self.set_fill_color(*NAVY)
        self.rect(0, 0, 210, 42, "F")
        self.set_xy(10, 8)
        self.set_font("Helvetica", "B", 13)
        self.set_text_color(*WHITE)
        self.cell(190, 7, title[:80], ln=True)
        self.set_x(10)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(170, 187, 221)
        self.cell(190, 5, subtitle[:100], ln=True)
        self.set_xy(10, 34)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(136, 153, 187)
        self.cell(190, 5, meta[:120])
        self.ln(12)
 
    def section_title(self, text: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(*NAVY)
        self.cell(0, 7, text, ln=True)
        self.set_draw_color(*BLUE)
        self.set_line_width(0.6)
        self.line(self.get_x(), self.get_y(), self.get_x() + 190, self.get_y())
        self.set_line_width(0.2)
        self.ln(4)
 
    def sub_title(self, text: str):
        self.ln(2)
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(0, 51, 102)
        self.cell(0, 6, text, ln=True)
        self.ln(1)
 
    def kpi_row(self, items: list):
        """items = list of (value_str, label_str)"""
        col_w = 190 / len(items)
        x0 = self.get_x()
        y0 = self.get_y()
        for i, (val, lbl) in enumerate(items):
            x = x0 + i * col_w
            self.set_fill_color(*LGREY)
            self.set_draw_color(208, 216, 238)
            self.rect(x, y0, col_w - 1, 22, "FD")
            self.set_xy(x, y0 + 2)
            self.set_font("Helvetica", "B", 16)
            self.set_text_color(*BLUE)
            self.cell(col_w - 1, 8, val, align="C")
            self.set_xy(x, y0 + 11)
            self.set_font("Helvetica", "", 7)
            self.set_text_color(*DGREY)
            self.cell(col_w - 1, 5, lbl.upper(), align="C")
        self.set_y(y0 + 26)
 
    def badge(self, text: str, w: float = 0):
        fg, bg = _badge_colors(text)
        if w == 0:
            w = self.get_string_width(text) + 6
        self.set_fill_color(*bg)
        self.set_text_color(*fg)
        self.set_font("Helvetica", "B", 7)
        self.cell(w, 5, text, fill=True, align="C")
        self.set_text_color(*BLACK)
 
    def table_header(self, cols: list, widths: list):
        self.set_fill_color(*NAVY)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 8)
        for col, w in zip(cols, widths):
            self.cell(w, 7, col, border=0, fill=True)
        self.ln()
        self.set_text_color(*BLACK)
 
    def table_row(self, cells: list, widths: list, shade: bool = False):
        if shade:
            self.set_fill_color(*LGREY)
        else:
            self.set_fill_color(*WHITE)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*BLACK)
        row_y = self.get_y()
        # check page break
        if row_y > 270:
            self.add_page()
            row_y = self.get_y()
        for cell, w in zip(cells, widths):
            self.cell(w, 6, str(cell)[:40], border=0, fill=True)
        self.ln()
        self.set_draw_color(232, 237, 248)
        self.line(10, self.get_y(), 200, self.get_y())
 
    def exec_box(self, text: str):
        self.set_fill_color(*LGREY)
        self.set_draw_color(*BLUE)
        self.set_line_width(0.8)
        x = self.get_x()
        y = self.get_y()
        # left bar
        self.set_fill_color(*BLUE)
        self.rect(x, y, 1.5, 0, "F")  # placeholder - drawn after
        self.set_fill_color(*LGREY)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*BLACK)
        self.set_x(x + 3)
        self.multi_cell(185, 5, str(text)[:1200], fill=True)
        # draw left accent after
        box_h = self.get_y() - y
        self.set_fill_color(*BLUE)
        self.rect(x, y, 1.5, box_h, "F")
        self.set_line_width(0.2)
        self.ln(3)
 
    def rec_card(self, title: str, priority: str, effort: str, desc: str, impact: str):
        if self.get_y() > 265:
            self.add_page()
        y = self.get_y()
        self.set_fill_color(*LGREY)
        self.set_draw_color(204, 213, 238)
        self.rect(10, y, 190, 0, "F")  # placeholder
        # left accent
        self.set_fill_color(*BLUE)
        self.rect(10, y, 1.5, 0, "F")
        self.set_x(13)
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(*NAVY)
        self.cell(130, 5, title[:80], ln=False)
        self.badge(priority, 20)
        self.ln(6)
        self.set_x(13)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*DGREY)
        self.cell(0, 4, f"Effort: {effort}", ln=True)
        self.set_x(13)
        self.set_font("Helvetica", "", 8)
        self.set_text_color(*BLACK)
        self.multi_cell(185, 4, desc[:300])
        self.set_x(13)
        self.set_font("Helvetica", "I", 7)
        self.set_text_color(*BLUE)
        self.multi_cell(185, 4, impact[:200])
        card_h = self.get_y() - y
        self.set_fill_color(*LGREY)
        self.rect(10, y, 190, card_h, "FD")
        self.set_fill_color(*BLUE)
        self.rect(10, y, 1.5, card_h, "F")
        self.ln(3)
 
 
# ════════════════════════════════════════════════════════════════════════════
# Main ReportGenerator class
# ════════════════════════════════════════════════════════════════════════════
 
class ReportGenerator:
 
    def generate(
        self,
        tools: List[Dict],
        duplications: List[Dict],
        assessments: List[Dict],
        report_type: str = "full",
        output_dir: str = "reports",
        fmt: str = "pdf",
    ) -> str:
        """Generate a report. fmt='pdf' (default) or 'html'."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        if fmt == "html":
            path = Path(output_dir) / f"ea_portfolio_report_{timestamp}.html"
            path.write_text(self._build_html(tools, duplications, assessments), encoding="utf-8")
        else:
            path = Path(output_dir) / f"ea_portfolio_report_{timestamp}.pdf"
            self._write_pdf(tools, duplications, assessments, str(path))
        return str(path)
 
    def _write_pdf(
        self,
        tools: List[Dict],
        duplications: List[Dict],
        assessments: List[Dict],
        dest: str,
    ) -> None:
        pdf = EAPdf()
        pdf.set_margins(10, 10, 10)
        pdf.set_auto_page_break(True, margin=14)
        pdf.add_page()
 
        gen_date = datetime.now().strftime("%d %B %Y %H:%M")
        total_cost = sum(t.get("annual_cost", 0) or 0 for t in tools)
        pot_savings = sum(d.get("potential_annual_savings", 0) or 0 for d in duplications)
 
        pdf.cover_header(
            "EA AI Intelligence - Portfolio Rationalization Report",
            "Enterprise Architecture  |  Application Portfolio Assessment  |  AI-Powered Advisory",
            f"Generated: {gen_date}  |  Framework: TIME + 6R Rationalization Model  |  CONFIDENTIAL",
        )
 
        # KPIs
        pdf.kpi_row([
            (str(len(tools)), "Apps Assessed"),
            (f"${total_cost:,.0f}", "Total Annual Spend"),
            (str(len(duplications)), "Overlap Pairs"),
            (f"${pot_savings:,.0f}", "Est. Savings"),
        ])
 
        # Assessments
        self._pdf_assessment_section(pdf, assessments)
 
        # TIME breakdown
        action_counts: Dict[str, int] = {}
        time_counts: Dict[str, int] = {}
        for t in tools:
            a = t.get("rationalization_action", "TBD")
            action_counts[a] = action_counts.get(a, 0) + 1
            tc = t.get("time_classification", "TOLERATE")
            time_counts[tc] = time_counts.get(tc, 0) + 1
 
        pdf.section_title("Portfolio Classification Summary")
        pdf.sub_title("TIME Classification")
        self._pdf_time_table(pdf, time_counts, len(tools))
        pdf.sub_title("6R Action Breakdown")
        self._pdf_action_table(pdf, action_counts, len(tools))
 
        # App detail
        pdf.section_title("Application Portfolio Detail")
        self._pdf_tool_table(pdf, tools)
 
        # Duplications
        if duplications:
            pdf.section_title("Duplication & Consolidation Opportunities")
            self._pdf_dup_table(pdf, duplications)
 
        pdf.output(dest)
 
    def generate_pipeline_pdf(self, pipeline: Dict, output_dir: str = "reports") -> str:
        """Generate a comprehensive multi-section PDF from the full EA pipeline output."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path(output_dir) / f"ea_full_intelligence_report_{timestamp}.pdf"
 
        pdf = EAPdf()
        pdf.set_margins(10, 10, 10)
        pdf.set_auto_page_break(True, margin=14)
        pdf.add_page()
 
        gen_date = datetime.now().strftime("%d %B %Y %H:%M")
        summary      = pipeline.get("pipeline_summary", {})
        time_data    = pipeline.get("TIME", {})
        mapping_data = pipeline.get("MAPPING", {})
        maturity_data= pipeline.get("MATURITY", {})
        insights_data= pipeline.get("INSIGHTS", {})
 
        apps         = time_data.get("applications", [])
        dups         = time_data.get("duplications", [])
        time_summary = time_data.get("portfolio_summary", {})
        time_assess  = time_data.get("assessment", {})
 
        total_cost   = time_summary.get("total_annual_cost", 0)
        pot_savings  = time_summary.get("potential_savings", 0)
        mat_score    = maturity_data.get("overall_maturity_score", "-")
        overall_risk = insights_data.get("risk_profile", {}).get("overall_risk", "-")
 
        stages = " > ".join(summary.get("stages_completed", []))
        pdf.cover_header(
            "EA AI Intelligence - Full Enterprise Architecture Report",
            "Portfolio Rationalization  |  Dependency Analysis  |  Maturity Assessment  |  Executive Intelligence",
            f"Generated: {gen_date}  |  Stages: {stages}  |  CONFIDENTIAL",
        )
 
        pdf.kpi_row([
            (str(len(apps)),          "Apps Assessed"),
            (f"${total_cost:,.0f}",   "Total Annual Spend"),
            (str(summary.get("flagged_for_action", 0)), "Apps Flagged"),
            (f"${pot_savings:,.0f}",  "Potential Savings"),
            (f"{mat_score}/5",        "EA Maturity Score"),
            (str(overall_risk),       "Overall Risk"),
        ])
 
        # Insights exec summary
        self._pdf_pipeline_insights(pdf, insights_data)
 
        # TIME
        pdf.section_title("Stage 1 - Portfolio Rationalization (TIME)")
        exec_sum = time_assess.get("executive_summary", "")
        if exec_sum:
            pdf.exec_box(exec_sum)
        action_counts: Dict[str, int] = {}
        time_counts: Dict[str, int] = {}
        for t in apps:
            a = t.get("rationalization_action", "TBD")
            action_counts[a] = action_counts.get(a, 0) + 1
            tc = t.get("time_classification", "TOLERATE")
            time_counts[tc] = time_counts.get(tc, 0) + 1
        pdf.sub_title("TIME Classification")
        self._pdf_time_table(pdf, time_counts, len(apps))
        pdf.sub_title("Application Detail")
        self._pdf_tool_table_compact(pdf, apps)
        if dups:
            pdf.sub_title("Duplication Opportunities")
            self._pdf_dup_table(pdf, dups)
        self._pdf_roadmap(pdf, time_assess.get("roadmap", {}))
 
        # Mapping
        pdf.section_title("Stage 2 - Dependency & Impact Analysis (MAPPING)")
        self._pdf_mapping_section(pdf, mapping_data)
 
        # Maturity
        pdf.section_title("Stage 3 - EA Maturity Assessment (MATURITY)")
        self._pdf_maturity_section(pdf, maturity_data)
 
        # Insights recs
        pdf.section_title("Stage 4 - Strategic Recommendations & KPIs (INSIGHTS)")
        self._pdf_insights_recs(pdf, insights_data)
 
        pdf.output(str(path))
        return str(path)
 
    # ── PDF section helpers ──────────────────────────────────────────────────
 
    def _pdf_assessment_section(self, pdf: EAPdf, assessments: List[Dict]):
        if not assessments:
            return
        latest = assessments[-1]
 
        exec_sum = latest.get("executive_summary", "")
        if exec_sum:
            pdf.section_title("Executive Summary")
            pdf.exec_box(exec_sum)
 
        recs = latest.get("top_recommendations", [])
        if recs:
            pdf.section_title("Top Priority Recommendations")
            for r in recs[:5]:
                pdf.rec_card(
                    f"#{r.get('rank','')} {r.get('title','')}",
                    r.get("priority", "Medium"),
                    r.get("effort", "-"),
                    r.get("description", ""),
                    f"Impact: {r.get('impact','')}  |  Timeline: {r.get('timeline','')}",
                )
 
        roadmap = latest.get("roadmap", {})
        if roadmap:
            pdf.section_title("Rationalization Roadmap")
            self._pdf_roadmap(pdf, roadmap)
 
        outcomes = latest.get("expected_outcomes", {})
        if outcomes:
            pdf.section_title("Expected Business Outcomes")
            pdf.table_header(["Outcome", "Detail"], [70, 120])
            for i, (k, v) in enumerate(outcomes.items()):
                pdf.table_row([k.replace("_", " ").title(), str(v)], [70, 120], shade=i % 2 == 0)
 
    def _pdf_time_table(self, pdf: EAPdf, counts: Dict[str, int], total: int):
        pdf.table_header(["TIME", "Count", "%", "Description"], [30, 20, 20, 120])
        for i, cat in enumerate(["INVEST", "TOLERATE", "MIGRATE", "ELIMINATE"]):
            c = counts.get(cat, 0)
            if c == 0:
                continue
            pct = round(c / max(total, 1) * 100)
            desc = TIME_DESCRIPTIONS.get(cat, "")
            y = pdf.get_y()
            pdf.set_fill_color(*(LGREY if i % 2 == 0 else WHITE))
            pdf.set_font("Helvetica", "", 8)
            pdf.set_x(10)
            pdf.badge(cat, 28)
            pdf.set_x(40)
            pdf.cell(18, 6, str(c), fill=False)
            pdf.cell(18, 6, f"{pct}%", fill=False)
            pdf.cell(120, 6, desc[:70], fill=False)
            pdf.ln()
            pdf.set_draw_color(232, 237, 248)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
 
    def _pdf_action_table(self, pdf: EAPdf, counts: Dict[str, int], total: int):
        pdf.table_header(["6R Action", "Count", "%", "Description"], [30, 20, 20, 120])
        for i, action in enumerate(["Retain", "Rehost", "Replatform", "Refactor", "Replace", "Retire"]):
            c = counts.get(action, 0)
            if c == 0:
                continue
            pct = round(c / max(total, 1) * 100)
            desc = ACTION_DESCRIPTIONS.get(action, "")
            pdf.set_x(10)
            pdf.badge(action, 28)
            pdf.set_x(40)
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(18, 6, str(c))
            pdf.cell(18, 6, f"{pct}%")
            pdf.cell(120, 6, desc[:70])
            pdf.ln()
            pdf.set_draw_color(232, 237, 248)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
 
    def _pdf_tool_table(self, pdf: EAPdf, tools: List[Dict]):
        cols   = ["Application", "Vendor", "Category", "Cost", "Users", "Score", "TIME", "6R", "Confidence"]
        widths = [32, 22, 22, 18, 14, 12, 22, 22, 16]
        pdf.table_header(cols, widths)
        for i, t in enumerate(tools):
            if pdf.get_y() > 270:
                pdf.add_page()
                pdf.table_header(cols, widths)
            action   = t.get("rationalization_action", "TBD")
            time_cls = t.get("time_classification", "TOLERATE")
            score    = t.get("composite_score", "-")
            conf     = t.get("confidence_level", "-")
            cost     = f"${t.get('annual_cost', 0):,.0f}" if t.get("annual_cost") else "-"
            users    = str(t.get("user_count", "-"))
            shade    = i % 2 == 0
            fill_col = LGREY if shade else WHITE
            pdf.set_fill_color(*fill_col)
            pdf.set_font("Helvetica", "B", 7)
            pdf.cell(32, 6, t.get("name", "-")[:20], fill=True)
            pdf.set_font("Helvetica", "", 7)
            pdf.cell(22, 6, (t.get("vendor") or "-")[:14], fill=True)
            pdf.cell(22, 6, (t.get("category") or "-")[:14], fill=True)
            pdf.cell(18, 6, cost, fill=True)
            pdf.cell(14, 6, users, fill=True)
            pdf.cell(12, 6, f"{score}/10", fill=True)
            pdf.badge(time_cls, 22)
            pdf.badge(action, 22)
            pdf.badge(conf if conf != "-" else "medium", 16)
            pdf.ln()
            pdf.set_draw_color(232, 237, 248)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
 
    def _pdf_tool_table_compact(self, pdf: EAPdf, tools: List[Dict]):
        cols   = ["Application", "Category", "Cost", "Users", "Score", "TIME", "6R"]
        widths = [40, 30, 22, 16, 14, 28, 28]
        pdf.table_header(cols, widths)
        for i, t in enumerate(tools):
            if pdf.get_y() > 270:
                pdf.add_page()
                pdf.table_header(cols, widths)
            action   = t.get("rationalization_action", "TBD")
            time_cls = t.get("time_classification", "TOLERATE")
            score    = t.get("composite_score", "-")
            cost     = f"${t.get('annual_cost', 0):,.0f}" if t.get("annual_cost") else "-"
            users    = str(t.get("user_count", "-"))
            fill_col = LGREY if i % 2 == 0 else WHITE
            pdf.set_fill_color(*fill_col)
            pdf.set_font("Helvetica", "B", 7)
            pdf.cell(40, 6, t.get("name", "-")[:24], fill=True)
            pdf.set_font("Helvetica", "", 7)
            pdf.cell(30, 6, t.get("category", "-")[:18], fill=True)
            pdf.cell(22, 6, cost, fill=True)
            pdf.cell(16, 6, users, fill=True)
            pdf.cell(14, 6, f"{score}/10", fill=True)
            pdf.badge(time_cls, 28)
            pdf.badge(action, 28)
            pdf.ln()
            pdf.set_draw_color(232, 237, 248)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
 
    def _pdf_dup_table(self, pdf: EAPdf, dups: List[Dict]):
        cols   = ["Category", "Tool A", "Tool B", "Overlap", "Retain", "Savings", "Priority"]
        widths = [25, 28, 28, 18, 28, 28, 18]
        pdf.table_header(cols, widths)
        for i, d in enumerate(dups[:15]):
            savings = f"${d.get('potential_annual_savings', 0):,.0f}"
            prio    = d.get("priority", "Low")
            fill_col = LGREY if i % 2 == 0 else WHITE
            pdf.set_fill_color(*fill_col)
            pdf.set_font("Helvetica", "", 7)
            pdf.cell(25, 6, d.get("category", "-")[:14], fill=True)
            pdf.cell(28, 6, d.get("tool_a", "-")[:16], fill=True)
            pdf.cell(28, 6, d.get("tool_b", "-")[:16], fill=True)
            pdf.cell(18, 6, f"{d.get('overlap_percentage', 0)}%", fill=True)
            pdf.cell(28, 6, d.get("retain_candidate", "-")[:16], fill=True)
            pdf.cell(28, 6, savings, fill=True)
            pdf.badge(prio, 18)
            pdf.ln()
            pdf.set_draw_color(232, 237, 248)
            pdf.line(10, pdf.get_y(), 200, pdf.get_y())
 
    def _pdf_roadmap(self, pdf: EAPdf, roadmap: Dict):
        if not roadmap:
            return
        phases = [
            ("Phase 1 - Quick Wins (0-3 Months)",         roadmap.get("short_term", [])),
            ("Phase 2 - Strategic (3-12 Months)",          roadmap.get("medium_term", [])),
            ("Phase 3 - Transformation (12-24 Months)",    roadmap.get("long_term", [])),
        ]
        for phase_name, items in phases:
            if not items:
                continue
            if isinstance(items, str):
                items = [items]
            pdf.sub_title(phase_name)
            for item in items[:8]:
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*BLACK)
                pdf.set_x(14)
                pdf.cell(3, 5, ">")
                pdf.cell(0, 5, str(item)[:110], ln=True)
 
    def _pdf_pipeline_insights(self, pdf: EAPdf, insights: Dict):
        if not insights or "error" in insights:
            return
        exec_sum = insights.get("executive_summary", "")
        if exec_sum:
            pdf.section_title("Executive Intelligence Summary")
            pdf.exec_box(exec_sum)
 
        fin = insights.get("financial_impact", {})
        if fin:
            pdf.sub_title("Financial Impact")
            pdf.table_header(["Metric", "Value"], [80, 110])
            for i, (k, v) in enumerate(fin.items()):
                if v:
                    pdf.table_row([k.replace("_", " ").title(), str(v)], [80, 110], shade=i % 2 == 0)
 
        risks = insights.get("risk_profile", {}).get("top_risks", [])
        if risks:
            pdf.sub_title("Top Risks")
            pdf.table_header(["Risk", "Impact", "Mitigation"], [55, 55, 80])
            for i, r in enumerate(risks[:5]):
                pdf.table_row(
                    [r.get("risk", "")[:30], r.get("impact", "")[:30], r.get("mitigation", "")[:45]],
                    [55, 55, 80], shade=i % 2 == 0
                )
 
        quick_wins = insights.get("quick_wins", [])
        if quick_wins:
            pdf.sub_title("Quick Wins")
            for w in quick_wins[:5]:
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*BLACK)
                pdf.set_x(14)
                pdf.cell(3, 5, chr(149))
                pdf.cell(0, 5, str(w)[:110], ln=True)
 
    def _pdf_mapping_section(self, pdf: EAPdf, mapping: Dict):
        if not mapping or mapping.get("skipped"):
            reason = mapping.get("reason", "No apps flagged for ELIMINATE/MIGRATE.")
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*DGREY)
            pdf.multi_cell(0, 5, reason)
            return
 
        overall = mapping.get("overall_impact_level", "-")
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(*BLACK)
        pdf.cell(0, 5, f"Overall Impact Level: {overall}", ln=True)
        pdf.ln(2)
 
        ctx = mapping.get("pipeline_context", "")
        if ctx:
            pdf.exec_box(ctx)
 
        app_analyses = mapping.get("app_analyses", [])
        if app_analyses:
            pdf.sub_title("Per-Application Analysis")
            pdf.table_header(
                ["Application", "TIME", "Impact", "Coupling", "Dependencies"],
                [38, 26, 22, 18, 86]
            )
            for i, a in enumerate(app_analyses):
                impact   = a.get("impact_level", "-")
                coupling = a.get("coupling_score", "-")
                tc       = a.get("time_classification", "-")
                deps     = ", ".join((a.get("direct_dependencies") or [])[:3])
                y = pdf.get_y()
                if y > 270:
                    pdf.add_page()
                fill_col = LGREY if i % 2 == 0 else WHITE
                pdf.set_fill_color(*fill_col)
                pdf.set_font("Helvetica", "B", 7)
                pdf.cell(38, 6, a.get("app_name", "-")[:22], fill=True)
                pdf.badge(tc, 26)
                pdf.badge(impact, 22)
                pdf.set_font("Helvetica", "", 7)
                pdf.cell(18, 6, f"{coupling}/10", fill=True)
                pdf.cell(86, 6, deps[:50], fill=True)
                pdf.ln()
                pdf.set_draw_color(232, 237, 248)
                pdf.line(10, pdf.get_y(), 200, pdf.get_y())
 
        order = mapping.get("recommended_migration_order", [])
        if order:
            pdf.sub_title("Recommended Migration Order")
            for i, app in enumerate(order):
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*BLACK)
                pdf.set_x(14)
                pdf.cell(10, 5, f"{i+1}.")
                pdf.cell(0, 5, str(app)[:100], ln=True)
 
    def _pdf_maturity_section(self, pdf: EAPdf, maturity: Dict):
        if not maturity:
            return
        score = maturity.get("overall_maturity_score", "-")
        level = maturity.get("maturity_level", "-")
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*NAVY)
        pdf.cell(60, 6, f"Overall Score: {score}/5", ln=False)
        pdf.badge(level, 60)
        pdf.ln(8)
 
        dims = maturity.get("dimensions", {})
        if dims:
            pdf.sub_title("Dimension Scores")
            pdf.table_header(["Dimension", "Score", "Key Gaps"], [55, 20, 115])
            for i, (dk, dv) in enumerate(dims.items()):
                if not isinstance(dv, dict):
                    continue
                ds   = dv.get("score", "-")
                gaps = ", ".join(dv.get("gaps", [])[:2]) or "-"
                pdf.table_row(
                    [dk.replace("_", " ").title(), f"{ds}/5", gaps[:65]],
                    [55, 20, 115], shade=i % 2 == 0
                )
 
        priorities = maturity.get("top_priorities", [])
        if priorities:
            pdf.sub_title("Top Improvement Priorities")
            for p in priorities[:5]:
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*BLACK)
                pdf.set_x(14)
                pdf.cell(3, 5, chr(149))
                pdf.cell(0, 5, str(p)[:110], ln=True)
 
        roadmap = maturity.get("roadmap", [])
        if roadmap:
            pdf.sub_title("Maturity Improvement Roadmap")
            pdf.table_header(["Phase", "Key Actions"], [55, 135])
            for i, phase in enumerate(roadmap[:3]):
                actions = phase.get("actions", [])
                acts = "; ".join(actions[:3]) if actions else "-"
                pdf.table_row(
                    [phase.get("phase", "")[:30], acts[:80]],
                    [55, 135], shade=i % 2 == 0
                )
 
    def _pdf_insights_recs(self, pdf: EAPdf, insights: Dict):
        if not insights:
            return
        recs = insights.get("strategic_recommendations", [])
        for r in recs[:6]:
            pdf.rec_card(
                f"Priority {r.get('priority','')} - {r.get('recommendation','')}",
                str(r.get("effort", "Medium")),
                str(r.get("effort", "-")),
                str(r.get("business_value", ""))[:300],
                f"Effort: {r.get('effort','-')}  |  Timeline: {r.get('timeline','-')}",
            )
 
        kpis = insights.get("kpis", [])
        if kpis:
            pdf.sub_title("Key Performance Indicators")
            pdf.table_header(["Metric", "Current", "Target", "Timeframe"], [60, 40, 40, 50])
            for i, k in enumerate(kpis[:6]):
                pdf.table_row(
                    [k.get("metric","")[:35], str(k.get("current",""))[:20],
                     str(k.get("target",""))[:20], str(k.get("timeframe",""))[:25]],
                    [60, 40, 40, 50], shade=i % 2 == 0
                )
 
    # ── HTML builder (unchanged from original) ───────────────────────────────
 
    def _build_html(
        self,
        tools: List[Dict],
        duplications: List[Dict],
        assessments: List[Dict],
    ) -> str:
        total_cost  = sum(t.get("annual_cost", 0) or 0 for t in tools)
        pot_savings = sum(d.get("potential_annual_savings", 0) or 0 for d in duplications)
        gen_date    = datetime.now().strftime("%d %B %Y %H:%M")
 
        action_counts: Dict[str, int] = {}
        time_counts:   Dict[str, int] = {}
        for t in tools:
            a  = t.get("rationalization_action", "TBD")
            action_counts[a] = action_counts.get(a, 0) + 1
            tc = t.get("time_classification", "TOLERATE")
            time_counts[tc]  = time_counts.get(tc, 0) + 1
 
        assessment_section   = self._assessment_section(assessments)
        tool_rows            = self._tool_rows(tools)
        dup_rows             = self._dup_rows(duplications)
        action_summary_rows  = self._action_summary_rows(action_counts)
        time_summary_rows    = self._time_summary_rows(time_counts)
 
        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>EA Portfolio Rationalization Report</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#f0f4fa;color:#1a2340;font-size:14px}}
  .report{{max-width:1340px;margin:0 auto;background:#fff;box-shadow:0 0 40px rgba(0,0,0,.1)}}
  .header{{background:#0a1628;color:#fff;padding:48px 40px}}
  .header h1{{font-size:26px;font-weight:700}}
  .header .sub{{opacity:.75;font-size:13px;margin-top:4px}}
  .header .meta{{font-size:12px;opacity:.7;margin-top:12px}}
  .kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#e0e7f0}}
  .kpi{{background:#fff;padding:28px 24px;text-align:center}}
  .kpi .val{{font-size:34px;font-weight:700;color:#0063DC}}
  .kpi .lbl{{font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.8px;margin-top:6px}}
  .section{{padding:36px 40px;border-bottom:1px solid #eef1f8}}
  h2{{font-size:18px;font-weight:700;color:#0a1628;margin-bottom:20px;padding-bottom:12px;border-bottom:2px solid #0063DC}}
  .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  thead th{{background:#0a1628;color:#fff;padding:11px 14px;text-align:left;font-weight:600;font-size:12px}}
  tbody td{{padding:10px 14px;border-bottom:1px solid #f0f3fa}}
  tbody tr:hover{{background:#f8fbff}}
  .badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
  .badge-retain{{color:#155724;background:#d4edda}}
  .badge-rehost{{color:#004085;background:#cce5ff}}
  .badge-replatform{{color:#856404;background:#fff3cd}}
  .badge-refactor{{color:#7d3c00;background:#fde8d8}}
  .badge-replace{{color:#721c24;background:#f8d7da}}
  .badge-retire{{color:#383d41;background:#e2e3e5}}
  .badge-invest{{color:#155724;background:#d4edda}}
  .badge-tolerate{{color:#004085;background:#cce5ff}}
  .badge-migrate{{color:#856404;background:#fff3cd}}
  .badge-eliminate{{color:#721c24;background:#f8d7da}}
  .badge-high{{color:#721c24;background:#f8d7da}}
  .badge-medium{{color:#856404;background:#fff3cd}}
  .badge-low{{color:#155724;background:#d4edda}}
  .exec-box{{background:#f8fbff;border-left:4px solid #0063DC;padding:24px;line-height:1.8;white-space:pre-wrap}}
  .footer{{background:#0a1628;color:#8899bb;padding:20px 40px;font-size:12px;text-align:center}}
</style>
</head>
<body>
<div class="report">
<div class="header">
  <h1>EA AI Intelligence - Portfolio Rationalization Report</h1>
  <div class="sub">Enterprise Architecture . Application Portfolio Assessment . AI-Powered Advisory</div>
  <div class="meta">Generated: {gen_date} . Framework: TIME + 6R Rationalization Model</div>
</div>
<div class="kpi-grid">
  <div class="kpi"><div class="val">{len(tools)}</div><div class="lbl">Applications Assessed</div></div>
  <div class="kpi"><div class="val">${total_cost:,.0f}</div><div class="lbl">Total Annual Spend</div></div>
  <div class="kpi"><div class="val">{len(duplications)}</div><div class="lbl">Overlap Pairs Found</div></div>
  <div class="kpi"><div class="val">${pot_savings:,.0f}</div><div class="lbl">Est. Annual Savings</div></div>
</div>
<div class="section">
  <h2>Portfolio Classification Summary</h2>
  <div class="two-col">
    <div>
      <table>
        <thead><tr><th>TIME</th><th>Count</th><th>% of Portfolio</th><th>Description</th></tr></thead>
        <tbody>{time_summary_rows}</tbody>
      </table>
    </div>
    <div>
      <table>
        <thead><tr><th>6R Action</th><th>Count</th><th>% of Portfolio</th><th>Description</th></tr></thead>
        <tbody>{action_summary_rows}</tbody>
      </table>
    </div>
  </div>
</div>
{assessment_section}
<div class="section">
  <h2>Application Portfolio Detail</h2>
  <table>
    <thead><tr><th>Application</th><th>Vendor</th><th>Category</th><th>Annual Cost</th><th>Users</th><th>Score</th><th>TIME</th><th>6R Action</th></tr></thead>
    <tbody>{tool_rows}</tbody>
  </table>
</div>
{self._dup_section(dup_rows) if duplications else ""}
<div class="footer">EA AI Intelligence - CONFIDENTIAL - {datetime.now().strftime("%Y")}</div>
</div>
</body>
</html>"""
 
    # ── HTML section helpers (unchanged from original) ────────────────────────
 
    def _assessment_section(self, assessments):
        if not assessments:
            return ""
        latest = assessments[-1]
        parts = []
        exec_sum = latest.get("executive_summary", "")
        if exec_sum:
            parts.append(f'<div class="section"><h2>Executive Summary</h2><div class="exec-box">{exec_sum}</div></div>')
        recs = latest.get("top_recommendations", [])
        if recs:
            cards = ""
            for r in recs[:5]:
                prio = r.get("priority", "Medium")
                cards += f'<div style="border:1px solid #ccd5ee;padding:16px;margin-bottom:12px;border-left:4px solid #0063DC;background:#f8fbff"><strong>#{r.get("rank","")} {r.get("title","")}</strong> <span class="badge badge-{prio.lower()}">{prio}</span><p style="margin-top:8px;color:#444">{r.get("description","")}</p><p style="color:#0063DC;font-style:italic;font-size:12px">Impact: {r.get("impact","")} . Timeline: {r.get("timeline","")}</p></div>'
            parts.append(f'<div class="section"><h2>Top Priority Recommendations</h2>{cards}</div>')
        roadmap = latest.get("roadmap", {})
        if roadmap:
            def pi(key):
                items = roadmap.get(key, [])
                if isinstance(items, str):
                    items = [items]
                return "".join(f"<li>{i}</li>" for i in items)
            parts.append(f'<div class="section"><h2>Rationalization Roadmap</h2><div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px"><div style="background:#f8fbff;border-top:3px solid #00A651;padding:16px"><strong>Phase 1 (0-3 Months)</strong><ul style="margin-top:8px;padding-left:16px">{pi("short_term")}</ul></div><div style="background:#f8fbff;border-top:3px solid #0063DC;padding:16px"><strong>Phase 2 (3-12 Months)</strong><ul style="margin-top:8px;padding-left:16px">{pi("medium_term")}</ul></div><div style="background:#f8fbff;border-top:3px solid #7B2FBE;padding:16px"><strong>Phase 3 (12-24 Months)</strong><ul style="margin-top:8px;padding-left:16px">{pi("long_term")}</ul></div></div></div>')
        return "\n".join(parts)
 
    def _time_summary_rows(self, counts):
        total = max(sum(counts.values()), 1)
        rows = ""
        for cat in ["INVEST", "TOLERATE", "MIGRATE", "ELIMINATE"]:
            c = counts.get(cat, 0)
            if c == 0:
                continue
            pct = round(c / total * 100)
            rows += f'<tr><td><span class="badge badge-{cat.lower()}">{cat}</span></td><td><strong>{c}</strong></td><td>{pct}%</td><td>{TIME_DESCRIPTIONS.get(cat,"")}</td></tr>'
        return rows
 
    def _action_summary_rows(self, counts):
        total = max(sum(counts.values()), 1)
        rows = ""
        for action in ["Retain", "Rehost", "Replatform", "Refactor", "Replace", "Retire"]:
            c = counts.get(action, 0)
            if c == 0:
                continue
            pct = round(c / total * 100)
            rows += f'<tr><td><span class="badge badge-{action.lower()}">{action}</span></td><td><strong>{c}</strong></td><td>{pct}%</td><td>{ACTION_DESCRIPTIONS.get(action,"")}</td></tr>'
        return rows
 
    def _tool_rows(self, tools):
        rows = ""
        for t in tools:
            action   = t.get("rationalization_action", "TBD")
            time_cls = t.get("time_classification", "TOLERATE")
            score    = t.get("composite_score", "-")
            cost     = f"${t.get('annual_cost', 0):,.0f}" if t.get("annual_cost") else "-"
            rows += f'<tr><td><strong>{t.get("name","-")}</strong></td><td>{t.get("vendor","-") or "-"}</td><td>{t.get("category","-")}</td><td>{cost}</td><td>{t.get("user_count","-")}</td><td><strong>{score}</strong>/10</td><td><span class="badge badge-{time_cls.lower()}">{time_cls}</span></td><td><span class="badge badge-{action.lower()}">{action}</span></td></tr>'
        return rows
 
    def _dup_rows(self, duplications):
        rows = ""
        for d in duplications[:15]:
            savings = f"${d.get('potential_annual_savings', 0):,.0f}"
            prio    = d.get("priority", "Low")
            rows += f'<tr><td>{d.get("category","-")}</td><td>{d.get("tool_a","-")}</td><td>{d.get("tool_b","-")}</td><td><strong>{d.get("overlap_percentage",0)}%</strong></td><td><strong>{d.get("retain_candidate","-")}</strong></td><td>{d.get("consolidate_candidate","-")}</td><td>{savings}</td><td><span class="badge badge-{prio.lower()}">{prio}</span></td></tr>'
        return rows
 
    def _dup_section(self, rows):
        return f'<div class="section"><h2>Duplication & Consolidation Opportunities</h2><table><thead><tr><th>Category</th><th>Tool A</th><th>Tool B</th><th>Overlap</th><th>Retain</th><th>Consolidate</th><th>Est. Savings</th><th>Priority</th></tr></thead><tbody>{rows}</tbody></table></div>'