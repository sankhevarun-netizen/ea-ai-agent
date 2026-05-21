import io
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any


ACTION_COLORS = {
    "Retain":     ("#155724", "#d4edda"),
    "Rehost":     ("#004085", "#cce5ff"),
    "Replatform": ("#856404", "#fff3cd"),
    "Refactor":   ("#7d3c00", "#fde8d8"),
    "Replace":    ("#721c24", "#f8d7da"),
    "Retire":     ("#383d41", "#e2e3e5"),
}

ACTION_DESCRIPTIONS = {
    "Retain":     "Strategic, healthy, high-value — no immediate action required",
    "Rehost":     "Lift-and-shift to cloud infrastructure with minimal changes",
    "Replatform": "Minor modernization leveraging managed / cloud-native services",
    "Refactor":   "Significant redesign and re-architecture required",
    "Replace":    "Better market alternative exists — plan migration",
    "Retire":     "Decommission — low value, high cost, or redundant",
}

TIME_COLORS = {
    "INVEST":    ("#155724", "#d4edda"),
    "TOLERATE":  ("#004085", "#cce5ff"),
    "MIGRATE":   ("#856404", "#fff3cd"),
    "ELIMINATE": ("#721c24", "#f8d7da"),
}

TIME_DESCRIPTIONS = {
    "INVEST":    "High strategic value — continue and grow investment",
    "TOLERATE":  "Functional but not strategic — maintain, no new investment",
    "MIGRATE":   "Move to a better platform, cloud, or replacement",
    "ELIMINATE": "Decommission — retire or replace immediately",
}


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
            self._write_pdf(tools, duplications, assessments, path)
        return str(path)

    def _write_pdf(
        self,
        tools: List[Dict],
        duplications: List[Dict],
        assessments: List[Dict],
        dest: Path,
    ) -> None:
        from xhtml2pdf import pisa
        html = self._build_pdf_html(tools, duplications, assessments)
        with open(dest, "wb") as f:
            result = pisa.CreatePDF(html, dest=f, encoding="utf-8")
        if result.err:
            raise RuntimeError(f"PDF generation error code {result.err}")

    def generate_pipeline_pdf(self, pipeline: Dict, output_dir: str = "reports") -> str:
        """Generate a comprehensive multi-section PDF from the full EA pipeline output."""
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = Path(output_dir) / f"ea_full_intelligence_report_{timestamp}.pdf"
        html = self._build_pipeline_pdf_html(pipeline)
        from xhtml2pdf import pisa
        with open(path, "wb") as f:
            result = pisa.CreatePDF(html, dest=f, encoding="utf-8")
        if result.err:
            raise RuntimeError(f"PDF generation error code {result.err}")
        return str(path)

    # ─── HTML builder ────────────────────────────────────────────────────────

    def _build_html(
        self,
        tools: List[Dict],
        duplications: List[Dict],
        assessments: List[Dict],
    ) -> str:
        total_cost = sum(t.get("annual_cost", 0) or 0 for t in tools)
        pot_savings = sum(d.get("potential_annual_savings", 0) or 0 for d in duplications)
        gen_date = datetime.now().strftime("%d %B %Y %H:%M")

        action_counts: Dict[str, int] = {}
        time_counts: Dict[str, int] = {}
        for t in tools:
            a = t.get("rationalization_action", "TBD")
            action_counts[a] = action_counts.get(a, 0) + 1
            tc = t.get("time_classification", "TOLERATE")
            time_counts[tc] = time_counts.get(tc, 0) + 1

        assessment_section = self._assessment_section(assessments)
        tool_rows = self._tool_rows(tools)
        dup_rows = self._dup_rows(duplications)
        action_summary_rows = self._action_summary_rows(action_counts)
        time_summary_rows = self._time_summary_rows(time_counts)

        return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>EA Portfolio Rationalization Report &mdash; {datetime.now().strftime("%B %Y")}</title>
<style>
  *{{margin:0;padding:0;box-sizing:border-box}}
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#f0f4fa;color:#1a2340;font-size:14px}}
  .report{{max-width:1340px;margin:0 auto;background:#fff;box-shadow:0 0 40px rgba(0,0,0,.1)}}
  .header{{background:linear-gradient(135deg,#0a1628 0%,#1a3a6e 60%,#0063DC 100%);color:#fff;padding:48px 40px}}
  .header-top{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:20px}}
  .logo-area h1{{font-size:26px;font-weight:700;letter-spacing:-.3px}}
  .logo-area .sub{{opacity:.75;font-size:13px;margin-top:4px}}
  .confidential{{background:rgba(255,255,255,.15);border:1px solid rgba(255,255,255,.3);
    padding:6px 14px;border-radius:4px;font-size:11px;font-weight:600;letter-spacing:1px}}
  .header-meta{{display:flex;gap:40px;font-size:12px;opacity:.7}}
  .kpi-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:1px;background:#e0e7f0}}
  .kpi{{background:#fff;padding:28px 24px;text-align:center}}
  .kpi .val{{font-size:34px;font-weight:700;color:#0063DC;line-height:1}}
  .kpi .lbl{{font-size:11px;color:#666;text-transform:uppercase;letter-spacing:.8px;margin-top:6px}}
  .section{{padding:36px 40px;border-bottom:1px solid #eef1f8}}
  .section:last-child{{border-bottom:none}}
  h2{{font-size:18px;font-weight:700;color:#0a1628;margin-bottom:20px;padding-bottom:12px;
    border-bottom:2px solid #0063DC;display:flex;align-items:center;gap:10px}}
  .two-col{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  thead th{{background:#0a1628;color:#fff;padding:11px 14px;text-align:left;font-weight:600;font-size:12px}}
  tbody td{{padding:10px 14px;border-bottom:1px solid #f0f3fa}}
  tbody tr:hover{{background:#f8fbff}}
  .badge{{display:inline-block;padding:3px 10px;border-radius:12px;font-size:11px;font-weight:700}}
  /* 6R badges */
  .badge-retain{{color:#155724;background:#d4edda}}
  .badge-rehost{{color:#004085;background:#cce5ff}}
  .badge-replatform{{color:#856404;background:#fff3cd}}
  .badge-refactor{{color:#7d3c00;background:#fde8d8}}
  .badge-replace{{color:#721c24;background:#f8d7da}}
  .badge-retire{{color:#383d41;background:#e2e3e5}}
  /* TIME badges */
  .badge-invest{{color:#155724;background:#d4edda}}
  .badge-tolerate{{color:#004085;background:#cce5ff}}
  .badge-migrate{{color:#856404;background:#fff3cd}}
  .badge-eliminate{{color:#721c24;background:#f8d7da}}
  /* priority / confidence */
  .badge-high{{color:#721c24;background:#f8d7da}}
  .badge-medium{{color:#856404;background:#fff3cd}}
  .badge-low{{color:#155724;background:#d4edda}}
  .badge-critical{{color:#fff;background:#c0392b}}
  .exec-box{{background:#f8fbff;border-left:4px solid #0063DC;padding:24px;border-radius:0 8px 8px 0;
    line-height:1.8;white-space:pre-wrap;font-size:14px}}
  .roadmap{{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;margin-top:4px}}
  .phase{{background:#f8fbff;border-radius:8px;padding:20px;border-top:3px solid}}
  .phase.p1{{border-color:#00A651}} .phase.p2{{border-color:#0063DC}} .phase.p3{{border-color:#7B2FBE}}
  .phase h3{{font-size:13px;font-weight:700;margin-bottom:12px;text-transform:uppercase;letter-spacing:.5px}}
  .phase ul{{list-style:none;padding:0}}
  .phase li{{font-size:13px;padding:6px 0;border-bottom:1px solid rgba(0,0,0,.06);
    padding-left:16px;position:relative}}
  .phase li::before{{content:'›';position:absolute;left:0;color:#0063DC;font-weight:700}}
  .rec-card{{background:#f8fbff;border:1px solid #e0e8f8;border-radius:8px;padding:20px;
    margin-bottom:14px;border-left:4px solid #0063DC}}
  .rec-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}
  .rec-title{{font-weight:700;font-size:14px;color:#0a1628}}
  .rec-meta{{display:flex;gap:8px}}
  .rec-desc{{font-size:13px;color:#444;line-height:1.6;margin-bottom:8px}}
  .rec-impact{{font-size:12px;color:#0063DC;font-style:italic}}
  .score-bar{{display:flex;align-items:center;gap:8px;font-size:12px}}
  .bar{{flex:1;height:6px;background:#eee;border-radius:3px;overflow:hidden}}
  .bar-fill{{height:100%;border-radius:3px;background:linear-gradient(90deg,#0063DC,#00A3E0)}}
  .footer{{background:#0a1628;color:#8899bb;padding:20px 40px;display:flex;
    justify-content:space-between;align-items:center;font-size:12px}}
  @media print{{
    body{{background:#fff}} .report{{box-shadow:none;max-width:100%}}
    .kpi-grid,.roadmap{{grid-template-columns:repeat(4,1fr)}}
  }}
</style>
</head>
<body>
<div class="report">

<div class="header">
  <div class="header-top">
    <div class="logo-area">
      <h1>EA AI Intelligence &mdash; Portfolio Rationalization Report</h1>
      <div class="sub">Enterprise Architecture · Application Portfolio Assessment · AI-Powered Advisory</div>
    </div>
    <div class="confidential">CONFIDENTIAL</div>
  </div>
  <div class="header-meta">
    <span>Generated: {gen_date}</span>
    <span>Powered by EA AI Intelligence</span>
    <span>Framework: TIME + 6R Rationalization Model</span>
  </div>
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
      <p style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;
        color:#666;margin-bottom:12px">TIME Classification</p>
      <table>
        <thead><tr><th>TIME</th><th>Count</th><th>% of Portfolio</th><th>Description</th></tr></thead>
        <tbody>{time_summary_rows}</tbody>
      </table>
    </div>
    <div>
      <p style="font-size:12px;font-weight:700;text-transform:uppercase;letter-spacing:.8px;
        color:#666;margin-bottom:12px">6R Action Breakdown</p>
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
    <thead>
      <tr>
        <th>Application</th><th>Vendor</th><th>Category</th>
        <th>Annual Cost</th><th>Users</th><th>Score</th>
        <th>Risk</th><th>Confidence</th><th>TIME</th><th>6R Action</th>
      </tr>
    </thead>
    <tbody>{tool_rows}</tbody>
  </table>
</div>

{self._dup_section(dup_rows) if duplications else ""}

<div class="footer">
  <span>EA AI Intelligence &mdash; Enterprise Architecture Advisory Platform</span>
  <span>CONFIDENTIAL &mdash; {datetime.now().strftime("%Y")}</span>
</div>
</div>
</body>
</html>"""

    # ─── Section builders ─────────────────────────────────────────────────────

    def _assessment_section(self, assessments: List[Dict]) -> str:
        if not assessments:
            return ""
        latest = assessments[-1]
        parts = []

        exec_sum = latest.get("executive_summary", "")
        if exec_sum:
            parts.append(f"""
<div class="section">
  <h2>Executive Summary</h2>
  <div class="exec-box">{exec_sum}</div>
</div>""")

        recs = latest.get("top_recommendations", [])
        if recs:
            cards = ""
            for r in recs[:5]:
                prio = r.get("priority", "Medium")
                eff = r.get("effort", "Medium")
                conf = r.get("confidence", "Medium")
                cards += f"""
<div class="rec-card">
  <div class="rec-header">
    <div class="rec-title">#{r.get('rank','')} {r.get('title','')}</div>
    <div class="rec-meta">
      <span class="badge badge-{prio.lower()}">{prio} Priority</span>
      <span class="badge badge-{eff.lower()}">Effort: {eff}</span>
      <span class="badge badge-{conf.lower()}">Confidence: {conf}</span>
    </div>
  </div>
  <div class="rec-desc">{r.get('description','')}</div>
  <div class="rec-impact">Impact: {r.get('impact','')} &bull; Timeline: {r.get('timeline','')}</div>
</div>"""
            parts.append(f"""
<div class="section">
  <h2>Top Priority Recommendations</h2>
  {cards}
</div>""")

        roadmap = latest.get("roadmap", {})
        if roadmap:
            def phase_items(key):
                items = roadmap.get(key, [])
                if isinstance(items, str):
                    items = [items]
                return "".join(f"<li>{i}</li>" for i in items)

            parts.append(f"""
<div class="section">
  <h2>Rationalization Roadmap</h2>
  <div class="roadmap">
    <div class="phase p1">
      <h3>Phase 1 &mdash; Quick Wins (0–3 Months)</h3>
      <ul>{phase_items("short_term")}</ul>
    </div>
    <div class="phase p2">
      <h3>Phase 2 &mdash; Strategic (3–12 Months)</h3>
      <ul>{phase_items("medium_term")}</ul>
    </div>
    <div class="phase p3">
      <h3>Phase 3 &mdash; Transformation (12–24 Months)</h3>
      <ul>{phase_items("long_term")}</ul>
    </div>
  </div>
</div>""")

        outcomes = latest.get("expected_outcomes", {})
        if outcomes:
            items = "".join(
                f"<tr><td><strong>{k.replace('_',' ').title()}</strong></td><td>{v}</td></tr>"
                for k, v in outcomes.items()
            )
            parts.append(f"""
<div class="section">
  <h2>Expected Business Outcomes</h2>
  <table><tbody>{items}</tbody></table>
</div>""")

        return "\n".join(parts)

    def _time_summary_rows(self, counts: Dict[str, int]) -> str:
        total = max(sum(counts.values()), 1)
        rows = ""
        for cat in ["INVEST", "TOLERATE", "MIGRATE", "ELIMINATE"]:
            c = counts.get(cat, 0)
            if c == 0:
                continue
            pct = round(c / total * 100)
            desc = TIME_DESCRIPTIONS.get(cat, "")
            rows += f"""<tr>
  <td><span class="badge badge-{cat.lower()}">{cat}</span></td>
  <td><strong>{c}</strong></td>
  <td>
    <div class="score-bar">
      <div class="bar"><div class="bar-fill" style="width:{pct}%"></div></div>
      <span>{pct}%</span>
    </div>
  </td>
  <td>{desc}</td>
</tr>"""
        return rows

    def _action_summary_rows(self, counts: Dict[str, int]) -> str:
        total = max(sum(counts.values()), 1)
        rows = ""
        for action in ["Retain", "Rehost", "Replatform", "Refactor", "Replace", "Retire"]:
            c = counts.get(action, 0)
            if c == 0:
                continue
            pct = round(c / total * 100)
            desc = ACTION_DESCRIPTIONS.get(action, "")
            rows += f"""<tr>
  <td><span class="badge badge-{action.lower()}">{action}</span></td>
  <td><strong>{c}</strong></td>
  <td>
    <div class="score-bar">
      <div class="bar"><div class="bar-fill" style="width:{pct}%"></div></div>
      <span>{pct}%</span>
    </div>
  </td>
  <td>{desc}</td>
</tr>"""
        return rows

    def _tool_rows(self, tools: List[Dict]) -> str:
        rows = ""
        for t in tools:
            action = t.get("rationalization_action", "TBD")
            time_cls = t.get("time_classification", "TOLERATE")
            score = t.get("composite_score", "—")
            risk = t.get("scores", {}).get("risk_score", "—")
            conf = t.get("confidence_level", "—")
            cost = f"${t.get('annual_cost', 0):,.0f}" if t.get("annual_cost") else "—"
            users = t.get("user_count", "—")
            rows += f"""<tr>
  <td><strong>{t.get('name','—')}</strong></td>
  <td>{t.get('vendor','—') or '—'}</td>
  <td>{t.get('category','—')}</td>
  <td>{cost}</td>
  <td>{users}</td>
  <td><strong>{score}</strong>/10</td>
  <td>{risk}/10</td>
  <td><span class="badge badge-{conf.lower() if conf != '—' else 'medium'}">{conf}</span></td>
  <td><span class="badge badge-{time_cls.lower()}">{time_cls}</span></td>
  <td><span class="badge badge-{action.lower()}">{action}</span></td>
</tr>"""
        return rows

    def _dup_rows(self, duplications: List[Dict]) -> str:
        rows = ""
        for d in duplications[:15]:
            savings = f"${d.get('potential_annual_savings', 0):,.0f}"
            prio = d.get("priority", "Low")
            rows += f"""<tr>
  <td>{d.get('category','—')}</td>
  <td>{d.get('tool_a','—')}</td>
  <td>{d.get('tool_b','—')}</td>
  <td><strong>{d.get('overlap_percentage',0)}%</strong></td>
  <td><strong>{d.get('retain_candidate','—')}</strong></td>
  <td>{d.get('consolidate_candidate','—')}</td>
  <td>{savings}</td>
  <td><span class="badge badge-{prio.lower()}">{prio}</span></td>
</tr>"""
        return rows

    def _dup_section(self, rows: str) -> str:
        return f"""
<div class="section">
  <h2>Duplication &amp; Consolidation Opportunities</h2>
  <table>
    <thead>
      <tr>
        <th>Category</th><th>Tool A</th><th>Tool B</th><th>Overlap</th>
        <th>Retain</th><th>Consolidate</th><th>Est. Savings</th><th>Priority</th>
      </tr>
    </thead>
    <tbody>{rows}</tbody>
  </table>
</div>"""

    # ─── PDF-safe HTML builder (no CSS Grid / flexbox / gradients) ────────────

    def _build_pdf_html(
        self,
        tools: List[Dict],
        duplications: List[Dict],
        assessments: List[Dict],
    ) -> str:
        gen_date = datetime.now().strftime("%d %B %Y %H:%M")
        total_cost = sum(t.get("annual_cost", 0) or 0 for t in tools)
        pot_savings = sum(d.get("potential_annual_savings", 0) or 0 for d in duplications)

        action_counts: Dict[str, int] = {}
        time_counts: Dict[str, int] = {}
        for t in tools:
            a = t.get("rationalization_action", "TBD")
            action_counts[a] = action_counts.get(a, 0) + 1
            tc = t.get("time_classification", "TOLERATE")
            time_counts[tc] = time_counts.get(tc, 0) + 1

        tool_rows = self._pdf_tool_rows(tools)
        time_rows = self._pdf_time_rows(time_counts, len(tools))
        action_rows = self._pdf_action_rows(action_counts, len(tools))
        dup_section = self._pdf_dup_section(duplications) if duplications else ""
        assessment_section = self._pdf_assessment_section(assessments)

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>
  @page {{ margin: 1.8cm 1.5cm; }}
  body {{ font-family: Helvetica, Arial, sans-serif; font-size: 10pt; color: #1a2340; }}
  h1 {{ font-size: 16pt; color: #0a1628; margin: 0 0 4pt 0; }}
  h2 {{ font-size: 12pt; color: #0a1628; border-bottom: 2pt solid #0063DC;
       padding-bottom: 4pt; margin: 18pt 0 8pt 0; }}
  h3 {{ font-size: 10pt; color: #003366; margin: 10pt 0 4pt 0; }}
  p  {{ margin: 4pt 0; line-height: 1.5; }}
  .header {{ background-color: #0a1628; color: #ffffff; padding: 14pt 16pt;
             margin-bottom: 12pt; }}
  .header h1 {{ color: #ffffff; font-size: 14pt; }}
  .header-sub {{ color: #aabbdd; font-size: 8pt; margin-top: 3pt; }}
  .header-meta {{ color: #8899bb; font-size: 8pt; margin-top: 6pt; }}
  .kpi-table {{ width: 100%; border-collapse: collapse; margin-bottom: 14pt; }}
  .kpi-table td {{ border: 1pt solid #d0d8ee; padding: 10pt 8pt;
                   text-align: center; background-color: #f8fbff; }}
  .kpi-val {{ font-size: 18pt; font-weight: bold; color: #0063DC; }}
  .kpi-lbl {{ font-size: 7pt; color: #666; text-transform: uppercase;
              letter-spacing: 0.5pt; margin-top: 3pt; }}
  table {{ width: 100%; border-collapse: collapse; font-size: 9pt; margin-bottom: 10pt; }}
  thead th {{ background-color: #0a1628; color: #ffffff; padding: 6pt 8pt;
              text-align: left; font-size: 8.5pt; }}
  tbody td {{ padding: 5pt 8pt; border-bottom: 0.5pt solid #e8edf8; }}
  tbody tr:nth-child(even) td {{ background-color: #f8fbff; }}
  .badge {{ display: inline; padding: 2pt 6pt; border-radius: 3pt;
            font-size: 8pt; font-weight: bold; }}
  .b-invest    {{ color: #155724; background-color: #d4edda; }}
  .b-tolerate  {{ color: #004085; background-color: #cce5ff; }}
  .b-migrate   {{ color: #856404; background-color: #fff3cd; }}
  .b-eliminate {{ color: #721c24; background-color: #f8d7da; }}
  .b-retain    {{ color: #155724; background-color: #d4edda; }}
  .b-rehost    {{ color: #004085; background-color: #cce5ff; }}
  .b-replatform{{ color: #856404; background-color: #fff3cd; }}
  .b-refactor  {{ color: #7d3c00; background-color: #fde8d8; }}
  .b-replace   {{ color: #721c24; background-color: #f8d7da; }}
  .b-retire    {{ color: #383d41; background-color: #e2e3e5; }}
  .b-high      {{ color: #721c24; background-color: #f8d7da; }}
  .b-medium    {{ color: #856404; background-color: #fff3cd; }}
  .b-low       {{ color: #155724; background-color: #d4edda; }}
  .b-critical  {{ color: #ffffff; background-color: #c0392b; }}
  .exec-box {{ background-color: #f0f4fa; border-left: 3pt solid #0063DC;
               padding: 10pt 12pt; margin: 6pt 0; font-size: 9.5pt; line-height: 1.6; }}
  .rec-card {{ border: 0.5pt solid #ccd5ee; padding: 8pt 10pt;
               margin-bottom: 8pt; border-left: 3pt solid #0063DC;
               background-color: #f8fbff; }}
  .rec-title {{ font-weight: bold; font-size: 10pt; color: #0a1628; }}
  .rec-desc  {{ font-size: 9pt; color: #444; margin: 4pt 0; line-height: 1.5; }}
  .rec-impact{{ font-size: 8.5pt; color: #0063DC; font-style: italic; }}
  .footer {{ color: #8899bb; font-size: 8pt; text-align: center;
             border-top: 0.5pt solid #ccd; padding-top: 6pt; margin-top: 14pt; }}
  .conf {{ color: #ffffff; }}
</style>
</head>
<body>

<div class="header">
  <h1>EA AI Intelligence &mdash; Portfolio Rationalization Report</h1>
  <div class="header-sub">Enterprise Architecture &nbsp;&bull;&nbsp; Application Portfolio Assessment &nbsp;&bull;&nbsp; AI-Powered Advisory</div>
  <div class="header-meta">Generated: {gen_date} &nbsp;&bull;&nbsp; Framework: TIME + 6R Rationalization Model &nbsp;&bull;&nbsp; CONFIDENTIAL</div>
</div>

<table class="kpi-table">
  <tr>
    <td><div class="kpi-val">{len(tools)}</div><div class="kpi-lbl">Applications Assessed</div></td>
    <td><div class="kpi-val">${total_cost:,.0f}</div><div class="kpi-lbl">Total Annual Spend</div></td>
    <td><div class="kpi-val">{len(duplications)}</div><div class="kpi-lbl">Overlap Pairs Found</div></td>
    <td><div class="kpi-val">${pot_savings:,.0f}</div><div class="kpi-lbl">Est. Annual Savings</div></td>
  </tr>
</table>

<h2>Portfolio Classification Summary</h2>

<h3>TIME Classification</h3>
<table>
  <thead><tr><th>TIME</th><th>Count</th><th>% of Portfolio</th><th>Description</th></tr></thead>
  <tbody>{time_rows}</tbody>
</table>

<h3>6R Action Breakdown</h3>
<table>
  <thead><tr><th>6R Action</th><th>Count</th><th>% of Portfolio</th><th>Description</th></tr></thead>
  <tbody>{action_rows}</tbody>
</table>

{assessment_section}

<h2>Application Portfolio Detail</h2>
<table>
  <thead>
    <tr>
      <th>Application</th><th>Vendor</th><th>Category</th>
      <th>Annual Cost</th><th>Users</th><th>Score</th>
      <th>Risk</th><th>Confidence</th><th>TIME</th><th>6R Action</th>
    </tr>
  </thead>
  <tbody>{tool_rows}</tbody>
</table>

{dup_section}

<div class="footer">
  EA AI Intelligence &mdash; Enterprise Architecture Advisory Platform &nbsp;&bull;&nbsp;
  CONFIDENTIAL &mdash; {datetime.now().strftime("%Y")}
</div>

</body>
</html>"""

    # ─── PDF row builders (simpler, no nested div/span issues) ───────────────

    def _pdf_tool_rows(self, tools: List[Dict]) -> str:
        rows = ""
        for t in tools:
            action = t.get("rationalization_action", "TBD")
            time_cls = t.get("time_classification", "TOLERATE")
            score = t.get("composite_score", "—")
            risk = t.get("scores", {}).get("risk_score", "—")
            conf = t.get("confidence_level", "—")
            cost = f"${t.get('annual_cost', 0):,.0f}" if t.get("annual_cost") else "—"
            users = t.get("user_count", "—")
            tc_cls = f"b-{time_cls.lower()}"
            ac_cls = f"b-{action.lower()}"
            cf_cls = f"b-{conf.lower()}" if conf != "—" else "b-medium"
            rows += f"""<tr>
  <td><strong>{t.get('name','—')}</strong></td>
  <td>{t.get('vendor','—') or '—'}</td>
  <td>{t.get('category','—')}</td>
  <td>{cost}</td><td>{users}</td>
  <td><strong>{score}</strong>/10</td>
  <td>{risk}/10</td>
  <td><span class="badge {cf_cls}">{conf}</span></td>
  <td><span class="badge {tc_cls}">{time_cls}</span></td>
  <td><span class="badge {ac_cls}">{action}</span></td>
</tr>"""
        return rows

    def _pdf_time_rows(self, counts: Dict[str, int], total_apps: int) -> str:
        total = max(total_apps, 1)
        rows = ""
        for cat in ["INVEST", "TOLERATE", "MIGRATE", "ELIMINATE"]:
            c = counts.get(cat, 0)
            if c == 0:
                continue
            pct = round(c / total * 100)
            desc = TIME_DESCRIPTIONS.get(cat, "")
            cls = f"b-{cat.lower()}"
            rows += f"""<tr>
  <td><span class="badge {cls}">{cat}</span></td>
  <td><strong>{c}</strong></td><td>{pct}%</td><td>{desc}</td>
</tr>"""
        return rows

    def _pdf_action_rows(self, counts: Dict[str, int], total_apps: int) -> str:
        total = max(total_apps, 1)
        rows = ""
        for action in ["Retain", "Rehost", "Replatform", "Refactor", "Replace", "Retire"]:
            c = counts.get(action, 0)
            if c == 0:
                continue
            pct = round(c / total * 100)
            desc = ACTION_DESCRIPTIONS.get(action, "")
            cls = f"b-{action.lower()}"
            rows += f"""<tr>
  <td><span class="badge {cls}">{action}</span></td>
  <td><strong>{c}</strong></td><td>{pct}%</td><td>{desc}</td>
</tr>"""
        return rows

    def _pdf_assessment_section(self, assessments: List[Dict]) -> str:
        if not assessments:
            return ""
        latest = assessments[-1]
        parts = []

        exec_sum = latest.get("executive_summary", "")
        if exec_sum:
            parts.append(f'<h2>Executive Summary</h2><div class="exec-box">{exec_sum}</div>')

        recs = latest.get("top_recommendations", [])
        if recs:
            cards = ""
            for r in recs[:5]:
                prio = r.get("priority", "Medium")
                cls = f"b-{prio.lower()}"
                cards += f"""<div class="rec-card">
  <div class="rec-title">#{r.get('rank','')} {r.get('title','')}</div>
  <div style="margin:3pt 0"><span class="badge {cls}">{prio} Priority</span>
    &nbsp; Effort: {r.get('effort','—')} &nbsp; Confidence: {r.get('confidence','—')}</div>
  <div class="rec-desc">{r.get('description','')}</div>
  <div class="rec-impact">Impact: {r.get('impact','')} &bull; Timeline: {r.get('timeline','')}</div>
</div>"""
            parts.append(f'<h2>Top Priority Recommendations</h2>{cards}')

        roadmap = latest.get("roadmap", {})
        if roadmap:
            def phase_rows(key):
                items = roadmap.get(key, [])
                if isinstance(items, str):
                    items = [items]
                return "".join(f"<tr><td>{i}</td></tr>" for i in items)

            parts.append(f"""<h2>Rationalization Roadmap</h2>
<h3>Phase 1 &mdash; Quick Wins (0&#8211;3 Months)</h3>
<table><tbody>{phase_rows("short_term")}</tbody></table>
<h3>Phase 2 &mdash; Strategic (3&#8211;12 Months)</h3>
<table><tbody>{phase_rows("medium_term")}</tbody></table>
<h3>Phase 3 &mdash; Transformation (12&#8211;24 Months)</h3>
<table><tbody>{phase_rows("long_term")}</tbody></table>""")

        outcomes = latest.get("expected_outcomes", {})
        if outcomes:
            rows = "".join(
                f"<tr><td><strong>{k.replace('_',' ').title()}</strong></td><td>{v}</td></tr>"
                for k, v in outcomes.items()
            )
            parts.append(f'<h2>Expected Business Outcomes</h2><table><tbody>{rows}</tbody></table>')

        return "\n".join(parts)

    def _pdf_dup_section(self, duplications: List[Dict]) -> str:
        rows = ""
        for d in duplications[:15]:
            savings = f"${d.get('potential_annual_savings', 0):,.0f}"
            prio = d.get("priority", "Low")
            cls = f"b-{prio.lower()}"
            rows += f"""<tr>
  <td>{d.get('category','—')}</td>
  <td>{d.get('tool_a','—')}</td><td>{d.get('tool_b','—')}</td>
  <td><strong>{d.get('overlap_percentage',0)}%</strong></td>
  <td><strong>{d.get('retain_candidate','—')}</strong></td>
  <td>{d.get('consolidate_candidate','—')}</td>
  <td>{savings}</td>
  <td><span class="badge {cls}">{prio}</span></td>
</tr>"""
        return f"""<h2>Duplication &amp; Consolidation Opportunities</h2>
<table>
  <thead><tr>
    <th>Category</th><th>Tool A</th><th>Tool B</th><th>Overlap</th>
    <th>Retain</th><th>Consolidate</th><th>Est. Savings</th><th>Priority</th>
  </tr></thead>
  <tbody>{rows}</tbody>
</table>"""

    # ═══════════════════════════════════════════════════════════════════════════
    # FULL PIPELINE PDF  (TIME + MAPPING + MATURITY + INSIGHTS)
    # ═══════════════════════════════════════════════════════════════════════════

    _PDF_BASE_STYLES = """
  @page { margin: 1.8cm 1.5cm; }
  body { font-family: Helvetica, Arial, sans-serif; font-size: 10pt; color: #1a2340; }
  h1 { font-size: 15pt; color: #0a1628; margin: 0 0 4pt 0; }
  h2 { font-size: 12pt; color: #0a1628; border-bottom: 2pt solid #0063DC;
       padding-bottom: 4pt; margin: 16pt 0 8pt 0; }
  h3 { font-size: 10pt; color: #003366; margin: 10pt 0 4pt 0; }
  p  { margin: 4pt 0; line-height: 1.5; }
  .header { background-color: #0a1628; color: #ffffff; padding: 14pt 16pt; margin-bottom: 12pt; }
  .header h1 { color: #ffffff; font-size: 14pt; }
  .header-sub { color: #aabbdd; font-size: 8pt; margin-top: 3pt; }
  .header-meta { color: #8899bb; font-size: 8pt; margin-top: 6pt; }
  .section-label { font-size: 8pt; font-weight: bold; text-transform: uppercase;
                   letter-spacing: 1pt; color: #0063DC; margin: 14pt 0 4pt 0; }
  .kpi-table { width: 100%; border-collapse: collapse; margin-bottom: 12pt; }
  .kpi-table td { border: 1pt solid #d0d8ee; padding: 10pt 8pt;
                  text-align: center; background-color: #f8fbff; }
  .kpi-val { font-size: 18pt; font-weight: bold; color: #0063DC; }
  .kpi-lbl { font-size: 7pt; color: #666; text-transform: uppercase;
             letter-spacing: 0.5pt; margin-top: 3pt; }
  table { width: 100%; border-collapse: collapse; font-size: 9pt; margin-bottom: 10pt; }
  thead th { background-color: #0a1628; color: #ffffff; padding: 6pt 8pt;
             text-align: left; font-size: 8.5pt; }
  tbody td { padding: 5pt 8pt; border-bottom: 0.5pt solid #e8edf8; }
  tbody tr:nth-child(even) td { background-color: #f8fbff; }
  .badge { display: inline; padding: 2pt 6pt; border-radius: 3pt;
           font-size: 8pt; font-weight: bold; }
  .b-invest    { color: #155724; background-color: #d4edda; }
  .b-tolerate  { color: #004085; background-color: #cce5ff; }
  .b-migrate   { color: #856404; background-color: #fff3cd; }
  .b-eliminate { color: #721c24; background-color: #f8d7da; }
  .b-retain    { color: #155724; background-color: #d4edda; }
  .b-rehost    { color: #004085; background-color: #cce5ff; }
  .b-replatform{ color: #856404; background-color: #fff3cd; }
  .b-refactor  { color: #7d3c00; background-color: #fde8d8; }
  .b-replace   { color: #721c24; background-color: #f8d7da; }
  .b-retire    { color: #383d41; background-color: #e2e3e5; }
  .b-high      { color: #721c24; background-color: #f8d7da; }
  .b-medium    { color: #856404; background-color: #fff3cd; }
  .b-low       { color: #155724; background-color: #d4edda; }
  .b-critical  { color: #ffffff; background-color: #c0392b; }
  .b-initial   { color: #721c24; background-color: #f8d7da; }
  .b-managed   { color: #856404; background-color: #fff3cd; }
  .b-defined   { color: #004085; background-color: #cce5ff; }
  .b-quantitatively-managed { color: #155724; background-color: #d4edda; }
  .b-optimizing{ color: #ffffff; background-color: #00a651; }
  .exec-box { background-color: #f0f4fa; border-left: 3pt solid #0063DC;
              padding: 10pt 12pt; margin: 6pt 0; font-size: 9.5pt; line-height: 1.6; }
  .rec-card { border: 0.5pt solid #ccd5ee; padding: 8pt 10pt;
              margin-bottom: 8pt; border-left: 3pt solid #0063DC;
              background-color: #f8fbff; }
  .rec-title { font-weight: bold; font-size: 10pt; color: #0a1628; }
  .rec-desc  { font-size: 9pt; color: #444; margin: 4pt 0; line-height: 1.5; }
  .rec-impact{ font-size: 8.5pt; color: #0063DC; font-style: italic; }
  .maturity-bar-bg { background-color: #e8edf8; height: 8pt; width: 100%; }
  .info-box { background-color: #f8fbff; border: 0.5pt solid #ccd5ee;
              padding: 8pt 12pt; margin: 6pt 0; font-size: 9pt; line-height: 1.5; }
  .footer { color: #8899bb; font-size: 8pt; text-align: center;
            border-top: 0.5pt solid #ccd; padding-top: 6pt; margin-top: 14pt; }
"""

    def _build_pipeline_pdf_html(self, pipeline: Dict) -> str:
        gen_date = datetime.now().strftime("%d %B %Y %H:%M")
        summary = pipeline.get("pipeline_summary", {})
        time_data = pipeline.get("TIME", {})
        mapping_data = pipeline.get("MAPPING", {})
        maturity_data = pipeline.get("MATURITY", {})
        insights_data = pipeline.get("INSIGHTS", {})

        apps = time_data.get("applications", [])
        dups = time_data.get("duplications", [])
        time_summary = time_data.get("portfolio_summary", {})
        time_assessment = time_data.get("assessment", {})

        total_cost = time_summary.get("total_annual_cost", 0)
        pot_savings = time_summary.get("potential_savings", 0)
        maturity_score = maturity_data.get("overall_maturity_score", "—")
        maturity_level = maturity_data.get("maturity_level", "—")
        overall_risk = insights_data.get("risk_profile", {}).get("overall_risk", "—")

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8"/>
<style>{self._PDF_BASE_STYLES}</style>
</head>
<body>

<div class="header">
  <h1>EA AI Intelligence &mdash; Full Enterprise Architecture Report</h1>
  <div class="header-sub">
    Portfolio Rationalization &bull; Dependency Analysis &bull;
    EA Maturity Assessment &bull; Executive Intelligence
  </div>
  <div class="header-meta">
    Generated: {gen_date} &bull;
    Stages: {" → ".join(summary.get("stages_completed", []))} &bull; CONFIDENTIAL
  </div>
</div>

<table class="kpi-table">
  <tr>
    <td><div class="kpi-val">{len(apps)}</div><div class="kpi-lbl">Apps Assessed</div></td>
    <td><div class="kpi-val">${total_cost:,.0f}</div><div class="kpi-lbl">Total Annual Spend</div></td>
    <td><div class="kpi-val">{summary.get("flagged_for_action", 0)}</div><div class="kpi-lbl">Apps Flagged</div></td>
    <td><div class="kpi-val">${pot_savings:,.0f}</div><div class="kpi-lbl">Potential Savings</div></td>
    <td><div class="kpi-val">{maturity_score}/5</div><div class="kpi-lbl">EA Maturity Score</div></td>
    <td><div class="kpi-val">{overall_risk}</div><div class="kpi-lbl">Overall Risk</div></td>
  </tr>
</table>

{self._pipeline_insights_section(insights_data)}
{self._pipeline_time_section(apps, dups, time_summary, time_assessment)}
{self._pipeline_mapping_section(mapping_data)}
{self._pipeline_maturity_section(maturity_data)}
{self._pipeline_insights_recs_section(insights_data)}

<div class="footer">
  EA AI Intelligence &mdash; Full Enterprise Architecture Report &bull;
  CONFIDENTIAL &bull; {datetime.now().strftime("%Y")}
</div>

</body>
</html>"""

    def _pipeline_insights_section(self, insights: Dict) -> str:
        if not insights or "error" in insights:
            return ""
        exec_sum = insights.get("executive_summary", "")
        fin = insights.get("financial_impact", {})
        risk = insights.get("risk_profile", {})
        quick_wins = insights.get("quick_wins", [])

        fin_rows = "".join(
            f"<tr><td><strong>{k.replace('_',' ').title()}</strong></td><td>{v}</td></tr>"
            for k, v in fin.items() if v
        ) if fin else ""

        risk_rows = ""
        for r in risk.get("top_risks", [])[:5]:
            risk_rows += (
                f"<tr><td><strong>{r.get('risk','')}</strong></td>"
                f"<td>{r.get('impact','')}</td><td>{r.get('mitigation','')}</td></tr>"
            )

        qw_rows = "".join(f"<tr><td>{w}</td></tr>" for w in quick_wins[:5])

        return f"""
<h2>Executive Intelligence Summary</h2>
{f'<div class="exec-box">{exec_sum}</div>' if exec_sum else ""}

{"<h3>Financial Impact</h3><table><tbody>" + fin_rows + "</tbody></table>" if fin_rows else ""}

{"<h3>Top Risks</h3><table><thead><tr><th>Risk</th><th>Impact</th><th>Mitigation</th></tr></thead><tbody>" + risk_rows + "</tbody></table>" if risk_rows else ""}

{"<h3>Quick Wins</h3><table><tbody>" + qw_rows + "</tbody></table>" if qw_rows else ""}
"""

    def _pipeline_time_section(
        self, apps: List[Dict], dups: List[Dict], summary: Dict, assessment: Dict
    ) -> str:
        time_counts = summary.get("time_breakdown", {})
        total = max(len(apps), 1)

        time_rows = ""
        for cat in ["INVEST", "TOLERATE", "MIGRATE", "ELIMINATE"]:
            c = time_counts.get(cat, 0)
            if not c:
                continue
            pct = round(c / total * 100)
            time_rows += (
                f"<tr><td><span class='badge b-{cat.lower()}'>{cat}</span></td>"
                f"<td><strong>{c}</strong></td><td>{pct}%</td>"
                f"<td>{TIME_DESCRIPTIONS.get(cat,'')}</td></tr>"
            )

        tool_rows = self._pdf_tool_rows(apps)

        dup_section = self._pdf_dup_section(dups) if dups else ""

        # Roadmap from TIME assessment
        roadmap_html = ""
        rm = assessment.get("roadmap", {})
        if rm:
            def phase_items(key):
                items = rm.get(key, [])
                return "".join(f"<tr><td>{i}</td></tr>" for i in (items if isinstance(items, list) else [items]))
            roadmap_html = f"""
<h3>Rationalization Roadmap</h3>
<h3>Phase 1 (0-3 months)</h3><table><tbody>{phase_items("short_term")}</tbody></table>
<h3>Phase 2 (3-12 months)</h3><table><tbody>{phase_items("medium_term")}</tbody></table>
<h3>Phase 3 (12-24 months)</h3><table><tbody>{phase_items("long_term")}</tbody></table>"""

        exec_sum = assessment.get("executive_summary", "")

        return f"""
<h2>Stage 1 — Portfolio Rationalization (TIME)</h2>
{f'<div class="exec-box">{exec_sum}</div>' if exec_sum else ""}

<h3>TIME Classification Breakdown</h3>
<table>
  <thead><tr><th>TIME</th><th>Count</th><th>%</th><th>Description</th></tr></thead>
  <tbody>{time_rows}</tbody>
</table>

<h3>Application Detail</h3>
<table>
  <thead><tr>
    <th>Application</th><th>Category</th><th>Annual Cost</th>
    <th>Users</th><th>Score</th><th>TIME</th><th>6R</th><th>Confidence</th>
  </tr></thead>
  <tbody>{self._pdf_tool_rows_compact(apps)}</tbody>
</table>

{dup_section}
{roadmap_html}
"""

    def _pdf_tool_rows_compact(self, tools: List[Dict]) -> str:
        rows = ""
        for t in tools:
            action = t.get("rationalization_action", "TBD")
            time_cls = t.get("time_classification", "TOLERATE")
            score = t.get("composite_score", "—")
            conf = t.get("confidence_level", "—")
            cost = f"${t.get('annual_cost', 0):,.0f}" if t.get("annual_cost") else "—"
            users = t.get("user_count", "—")
            rows += f"""<tr>
  <td><strong>{t.get('name','—')}</strong></td>
  <td>{t.get('category','—')}</td><td>{cost}</td><td>{users}</td>
  <td><strong>{score}</strong>/10</td>
  <td><span class="badge b-{time_cls.lower()}">{time_cls}</span></td>
  <td><span class="badge b-{action.lower()}">{action}</span></td>
  <td><span class="badge b-{conf.lower() if conf != '—' else 'medium'}">{conf}</span></td>
</tr>"""
        return rows

    def _pipeline_mapping_section(self, mapping: Dict) -> str:
        if not mapping or mapping.get("skipped"):
            reason = mapping.get("reason", "No apps flagged for ELIMINATE/MIGRATE.")
            return f"""
<h2>Stage 2 — Dependency &amp; Impact Analysis (MAPPING)</h2>
<div class="info-box">{reason}</div>
"""
        overall = mapping.get("overall_impact_level", "—")
        pipeline_ctx = mapping.get("pipeline_context", "")
        migration_order = mapping.get("recommended_migration_order", [])
        cross_risks = mapping.get("cross_app_risks", [])
        quick_wins = mapping.get("quick_wins", [])
        app_analyses = mapping.get("app_analyses", [])

        app_rows = ""
        for a in app_analyses:
            impact = a.get("impact_level", "—")
            coupling = a.get("coupling_score", "—")
            tc = a.get("time_classification", "—")
            app_rows += f"""<tr>
  <td><strong>{a.get('app_name','—')}</strong></td>
  <td><span class="badge b-{tc.lower()}">{tc}</span></td>
  <td><span class="badge b-{impact.lower()}">{impact}</span></td>
  <td>{coupling}/10</td>
  <td>{", ".join(a.get("direct_dependencies",[]) or ["—"])}</td>
  <td>{a.get("recommended_sequence","—")}</td>
</tr>"""

        order_rows = "".join(
            f"<tr><td>{i+1}</td><td>{app}</td></tr>"
            for i, app in enumerate(migration_order)
        )
        risk_rows = "".join(f"<tr><td>{r}</td></tr>" for r in cross_risks[:6])
        qw_rows = "".join(f"<tr><td>{w}</td></tr>" for w in (quick_wins if isinstance(quick_wins, list) else [quick_wins])[:3])

        return f"""
<h2>Stage 2 — Dependency &amp; Impact Analysis (MAPPING)</h2>
<p><strong>Overall Impact Level:</strong> <span class="badge b-{overall.lower()}">{overall}</span></p>
{f'<div class="info-box">{pipeline_ctx}</div>' if pipeline_ctx else ""}

<h3>Per-Application Analysis</h3>
<table>
  <thead><tr>
    <th>Application</th><th>TIME</th><th>Impact</th>
    <th>Coupling</th><th>Direct Dependencies</th><th>Migration Sequence</th>
  </tr></thead>
  <tbody>{app_rows}</tbody>
</table>

{"<h3>Recommended Migration Order</h3><table><thead><tr><th>#</th><th>Application</th></tr></thead><tbody>" + order_rows + "</tbody></table>" if order_rows else ""}
{"<h3>Cross-App Risks</h3><table><tbody>" + risk_rows + "</tbody></table>" if risk_rows else ""}
{"<h3>Quick Wins (Lowest Coupling)</h3><table><tbody>" + qw_rows + "</tbody></table>" if qw_rows else ""}
"""

    def _pipeline_maturity_section(self, maturity: Dict) -> str:
        if not maturity:
            return ""
        score = maturity.get("overall_maturity_score", "—")
        level = maturity.get("maturity_level", "—")
        dims = maturity.get("dimensions", {})
        priorities = maturity.get("top_priorities", [])
        roadmap = maturity.get("roadmap", [])

        level_cls = f"b-{level.lower().replace(' ', '-')}" if level != "—" else "b-medium"

        dim_rows = ""
        for dim_key, dim_val in dims.items():
            if not isinstance(dim_val, dict):
                continue
            ds = dim_val.get("score", "—")
            gaps = ", ".join(dim_val.get("gaps", [])[:2]) or "—"
            dim_rows += (
                f"<tr><td><strong>{dim_key.replace('_',' ').title()}</strong></td>"
                f"<td><strong>{ds}/5</strong></td><td>{gaps}</td></tr>"
            )

        priority_rows = "".join(f"<tr><td>{p}</td></tr>" for p in priorities[:5])

        rm_rows = ""
        for phase in roadmap[:3]:
            actions = phase.get("actions", [])
            acts = "; ".join(actions[:3]) if actions else "—"
            rm_rows += f"<tr><td><strong>{phase.get('phase','')}</strong></td><td>{acts}</td></tr>"

        return f"""
<h2>Stage 3 — EA Maturity Assessment (MATURITY)</h2>
<p>
  <strong>Overall Score:</strong> {score}/5 &nbsp;&nbsp;
  <strong>Level:</strong> <span class="badge {level_cls}">{level}</span>
</p>

{"<h3>Dimension Scores</h3><table><thead><tr><th>Dimension</th><th>Score</th><th>Key Gaps</th></tr></thead><tbody>" + dim_rows + "</tbody></table>" if dim_rows else ""}
{"<h3>Top Improvement Priorities</h3><table><tbody>" + priority_rows + "</tbody></table>" if priority_rows else ""}
{"<h3>Maturity Improvement Roadmap</h3><table><thead><tr><th>Phase</th><th>Key Actions</th></tr></thead><tbody>" + rm_rows + "</tbody></table>" if rm_rows else ""}
"""

    def _pipeline_insights_recs_section(self, insights: Dict) -> str:
        if not insights:
            return ""
        recs = insights.get("strategic_recommendations", [])
        kpis = insights.get("kpis", [])

        if not recs and not kpis:
            return ""

        rec_cards = ""
        for r in recs[:6]:
            prio = str(r.get("effort", "Medium"))
            rec_cards += f"""<div class="rec-card">
  <div class="rec-title">Priority {r.get('priority','')} — {r.get('recommendation','')}</div>
  <div class="rec-desc">{r.get('business_value','')}</div>
  <div class="rec-impact">Effort: {r.get('effort','—')} &bull; Timeline: {r.get('timeline','—')}</div>
</div>"""

        kpi_rows = "".join(
            f"<tr><td><strong>{k.get('metric','')}</strong></td>"
            f"<td>{k.get('current','')}</td><td>{k.get('target','')}</td>"
            f"<td>{k.get('timeframe','')}</td></tr>"
            for k in kpis[:6]
        )

        return f"""
<h2>Stage 4 — Strategic Recommendations &amp; KPIs (INSIGHTS)</h2>
{rec_cards}
{"<h3>Key Performance Indicators</h3><table><thead><tr><th>Metric</th><th>Current</th><th>Target</th><th>Timeframe</th></tr></thead><tbody>" + kpi_rows + "</tbody></table>" if kpi_rows else ""}
"""
