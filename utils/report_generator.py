import io
import math
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import List, Dict, Any
from fpdf import FPDF

# Vercel/serverless runs in UTC — render report timestamps in IST instead
IST = timezone(timedelta(hours=5, minutes=30))


def _now():
    return datetime.now(IST)


# ── Safe string helper (fpdf2 Helvetica only supports Latin-1) ────────────────

_UNICODE_MAP = {
    '–': '-',    # en dash
    '—': '-',    # em dash
    '―': '-',    # horizontal bar
    '‘': "'",    # left single quote
    '’': "'",    # right single quote
    '“': '"',    # left double quote
    '”': '"',    # right double quote
    '•': '-',    # bullet
    '…': '...',  # ellipsis
    '→': '->',   # right arrow
    '←': '<-',   # left arrow
    '↑': '^',    # up arrow
    '↓': 'v',    # down arrow
    '≈': '~',    # almost equal / approx
    '≠': '!=',   # not equal
    '≤': '<=',   # less-than or equal
    '≥': '>=',   # greater-than or equal
    '×': 'x',    # multiplication sign
    '·': '.',    # middle dot
    '−': '-',    # minus sign
    ' ': ' ',    # non-breaking space
    '±': '+/-',  # plus-minus
    '™': '(TM)', # trade mark
    '®': '(R)',  # registered
    '©': '(C)',  # copyright
    '†': '+',    # dagger
    '‡': '++',   # double dagger
    '●': '-',    # black circle bullet
    '►': '>',    # black right-pointing triangle
    '✔': 'v',    # heavy check mark
    '✘': 'x',    # heavy ballot x
}


def _safe_str(val, maxlen: int = 0) -> str:
    """Convert any value to a Latin-1–safe string for fpdf2 built-in fonts."""
    if val is None:
        return '-'
    s = str(val)
    for orig, rep in _UNICODE_MAP.items():
        s = s.replace(orig, rep)
    # Replace all remaining non-Latin-1 codepoints char by char
    out = []
    for ch in s:
        cp = ord(ch)
        if cp < 128 or (160 <= cp <= 255):
            out.append(ch)   # ASCII or Latin-1 supplement — safe
        elif cp in (0x2014, 0x2013, 0x2015, 0x2012):
            out.append('-')   # em/en dash family
        elif cp in (0x2019, 0x2018, 0x02bc):
            out.append("'")   # smart single quotes
        elif cp in (0x201c, 0x201d, 0x201e):
            out.append('"')   # smart double quotes
        elif cp == 0x2026:
            out.append('...')  # ellipsis
        elif cp == 0x20ac:
            out.append('EUR')  # euro sign
        elif cp == 0x2248:
            out.append('~')    # almost equal / approx
        elif cp in (0x2264, 0x2266):
            out.append('<=')   # less-than or equal
        elif cp in (0x2265, 0x2267):
            out.append('>=')   # greater-than or equal
        elif cp == 0x2260:
            out.append('!=')   # not equal
        elif cp == 0x00b1:
            out.append('+/-')  # plus-minus (Latin-1 but keep explicit)
        elif cp in (0x2192, 0x21d2):
            out.append('->')   # right arrow
        elif cp in (0x2190, 0x21d0):
            out.append('<-')   # left arrow
        elif cp in (0x2191, 0x21d1):
            out.append('^')    # up arrow
        elif cp in (0x2193, 0x21d3):
            out.append('v')    # down arrow
        elif cp in (0x2022, 0x25cf, 0x25e6):
            out.append('-')    # bullets
        elif cp == 0x2122:
            out.append('(TM)') # trademark
        elif cp == 0x00a9:
            out.append('(C)')  # copyright
        elif cp == 0x00ae:
            out.append('(R)')  # registered
        elif cp < 0x2500:
            out.append(' ')    # most other unicode → space (cleaner than ?)
        else:
            out.append('')     # drop box-drawing, emoji, etc.
    s = ''.join(out)
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

ACTION_DESC = {
    "Retain":     "Strategic and healthy -- no immediate action required",
    "Rehost":     "Lift-and-shift to cloud infrastructure",
    "Replatform": "Minor modernisation leveraging cloud-native services",
    "Refactor":   "Significant redesign and re-architecture required",
    "Replace":    "Better market alternative exists -- plan migration",
    "Retire":     "Decommission -- low value, high cost, or redundant",
}

# ── EA Maturity dimension context descriptions ────────────────────────────────
DIM_EA_CONTEXT = {
    "vision_and_strategy": (
        "Evaluates whether EA has a clear vision, roadmap and investment strategy "
        "aligned to business objectives. High maturity enables board-level EA "
        "governance and long-term architecture planning across the enterprise."
    ),
    "organization": (
        "Assesses dedicated EA roles, governance committees and communities of "
        "practice. Mature organisations have clear accountability structures with "
        "cross-functional teams driving continuous architecture improvement."
    ),
    "leadership_and_governance": (
        "Measures how EA principles are enforced enterprise-wide and whether "
        "technology decisions align to strategic goals through executive sponsorship, "
        "formal ARB processes and structured review mechanisms."
    ),
    "behaviour_and_culture": (
        "Reflects EA awareness and adoption depth. High maturity embeds architecture "
        "thinking into project delivery, transformation programmes and everyday "
        "technology decisions across all business functions."
    ),
    "metrics_and_analysis": (
        "Evaluates use of KPIs and data analytics to measure EA programme "
        "effectiveness. Mature organisations use EA metrics to drive investment "
        "prioritisation, risk reduction and continuous improvement cycles."
    ),
    "policy_and_standards": (
        "Governs technology standards, architecture principles and compliance "
        "frameworks. High maturity ensures enterprise-wide enforcement with "
        "automated governance checkpoints, audit trails and lifecycle controls."
    ),
    "enabling_processes": (
        "Covers EA tooling, application lifecycle management, security-by-design "
        "and infrastructure maturity. High maturity means EA processes are "
        "automated and tools integrated across domains for real-time insight."
    ),
    "tools_and_technology": (
        "Assesses EA tool adoption, repository quality and governance automation. "
        "High maturity enables data-driven, real-time architecture decisions at "
        "enterprise scale, reducing manual governance effort significantly."
    ),
}

PILLAR_EA_DESC = {
    "Vision & Strategy": (
        "The strategic direction and ambition for EA capability. "
        "Covers EA roadmap, investment priorities and alignment to business strategy."
    ),
    "People": (
        "The human capital dimension: roles, skills, governance culture and "
        "leadership commitment to EA. Critical enabler for consistent adoption."
    ),
    "Processes": (
        "The operational backbone: standards, policies, metrics and enabling "
        "processes that govern how architecture is practised and measured."
    ),
    "Technology": (
        "The tooling and technology infrastructure supporting EA practice: "
        "repositories, modelling tools, automation and real-time decision support."
    ),
}

MATURITY_BAND_DESC = {
    "High":   "EA practices are embedded, enterprise-wide and continuously improved. Architecture drives strategic decisions.",
    "Medium": "EA processes are defined and partially adopted. Inconsistent enforcement limits strategic impact.",
    "Low":    "EA is ad-hoc and reactive. No formal capability exists. Immediate investment in EA foundations is required.",
}


def _badge(key: str):
    k = key.lower().replace(" ", "-")
    return BADGE.get(k, BADGE["tbd"])


def _fmt_kpi(val: str) -> str:
    """Shorten large numbers so they fit KPI card cells (e.g. $1,234,567 → $1.2M)."""
    s = str(val).strip()
    prefix = "$" if s.startswith("$") else ""
    try:
        num = float(s.replace("$", "").replace(",", "").replace(" ", ""))
        if abs(num) >= 1_000_000:
            return f"{prefix}{num/1_000_000:.1f}M"
        if abs(num) >= 100_000:
            return f"{prefix}{num/1_000:.0f}K"
        if abs(num) >= 10_000:
            return f"{prefix}{num/1_000:.1f}K"
        if prefix:
            return f"${num:,.0f}"
    except (ValueError, TypeError):
        pass
    return s if len(s) <= 12 else s[:11] + "…"


def _synthesize_recommendations(apps, arb_data, mapping_data, maturity_data,
                                 total_cost, pot_savings, overall_risk):
    """Builds a cross-stage 'Combined Intelligence' narrative, recommendation
    set and quick wins from whatever stage data is actually available
    (TIME / ARB / MAPPING / MATURITY). Used as a fallback for Section 6 when
    the INSIGHTS agent itself returned no strategic_recommendations, so the
    report's final section is never left blank in either PDF or HTML.
    Shared by both report builders so the two outputs stay identical.
    """
    apps          = apps or []
    arb_data      = arb_data or {}
    mapping_data  = mapping_data or {}
    maturity_data = maturity_data or {}

    retire_n   = sum(1 for a in apps if a.get("rationalization_action", "") in ("Retire", "Replace"))
    refactor_n = sum(1 for a in apps if a.get("rationalization_action", "") in ("Refactor", "Replatform", "Rehost"))
    eol_n      = sum(1 for a in apps if a.get("end_of_life"))
    total_n    = len(apps)
    pct_retire = round(retire_n / total_n * 100) if total_n else 0

    arb_decision   = str(arb_data.get("decision", "") or "").upper()
    arb_conditions = arb_data.get("conditions") or []

    map_skipped = bool(mapping_data.get("skipped"))
    map_impact  = str(mapping_data.get("overall_impact_level", "") or "") if not map_skipped else ""

    mat_score_raw = maturity_data.get("overall_maturity_score") or maturity_data.get("overall_score")
    mat_band      = maturity_data.get("overall_band") or maturity_data.get("maturity_level") or ""
    try:
        mat_score_f = float(mat_score_raw) if mat_score_raw not in (None, "-", "") else None
    except (TypeError, ValueError):
        mat_score_f = None

    dims = maturity_data.get("dimensions", {}) or {}
    lowest_dim, lowest_score = None, 99
    for k, v in dims.items():
        if isinstance(v, dict) and v.get("score") is not None:
            try:
                sc = float(v["score"])
            except (TypeError, ValueError):
                continue
            if sc < lowest_score:
                lowest_score, lowest_dim = sc, k.replace("_", " ").title()

    # ── Narrative ───────────────────────────────────────────────────────────
    narrative = (
        f"This combined intelligence view synthesises findings across {total_n} assessed applications "
        f"(${total_cost:,.0f} annual spend, ${pot_savings:,.0f} potential savings)"
        + (f", an ARB governance decision of {arb_decision}" if arb_decision else "")
        + (f", a {map_impact.lower()} dependency impact assessment" if map_impact else "")
        + (f", and an EA maturity score of {mat_score_f:.1f}/5 ({mat_band})" if mat_score_f is not None else "")
        + ". "
        + (f"Overall portfolio risk is classified as {overall_risk}, reflecting combined exposure from "
           f"rationalisation, governance and technology debt signals." if overall_risk and overall_risk != "-" else "")
    ).strip()

    # ── Recommendations ─────────────────────────────────────────────────────
    recs = []
    rank = 1
    if retire_n > 0:
        recs.append({
            "priority": rank, "effort": "High" if retire_n >= 10 else "Medium", "timeline": "0-6 months",
            "recommendation": f"Execute phased decommissioning of {retire_n} applications flagged for retirement or replacement",
            "business_value": (
                f"{retire_n} applications ({pct_retire}% of the portfolio) are flagged Retire/Replace, representing "
                f"an estimated ${pot_savings:,.0f} in annual savings. Sequence low-dependency, low-risk applications "
                f"first to build early momentum."
            ),
        })
        rank += 1
    if refactor_n > 0:
        recs.append({
            "priority": rank, "effort": "Medium", "timeline": "6-18 months",
            "recommendation": f"Plan modernisation for {refactor_n} applications earmarked for refactoring, replatforming or rehosting",
            "business_value": (
                f"{refactor_n} applications require technical modernisation rather than outright retirement. "
                f"Addressing these reduces long-term technical debt and extends useful application life."
            ),
        })
        rank += 1
    if arb_decision:
        if arb_decision in ("REJECTED", "CONDITIONAL"):
            recs.append({
                "priority": rank, "effort": "Medium", "timeline": "0-3 months",
                "recommendation": "Resolve outstanding ARB governance conditions before proceeding with portfolio changes",
                "business_value": (
                    f"The Architecture Review Board returned a {arb_decision} decision"
                    + (f" with {len(arb_conditions)} condition(s) to satisfy" if arb_conditions else "")
                    + ". Addressing these unblocks downstream rationalisation and migration work."
                ),
            })
        else:
            recs.append({
                "priority": rank, "effort": "Low", "timeline": "0-3 months",
                "recommendation": "Proceed with the ARB-approved transformation roadmap",
                "business_value": "Governance approval is in place — execution can begin without further architecture review delays.",
            })
        rank += 1
    if map_impact:
        recs.append({
            "priority": rank, "effort": "Medium", "timeline": "3-9 months",
            "recommendation": "Sequence migrations using dependency-aware impact analysis",
            "business_value": (
                f"Dependency mapping shows an overall {map_impact} impact level. Migrating highly-coupled "
                f"applications first, in the order recommended by the dependency analysis, minimises "
                f"cross-application disruption."
            ),
        })
        rank += 1
    if mat_score_f is not None:
        if mat_score_f < 2.5:
            recs.append({
                "priority": rank, "effort": "High", "timeline": "6-18 months",
                "recommendation": "Invest in foundational EA capability uplift" + (f", starting with {lowest_dim}" if lowest_dim else ""),
                "business_value": (
                    f"EA maturity is assessed at {mat_score_f:.1f}/5 ({mat_band}). "
                    + (f"{lowest_dim} is the lowest-scoring dimension and should be prioritised. " if lowest_dim else "")
                    + "Raising maturity is a precondition for sustaining rationalisation savings beyond this cycle."
                ),
            })
        else:
            recs.append({
                "priority": rank, "effort": "Low", "timeline": "Ongoing",
                "recommendation": "Sustain EA maturity through continuous governance and benchmarking",
                "business_value": (
                    f"EA maturity is assessed at {mat_score_f:.1f}/5 ({mat_band}), a solid foundation. "
                    f"Re-running this assessment annually keeps governance evidence-based and board-reportable."
                ),
            })
        rank += 1
    recs.append({
        "priority": rank, "effort": "Medium", "timeline": "0-3 months",
        "recommendation": "Establish a unified EA transformation governance cadence",
        "business_value": (
            "Bring portfolio rationalisation, ARB governance, dependency planning and maturity uplift under a "
            "single steering cadence so investment decisions stay aligned across all four disciplines."
        ),
    })

    # ── Quick wins ───────────────────────────────────────────────────────────
    quick_wins = []
    if eol_n:
        quick_wins.append(f"Prioritise the {eol_n} end-of-life application(s) for immediate decommissioning planning")
    if retire_n:
        quick_wins.append("Consolidate duplicate/overlapping tools identified in portfolio rationalisation")
    if map_impact:
        quick_wins.append("Document dependencies for the highest-coupling applications before scheduling migrations")
    if lowest_dim:
        quick_wins.append(f"Run a focused improvement sprint on {lowest_dim}, the lowest-scoring EA dimension")
    if not quick_wins:
        quick_wins.append("Re-run this pipeline after the next data refresh to track portfolio and maturity trends")

    return {"narrative": narrative, "recommendations": recs, "quick_wins": quick_wins}


def _svg_speedo_gauge(score: float, max_score: float = 5.0, size: int = 160) -> str:
    """Semicircular speedometer-style gauge (Low/Medium/High zones + needle),
    matching the in-app Maturity Assessment dial. Used by the HTML report so
    Section 5 visually matches what the user sees after running the live
    assessment, not just a flat linear bar.
    """
    cx, cy = size / 2.0, size * 0.46
    r = size / 2.0 - 22
    t_score = max(0.0, min(1.0, score / max_score))

    def pt(t, radius):
        ang = math.radians(180 - t * 180)
        return cx + radius * math.cos(ang), cy - radius * math.sin(ang)

    zones = [(0.0, 0.40, "#dc3545"), (0.40, 0.70, "#ffa500"), (0.70, 1.0, "#28a745")]
    arcs = ""
    for t0, t1, color in zones:
        x0, y0 = pt(t0, r)
        x1, y1 = pt(t1, r)
        arcs += (f'<path d="M {x0:.1f} {y0:.1f} A {r:.1f} {r:.1f} 0 0 1 {x1:.1f} {y1:.1f}" '
                 f'fill="none" stroke="{color}" stroke-width="13" stroke-linecap="butt"/>')

    npx, npy = pt(t_score, r - 9)
    lx, ly = pt(0.0, r + 12)
    hx, hy = pt(1.0, r + 12)

    return f'''<svg width="{size}" height="{cy + 26:.0f}" viewBox="0 0 {size} {cy + 26:.0f}" style="display:block;margin:0 auto">
  {arcs}
  <line x1="{cx:.1f}" y1="{cy:.1f}" x2="{npx:.1f}" y2="{npy:.1f}" stroke="#0a1628" stroke-width="3" stroke-linecap="round"/>
  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="5.5" fill="#0a1628"/>
  <text x="{lx:.1f}" y="{ly:.1f}" font-size="10" font-weight="700" fill="#dc3545" font-family="Inter,sans-serif" text-anchor="middle">LOW</text>
  <text x="{hx:.1f}" y="{hy:.1f}" font-size="10" font-weight="700" fill="#28a745" font-family="Inter,sans-serif" text-anchor="middle">HIGH</text>
  <text x="{cx:.1f}" y="{cy - 14:.0f}" font-size="26" font-weight="800" fill="#0a1628" font-family="Inter,sans-serif" text-anchor="middle">{score:.1f}</text>
</svg>'''


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
            f"{_now().strftime('%d %B %Y')}  |  Page {self.page_no()}",
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
        self.multi_cell(182, 14, _safe_str(title), align="L")

        self.set_x(14)
        self.set_font("Helvetica", "", 12)
        self.set_text_color(160, 180, 220)
        self.multi_cell(182, 7, _safe_str(subtitle), align="L")

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
            self.cell(0, 6, _safe_str(line), ln=True)
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
        if self.get_y() > 232:
            self.add_page()
        n = len(items)
        col_w = 182 / n
        card_w = col_w - 2
        card_h = 30
        x0 = 14
        y0 = self.get_y()
        for i, (val, lbl) in enumerate(items):
            x = x0 + i * col_w
            display_val = _fmt_kpi(str(val))
            # card background
            self.set_fill_color(*LGREY)
            self.set_draw_color(*MGREY)
            self.set_line_width(0.3)
            self.rect(x, y0, card_w, card_h, "FD")
            # top accent
            self.set_fill_color(*BLUE)
            self.rect(x, y0, card_w, 2, "F")
            # value — scale font to fit, never wider than the card
            font_sz = 13
            self.set_font("Helvetica", "B", font_sz)
            while font_sz > 7 and self.get_string_width(display_val) > card_w - 4:
                font_sz -= 1
                self.set_font("Helvetica", "B", font_sz)
            self.set_xy(x, y0 + 5)
            self.set_text_color(*NAVY)
            self.cell(card_w, 8, display_val, align="C")
            # label — wraps within the card width instead of overflowing
            self.set_xy(x + 1, y0 + 16)
            self.set_font("Helvetica", "", 5.8)
            self.set_text_color(*DGREY)
            self.multi_cell(card_w - 2, 3.4, str(lbl).upper(), align="C")
        self.set_y(y0 + card_h + 4)

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
            self.cell(w, 8, _safe_str(col), border=0, fill=True)
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
            self.cell(w, 6, _safe_str(cell)[:45], border=0, fill=True)
        self.ln()
        self.set_draw_color(*MGREY)
        self.line(14, self.get_y(), 196, self.get_y())

    # ── Executive summary box ─────────────────────────────────────────────────

    def exec_box(self, text: str, label: str = "EXECUTIVE SUMMARY"):
        if not text:
            return
        x, y = 14, self.get_y()
        # label tab — width sized to the actual text so long labels never clip
        self.set_fill_color(*NAVY)
        self.set_text_color(*WHITE)
        self.set_font("Helvetica", "B", 7)
        self.set_xy(x, y)
        label_txt = f"  {label}  "
        tab_w = min(182, max(44, self.get_string_width(label_txt) + 4))
        self.cell(tab_w, 5, label_txt, fill=True)
        self.ln(5)
        # body
        self.set_fill_color(*LGREY)
        self.set_font("Helvetica", "", 9)
        self.set_text_color(*BLACK)
        self.set_x(14)
        body_y = self.get_y()
        self.multi_cell(182, 5.5, _safe_str(text, 2000), fill=True)
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
        self.cell(8, 7, _safe_str(rank), fill=True, align="C")
        self.set_fill_color(*LGREY)
        self.set_text_color(*NAVY)
        self.set_font("Helvetica", "B", 9)
        self.cell(122, 7, f"  {_safe_str(title)[:70]}", fill=True)
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
        self.multi_cell(174, 5, _safe_str(desc, 400), fill=True)

        # Impact
        if impact:
            self.set_x(22)
            self.set_fill_color(*LGREY)
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(*BLUE)
            self.multi_cell(174, 4.5, f"Impact: {_safe_str(impact, 200)}", fill=True)

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
                self.multi_cell(col_w, 4.5, f"- {_safe_str(item, 60)}", fill=True)
                cy = self.get_y()
        self.set_y(max(self.get_y(), y0 + 60))
        self.ln(4)

    # ── Semicircular maturity dial gauge ─────────────────────────────────────

    def dial_gauge(self, score: float, x: float, y: float, r: float = 18):
        """Speedometer-style maturity dial (Low/Medium/High zones + needle),
        approximated with short radial line segments since plain fpdf2 has
        no native arc-stroke primitive. Mirrors the live in-app gauge and
        the HTML report's SVG version so both reports match.
        """
        cx, cy = x + r + 4, y + r + 6
        t_score = max(0.0, min(1.0, score / 5.0))

        def pt(t, radius):
            ang = math.radians(180 - t * 180)
            return cx + radius * math.cos(ang), cy - radius * math.sin(ang)

        zones = [(0.0, 0.40, (220, 53, 69)), (0.40, 0.70, (255, 170, 0)), (0.70, 1.0, (40, 167, 69))]
        self.set_line_width(4.2)
        for t0, t1, color in zones:
            self.set_draw_color(*color)
            n = max(8, int(70 * (t1 - t0)))
            for i in range(n):
                ta = t0 + (t1 - t0) * i / n
                tb = t0 + (t1 - t0) * (i + 1) / n
                x1, y1 = pt(ta, r)
                x2, y2 = pt(tb, r)
                self.line(x1, y1, x2, y2)
        self.set_line_width(0.3)

        # Needle + pivot
        ntx, nty = pt(t_score, r - 6)
        self.set_draw_color(*NAVY)
        self.set_line_width(1.1)
        self.line(cx, cy, ntx, nty)
        self.set_line_width(0.3)
        self.set_fill_color(*NAVY)
        self.ellipse(cx - 1.4, cy - 1.4, 2.8, 2.8, "F")

        # Low / High labels
        self.set_font("Helvetica", "B", 6.5)
        self.set_text_color(220, 53, 69)
        self.set_xy(cx - r - 4, cy + 2)
        self.cell(14, 4, "LOW")
        self.set_text_color(40, 167, 69)
        self.set_xy(cx + r - 10, cy + 2)
        self.cell(14, 4, "HIGH")

        # Score number, centred under the dial
        self.set_font("Helvetica", "B", 15)
        self.set_text_color(*NAVY)
        self.set_xy(cx - 18, cy + 7)
        self.cell(36, 9, f"{score:.1f}", align="C")
        self.set_font("Helvetica", "", 7)
        self.set_text_color(*DGREY)
        self.set_xy(cx - 18, cy + 15)
        self.cell(36, 4, "/ 5", align="C")


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

        gen_date = _now().strftime("%d %B %Y  %H:%M")
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
                f"Framework:      6R Rationalization Model",
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

        # 6R action breakdown
        action_counts: Dict[str, int] = {}
        for t in tools:
            a = t.get("rationalization_action", "TBD")
            action_counts[a] = action_counts.get(a, 0) + 1

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

        gen_date      = _now().strftime("%d %B %Y  %H:%M")
        summary       = pipeline.get("pipeline_summary", {})
        time_data     = pipeline.get("TIME", {})
        arb_data      = pipeline.get("ARB", {}) or {}
        mapping_data  = pipeline.get("MAPPING", {})
        maturity_data = pipeline.get("MATURITY", {})
        insights_data = pipeline.get("INSIGHTS", {})

        apps          = time_data.get("applications", [])
        dups          = time_data.get("duplications", [])
        # /time/ingest returns "summary"; run_time() returns "portfolio_summary" — support both
        time_summary  = time_data.get("portfolio_summary") or time_data.get("summary", {})
        time_assess   = time_data.get("assessment", {}) or {}

        total_cost    = time_summary.get("total_annual_cost", 0) or sum(a.get("annual_cost") or 0 for a in apps)
        pot_savings   = time_summary.get("potential_savings", 0) or sum(d.get("potential_annual_savings", 0) for d in dups)
        dups_count    = time_summary.get("duplications_found", 0) or len(dups)
        mat_score     = maturity_data.get("overall_maturity_score") or maturity_data.get("overall_score") or "-"
        mat_band      = maturity_data.get("overall_band") or maturity_data.get("maturity_level") or "-"
        _rp_pdf       = (insights_data.get("risk_profile") or {}) if isinstance(insights_data.get("risk_profile"), dict) else {}
        overall_risk  = str(_rp_pdf.get("overall_risk") or insights_data.get("overall_risk") or "").strip().upper()
        if not overall_risk or overall_risk in ("-", "NONE", "N/A", "NA", "NULL"):
            _r = sum(1 for a in apps if a.get("rationalization_action","") in ("Retire","Replace"))
            _e = sum(1 for a in apps if a.get("end_of_life"))
            overall_risk = "HIGH" if (_r >= 5 or _e >= 3) else "MEDIUM" if (_r >= 2 or _e >= 1) else "LOW" if apps else "-"
        flagged_count = sum(1 for a in apps if a.get("rationalization_action","") not in ("Retain",""))
        stages        = "  >  ".join(summary.get("stages_completed", []))

        # Stages that were actually run — skipped stages are omitted entirely
        # from the report (no section title, no placeholder), and remaining
        # sections are renumbered so there are never gaps.
        has_arb      = bool(arb_data.get("decision"))
        has_mapping  = bool(mapping_data) and not mapping_data.get("skipped")
        has_maturity = bool(maturity_data) or mat_score != "-"

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
                f"EA Maturity Score:  {mat_score} / 5  ({mat_band})",
                f"Overall Risk:       {overall_risk}",
                f"Classification:     CONFIDENTIAL",
            ],
            stages=stages,
        )

        # ── Section 1 -- Executive Intelligence Summary ────────────────────────
        pdf.add_page()
        ins_exec  = _safe_str(insights_data.get("executive_summary", "") or "")
        time_exec = _safe_str(time_assess.get("executive_summary", "") or "")
        pdf.section_title("1.", "Executive Intelligence Summary")
        if ins_exec:
            pdf.exec_box(ins_exec, label="INSIGHTS -- EXECUTIVE SUMMARY")
        if time_exec and time_exec != ins_exec:
            pdf.exec_box(time_exec, label="PORTFOLIO -- RATIONALIZATION SUMMARY")
        if not ins_exec and not time_exec:
            # Auto-generate narrative from portfolio data
            _retire_n = sum(1 for a in apps if a.get("rationalization_action","") in ("Retire","Replace"))
            _refac_n  = sum(1 for a in apps if a.get("rationalization_action","") in ("Refactor","Replatform","Rehost"))
            _retain_n = sum(1 for a in apps if a.get("rationalization_action","") == "Retain")
            _fallback = (
                f"This intelligence report consolidates AI-driven analysis of {len(apps)} enterprise applications "
                f"with a combined annual portfolio spend of ${total_cost:,.0f}. "
                f"The analysis identifies ${pot_savings:,.0f} in estimated annual savings through strategic rationalisation. "
                f"Portfolio breakdown: {_retain_n} applications recommended for retention, "
                f"{_retire_n} flagged for retirement or replacement, and {_refac_n} earmarked for refactoring or migration. "
                f"EA Maturity is assessed at {mat_score}/5 ({mat_band}). "
                f"Overall portfolio risk is classified as {overall_risk}."
            )
            pdf.exec_box(_fallback, label="PORTFOLIO -- AI INTELLIGENCE SUMMARY")

        # KPI overview
        pdf.kpi_row([
            (str(len(apps)),          "Apps Assessed"),
            (f"${total_cost:,.0f}",   "Portfolio Spend"),
            (f"${pot_savings:,.0f}",  "Est. Savings"),
            (str(dups_count),         "Duplications"),
            (str(flagged_count),      "Apps Flagged"),
            (f"{mat_score}/5",        "Maturity Score"),
            (str(overall_risk),       "Risk Level"),
        ])

        # Financial impact
        fin = insights_data.get("financial_impact", {})
        if fin:
            pdf.sub_title("Financial Impact Analysis")
            pdf.table_header(["Metric", "Value"], [80, 102])
            for i, (k, v) in enumerate(fin.items()):
                if v:
                    # Flatten nested dicts to readable string instead of Python repr
                    if isinstance(v, dict):
                        v_str = "  |  ".join(f"{dk.replace('_',' ')}: {dv}" for dk, dv in v.items() if dv)
                    elif isinstance(v, list):
                        v_str = ",  ".join(str(x) for x in v[:3])
                    else:
                        v_str = str(v)
                    pdf.table_row([k.replace("_", " ").title(), _safe_str(v_str)], [80, 102], shade=i%2==0)

        sec_num = 2

        # ── Section 2 -- Portfolio Rationalization (TIME) ──────────────────────
        pdf.section_title(f"{sec_num}.", "Portfolio Rationalization Analysis")
        sec_num += 1
        if time_exec:
            pdf.exec_box(time_exec, label="RATIONALIZATION -- EXECUTIVE SUMMARY")

        action_counts: Dict[str, int] = {}
        for t in apps:
            a = t.get("rationalization_action", "TBD")
            action_counts[a] = action_counts.get(a, 0) + 1

        pdf.sub_title("TIME Framework Classification")
        self._pdf_time_table(pdf, apps)

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

        # ── Section -- ARB Governance Decision (omitted entirely if skipped) ───
        if has_arb:
            pdf.section_title(f"{sec_num}.", "Architecture Review Board (ARB) -- Governance Decision")
            sec_num += 1
            self._pdf_arb_section(pdf, arb_data)

        # ── Section -- Dependency Analysis (MAPPING) (omitted if skipped) ──────
        if has_mapping:
            pdf.section_title(f"{sec_num}.", "Dependency & Impact Analysis -- MAPPING")
            sec_num += 1
            self._pdf_mapping_section(pdf, mapping_data)

        # ── Section -- Compliance Gap Analysis (omitted if skipped) ─────────────
        compliance_data = pipeline.get("COMPLIANCE", {})
        has_compliance  = bool(compliance_data) and not compliance_data.get("skipped")
        if has_compliance:
            pdf.section_title(f"{sec_num}.", "Compliance Gap Analysis -- REGULATORY MAPPING")
            sec_num += 1
            self._pdf_compliance_section(pdf, compliance_data)

        # ── Section -- EA Maturity Assessment (KPMG 4-Pillar Framework) ────────
        if has_maturity:
            pdf.section_title(f"{sec_num}.", "EA Maturity Assessment -- 4 Pillars / 8 Dimensions")
            sec_num += 1
            self._pdf_maturity_section(pdf, maturity_data)

        # ── Section -- Strategic Recommendations (INSIGHTS) ────────────────────
        pdf.section_title(f"{sec_num}.", "Strategic Recommendations -- INSIGHTS")
        sec_num += 1

        # Coverage banner — mirrors the HTML report's "Intelligence synthesised
        # from all pipeline stages" strip, listing only stages that actually ran.
        stages_covered = []
        if apps:
            stages_covered.append("Portfolio Rationalization (TIME . 6R)")
        if has_arb:
            stages_covered.append("ARB Governance")
        if has_mapping:
            stages_covered.append("Dependency Analysis (MAPPING)")
        if has_compliance:
            stages_covered.append("Compliance Gap Analysis")
        if has_maturity:
            stages_covered.append("EA Maturity Assessment")
        if stages_covered:
            pdf.set_x(14)
            pdf.set_font("Helvetica", "B", 7.5)
            pdf.set_text_color(*BLUE)
            pdf.cell(0, 5, "INTELLIGENCE SYNTHESISED FROM ALL PIPELINE STAGES", ln=True)
            pdf.ln(1)
            chip_h = 6
            cx = 14
            cy = pdf.get_y()
            pdf.set_font("Helvetica", "B", 7.5)
            for s in stages_covered:
                w = pdf.get_string_width(s) + 6
                if cx + w > 196:
                    cx = 14
                    cy += chip_h + 2
                pdf.set_xy(cx, cy)
                pdf.set_fill_color(232, 238, 255)
                pdf.set_text_color(*NAVY)
                pdf.cell(w, chip_h, s, fill=True, align="C")
                cx += w + 3
            pdf.set_y(cy + chip_h + 4)

        # Combined Intelligence narrative + recommendations — if the INSIGHTS
        # agent itself returned no strategic_recommendations, synthesise an
        # elaborated, cross-stage view from TIME/ARB/MAPPING/MATURITY data so
        # this section is never left blank.
        _effective_insights = dict(insights_data or {})
        if not _effective_insights.get("strategic_recommendations"):
            _synth = _synthesize_recommendations(
                apps, arb_data, mapping_data, maturity_data, total_cost, pot_savings, overall_risk
            )
            pdf.exec_box(_synth["narrative"], label="COMBINED INTELLIGENCE -- CROSS-STAGE SYNTHESIS")
            _effective_insights["strategic_recommendations"] = _synth["recommendations"]
            if not _effective_insights.get("quick_wins"):
                _effective_insights["quick_wins"] = _synth["quick_wins"]

        self._pdf_insights_recs(pdf, _effective_insights)

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

    _TIME_PDF_DESC = {
        "Invest":    "High business value + healthy tech -- retain and grow investment",
        "Tolerate":  "High business value + ageing tech -- maintain, plan modernisation",
        "Migrate":   "Low business value + healthy tech -- consolidate or repurpose",
        "Eliminate": "Low business value + poor tech -- decommission priority",
    }

    def _pdf_time_table(self, pdf, apps):
        total = max(len(apps), 1)
        tc_counts: Dict[str, int] = {}
        for t in apps:
            tc = t.get("time_classification", "Eliminate")
            tc_counts[tc] = tc_counts.get(tc, 0) + 1
        pdf.table_header(["TIME Quadrant", "Count", "% Portfolio", "Description"], [34, 16, 20, 112])
        for action in ["Invest", "Tolerate", "Migrate", "Eliminate"]:
            c   = tc_counts.get(action, 0)
            pct = round(c / total * 100)
            pdf.set_x(14)
            pdf.badge(action, 32)
            pdf.set_font("Helvetica", "", 8)
            pdf.cell(18, 6, str(c))
            pdf.cell(20, 6, f"{pct}%")
            pdf.cell(112, 6, self._TIME_PDF_DESC.get(action, "")[:68])
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
        cols   = ["Application", "Vendor", "Category", "Annual Cost", "Users", "Score", "6R Action", "Confidence"]
        widths = [36, 24, 22, 22, 14, 14, 28, 22]
        pdf.table_header(cols, widths)
        for i, t in enumerate(tools):
            if pdf.get_y() > 268:
                pdf.add_page(); pdf.table_header(cols, widths)
            cost  = f"${t.get('annual_cost',0):,.0f}" if t.get("annual_cost") else "-"
            score = t.get("composite_score", "-")
            act   = t.get("rationalization_action", "TBD")
            conf  = t.get("confidence_level", "Low")
            fill  = LGREY if i%2==0 else WHITE
            pdf.set_fill_color(*fill)
            pdf.set_x(14)
            pdf.set_font("Helvetica", "B", 7)
            pdf.cell(36, 6, (t.get("name") or "-")[:24], fill=True)
            pdf.set_font("Helvetica", "", 7)
            pdf.cell(24, 6, (t.get("vendor") or "-")[:15], fill=True)
            pdf.cell(22, 6, (t.get("category") or "-")[:14], fill=True)
            pdf.cell(22, 6, cost, fill=True)
            pdf.cell(14, 6, str(t.get("user_count") or "-"), fill=True)
            pdf.cell(14, 6, f"{score}/10", fill=True)
            pdf.badge(act, 28); pdf.badge(conf, 22)
            pdf.ln()
            pdf.set_draw_color(*MGREY); pdf.line(14, pdf.get_y(), 196, pdf.get_y())

    def _pdf_tool_table_compact(self, pdf, tools):
        cols   = ["Application", "Category", "Annual Cost", "Users", "Score", "TIME", "6R Action", "Conf."]
        widths = [40, 24, 20, 12, 12, 24, 26, 14]
        pdf.table_header(cols, widths)
        for i, t in enumerate(tools):
            if pdf.get_y() > 268:
                pdf.add_page(); pdf.table_header(cols, widths)
            cost = f"${t.get('annual_cost',0):,.0f}" if t.get("annual_cost") else "-"
            fill = LGREY if i%2==0 else WHITE
            pdf.set_fill_color(*fill)
            pdf.set_x(14)
            pdf.set_font("Helvetica", "B", 7)
            pdf.cell(36, 6, (t.get("name") or "-")[:24], fill=True)
            pdf.set_font("Helvetica", "", 7)
            pdf.cell(22, 6, (t.get("category") or "-")[:14], fill=True)
            pdf.cell(20, 6, cost, fill=True)
            pdf.cell(12, 6, str(t.get("user_count") or "-"), fill=True)
            pdf.cell(12, 6, f"{t.get('composite_score','-')}/10", fill=True)
            pdf.badge(t.get("time_classification","Eliminate"), 22)
            pdf.badge(t.get("rationalization_action","TBD"), 24)
            pdf.badge(t.get("confidence_level","Low"), 14)
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
            reason = mapping.get("reason", "No apps flagged for action (Retire/Replace/Refactor).")
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*DGREY)
            pdf.set_x(14)
            pdf.multi_cell(182, 5, _safe_str(reason))
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
            pdf.table_header(["Application","Rationalization","Impact Level","Coupling","Direct Dependencies"],
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
                pdf.badge(a.get("rationalization_action","-"), 26)
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

    def _pdf_compliance_section(self, pdf, compliance):
        """Compliance Gap Analysis section — per-regulation summary + per-app table."""
        if not compliance or compliance.get("skipped"):
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*DGREY)
            pdf.set_x(14)
            pdf.cell(0, 6, "Compliance check was skipped for this pipeline run.", ln=True)
            return

        score      = compliance.get("overall_compliance_score")
        regs       = compliance.get("regulations_checked", [])
        reg_sum    = compliance.get("regulation_summary", {})
        app_map    = compliance.get("app_compliance_map", [])
        crit_gaps  = compliance.get("critical_gaps", [])
        top_risks  = compliance.get("top_risks", [])
        roadmap    = compliance.get("remediation_roadmap", [])
        limits     = compliance.get("data_limitations", "")

        # Score badge
        if score is not None:
            score_int = int(score)
            if score_int >= 80:
                badge_fill = (212, 237, 218); badge_text = GREEN
            elif score_int >= 50:
                badge_fill = (255, 243, 205); badge_text = AMBER
            else:
                badge_fill = (248, 215, 218); badge_text = RED
            pdf.set_x(14)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_text_color(*NAVY)
            pdf.cell(80, 6, f"Overall Compliance Score:", ln=False)
            pdf.set_fill_color(*badge_fill)
            pdf.set_text_color(*badge_text)
            pdf.set_font("Helvetica", "B", 11)
            pdf.cell(30, 6, f"{score_int}/100", fill=True, align="C", ln=True)
            pdf.ln(2)

        if regs:
            pdf.set_x(14)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*NAVY)
            pdf.cell(0, 5, f"Regulations Assessed: {', '.join(regs)}", ln=True)
            pdf.ln(2)

        # Per-regulation summary table
        if reg_sum:
            pdf.sub_title("Regulation Summary")
            pdf.table_header(["Regulation", "Apps Affected", "Gaps Found", "Non-Compliant", "Risk Level"],
                             [46, 28, 28, 30, 50])
            for i, (reg, data) in enumerate(reg_sum.items()):
                if pdf.get_y() > 268:
                    pdf.add_page()
                fill = LGREY if i % 2 == 0 else WHITE
                pdf.set_fill_color(*fill)
                pdf.set_x(14)
                pdf.set_font("Helvetica", "B", 7.5)
                pdf.set_text_color(*BLACK)
                pdf.cell(46, 6, _safe_str(reg)[:28], fill=True)
                pdf.set_font("Helvetica", "", 7.5)
                pdf.cell(28, 6, str(data.get("apps_affected", "-")), fill=True, align="C")
                pdf.cell(28, 6, str(data.get("gaps_count", "-")), fill=True, align="C")
                pdf.cell(30, 6, str(data.get("non_compliant_count", "-")), fill=True, align="C")
                pdf.badge(data.get("risk", "-"), 50)
                pdf.ln()
                pdf.set_draw_color(*MGREY)
                pdf.line(14, pdf.get_y(), 196, pdf.get_y())

        # Per-app compliance table
        if app_map:
            pdf.sub_title("Per-Application Compliance Assessment")
            pdf.table_header(["Application", "Status", "Risk", "Data Classification", "Key Gap"],
                             [38, 24, 18, 36, 66])
            status_colors = {
                "COMPLIANT":     (212, 237, 218),
                "PARTIAL":       (255, 243, 205),
                "NON_COMPLIANT": (248, 215, 218),
                "UNKNOWN":       (232, 237, 248),
            }
            for i, a in enumerate(app_map):
                if pdf.get_y() > 265:
                    pdf.add_page()
                status = _safe_str(a.get("compliance_status", "UNKNOWN")).upper()
                fill   = status_colors.get(status, LGREY) if i % 2 == 0 else WHITE
                first_gap = _safe_str((a.get("gaps") or [""])[0])[:38]
                pdf.set_fill_color(*fill)
                pdf.set_x(14)
                pdf.set_font("Helvetica", "B", 7)
                pdf.set_text_color(*BLACK)
                pdf.cell(38, 6, _safe_str(a.get("app_name", "-"))[:22], fill=True)
                pdf.set_font("Helvetica", "B", 6.5)
                pdf.cell(24, 6, status[:14], fill=True)
                pdf.set_font("Helvetica", "", 7)
                pdf.badge(a.get("risk_level", "-"), 18)
                pdf.cell(36, 6, _safe_str(a.get("data_classification", "-"))[:22], fill=True)
                pdf.cell(66, 6, first_gap, fill=True)
                pdf.ln()
                pdf.set_draw_color(*MGREY)
                pdf.line(14, pdf.get_y(), 196, pdf.get_y())

        # Critical gaps
        if crit_gaps:
            pdf.ln(3)
            pdf.set_x(14)
            pdf.set_fill_color(248, 215, 218)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*RED)
            pdf.cell(182, 6, "  CRITICAL COMPLIANCE GAPS", fill=True, ln=True)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*BLACK)
            for gap in crit_gaps[:5]:
                pdf.set_x(18)
                pdf.multi_cell(178, 5, f"- {_safe_str(gap)}")

        # Remediation roadmap
        if roadmap:
            pdf.ln(3)
            pdf.sub_title("Remediation Roadmap")
            for i, step in enumerate(roadmap[:6]):
                pdf.set_x(14)
                pdf.set_font("Helvetica", "B", 7.5)
                pdf.set_text_color(*NAVY)
                pdf.cell(8, 5, f"{i+1}.")
                pdf.set_font("Helvetica", "", 7.5)
                pdf.set_text_color(*BLACK)
                pdf.multi_cell(174, 5, _safe_str(step))

        if limits:
            pdf.ln(2)
            pdf.set_x(14)
            pdf.set_font("Helvetica", "I", 7.5)
            pdf.set_text_color(*DGREY)
            pdf.multi_cell(182, 5, f"Data note: {_safe_str(limits)}")

    def _pdf_arb_section(self, pdf, arb):
        """ARB Governance Decision section."""
        if not arb or not arb.get("decision"):
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*DGREY)
            pdf.set_x(14)
            pdf.cell(0, 6, "ARB governance review not completed for this pipeline run.", ln=True)
            return

        decision   = _safe_str(arb.get("decision", "UNKNOWN")).upper()
        confidence = arb.get("confidence_score", 0)
        compliance = arb.get("compliance_score", 0)
        complexity = _safe_str(arb.get("integration_complexity", "-"))
        reasoning  = _safe_str(arb.get("reasoning", ""))
        conditions = arb.get("conditions") or []
        risks      = arb.get("risks") or []
        recs       = arb.get("recommendations") or []

        dec_colors = {"APPROVED": GREEN, "REJECTED": RED, "CONDITIONAL": AMBER}
        dec_fill   = {"APPROVED": (212,237,218), "REJECTED": (248,215,218), "CONDITIONAL": (255,243,205)}
        dc  = dec_colors.get(decision, SLATE)
        dfg = dec_fill.get(decision, (226,227,229))

        # Decision banner
        pdf.set_fill_color(*dfg)
        pdf.set_x(14)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*dc)
        pdf.cell(182, 11, f"  ARB Decision: {decision}", fill=True, ln=True)
        pdf.ln(4)

        # Scores row
        pdf.table_header(["Confidence Score", "Compliance Score", "Integration Complexity"], [60, 60, 62])
        pdf.table_row([f"{confidence}/100", f"{compliance}/100", complexity], [60, 60, 62], shade=False)
        pdf.ln(6)

        # Reasoning
        if reasoning:
            pdf.sub_title("ARB Reasoning")
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*BLACK)
            pdf.set_x(14)
            pdf.multi_cell(182, 5, _safe_str(reasoning, 500))
            pdf.ln(3)

        # Conditions / Risks / Recommendations columns
        if conditions or risks or recs:
            pdf.table_header(["Conditions", "Risk Flags", "Recommendations"], [60, 60, 62])
            max_rows = max(len(conditions), len(risks), len(recs), 1)
            for i in range(min(max_rows, 5)):
                c = _safe_str(conditions[i] if i < len(conditions) else "")[:38]
                r = _safe_str(risks[i]      if i < len(risks)      else "")[:38]
                rec = _safe_str(recs[i]     if i < len(recs)       else "")[:38]
                pdf.table_row([c, r, rec], [60, 60, 62], shade=i%2==0)

        # ── Human Sign-off Audit Trail ────────────────────────────────────────
        signoff = arb.get("signoff") or {}
        if signoff and not signoff.get("skipped"):
            pdf.ln(6)
            pdf.set_x(14)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*NAVY)
            pdf.cell(0, 6, "Human Sign-off Audit Trail", ln=True)
            pdf.set_draw_color(*NAVY)
            pdf.line(14, pdf.get_y(), 196, pdf.get_y())
            pdf.ln(3)

            eff = _safe_str(signoff.get("effective_decision", "—")).upper()
            ai_dec = _safe_str(signoff.get("ai_decision", "—")).upper()
            signed_at = _safe_str(signoff.get("signed_at", "—"))[:19].replace("T", " ")
            eff_col = {"APPROVED": GREEN, "REJECTED": RED, "CONDITIONAL": AMBER, "PENDING_MORE_INFO": SLATE}.get(eff, SLATE)
            eff_fill = {"APPROVED": (212,237,218), "REJECTED": (248,215,218), "CONDITIONAL": (255,243,205), "PENDING_MORE_INFO": (226,227,229)}.get(eff, (226,227,229))

            pdf.set_fill_color(*eff_fill)
            pdf.set_x(14)
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(*eff_col)
            pdf.cell(182, 8, f"  Effective Decision: {eff}   (AI Recommended: {ai_dec})   Signed: {signed_at}", fill=True, ln=True)
            pdf.ln(3)

            arch = signoff.get("architect") or {}
            cio  = signoff.get("cio") or {}

            pdf.table_header(["Role", "Name", "Decision", "Notes"], [24, 44, 36, 78])
            if arch.get("name"):
                arch_dec_label = {
                    "accept":               "Accepted AI Decision",
                    "override_approved":    "Overrode -> APPROVED",
                    "override_conditional": "Overrode -> CONDITIONAL",
                    "override_rejected":    "Overrode -> REJECTED",
                }.get(arch.get("decision", "accept"), arch.get("decision", "—"))
                pdf.table_row(["Architect", arch.get("name","—"), arch_dec_label, (arch.get("notes") or "—")[:50]], [24, 44, 36, 78], shade=True)
            if cio and cio.get("name"):
                cio_dec_label = {
                    "approved":  "Approved",
                    "rejected":  "Rejected",
                    "more_info": "Requested More Info",
                }.get(cio.get("decision", ""), cio.get("decision", "—"))
                pdf.table_row(["CIO", cio.get("name","—"), cio_dec_label, (cio.get("notes") or "—")[:50]], [24, 44, 36, 78], shade=False)

    def _pdf_maturity_section(self, pdf, maturity):
        """EA Maturity Assessment — KPMG 4-pillar / 8-dimension framework."""
        if not maturity:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(*DGREY)
            pdf.set_x(14)
            pdf.cell(0, 6, "Maturity assessment not available.", ln=True)
            return

        score = float(maturity.get("overall_maturity_score") or 0)
        band  = _safe_str(maturity.get("overall_band") or maturity.get("maturity_level") or "Unknown")
        band_c    = {"High": GREEN, "Medium": AMBER, "Low": RED}.get(band, SLATE)
        band_fill = {"High": (212,237,218), "Medium": (255,243,205), "Low": (248,215,218)}.get(band, (226,227,229))

        DIM_ORDER = [
            "vision_and_strategy", "organization", "leadership_and_governance",
            "behaviour_and_culture", "metrics_and_analysis", "policy_and_standards",
            "enabling_processes", "tools_and_technology",
        ]
        DIM_LABELS = {
            "vision_and_strategy":       "Vision & Strategy",
            "organization":              "Organization",
            "leadership_and_governance": "Leadership & Governance",
            "behaviour_and_culture":     "Behaviour & Culture",
            "metrics_and_analysis":      "Metrics & Analysis",
            "policy_and_standards":      "Policy & Standards",
            "enabling_processes":        "Enabling Processes",
            "tools_and_technology":      "Tools & Technology",
        }

        # ── Framework introduction ────────────────────────────────────────────
        pdf.set_x(14)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*BLACK)
        intro = (
            "This section presents an evidence-based assessment of the organisation's EA maturity "
            "using the KPMG 4-Pillar Framework: Vision & Strategy, People, Processes and Technology. "
            "Eight dimensions are scored 0-5 and grouped into three maturity bands: "
            "Low (0-2.0) -- ad-hoc, no formal EA capability; "
            "Medium (2.0-3.5) -- defined but inconsistently adopted; "
            "High (3.5-5.0) -- embedded, enterprise-wide EA excellence. "
            "Results are sourced from a structured 30-question assessment and anchored to evidence "
            "provided by respondents, making them directly actionable for EA investment planning."
        )
        pdf.multi_cell(182, 4.5, _safe_str(intro))
        pdf.ln(4)

        # ── Use Case & Business Value elaboration ─────────────────────────────
        pdf.sub_title("EA Maturity Assessment -- Use Case & Business Value")

        use_case_paras = [
            (
                "Why EA Maturity Assessment Matters",
                "EA Maturity Assessment is a strategic diagnostic that measures how effectively an "
                "organisation designs, governs and executes its Enterprise Architecture practice. "
                "It elevates EA from a purely technical discipline to a measurable business enabler -- "
                "quantifying where the organisation excels and exposing structural gaps that block "
                "transformation value. A single score across 8 evidence-based dimensions gives "
                "leadership a defensible, board-ready view of EA health, directly tied to business "
                "outcomes such as cost efficiency, agility and risk reduction."
            ),
            (
                "1. Strategic Investment Prioritisation",
                "Maturity scores directly guide budget allocation. Dimensions scoring below 2.5/5 "
                "identify where targeted EA investment -- in tooling, talent, governance or process -- "
                "will deliver the highest return. Without this baseline, EA spending is reactive and "
                "poorly directed. With it, CIOs and CFOs can defend EA investment decisions with "
                "evidence-backed ROI projections tied to measurable capability uplift."
            ),
            (
                "2. Digital & Cloud Transformation Readiness",
                "Before major programmes -- cloud migration, ERP replacement, digital platforms or "
                "M&A integration -- maturity baselines surface hidden execution risk. Organisations "
                "with Low maturity in Enabling Processes or Tools & Technology face significantly "
                "higher transformation failure rates, schedule overruns and integration debt. "
                "The assessment gives programme boards an early-warning view of where EA capability "
                "must be built before, not during, the transformation."
            ),
            (
                "3. Architecture Governance & Shadow IT Control",
                "Leadership & Governance dimension scores measure whether EA principles are enforced "
                "consistently across business units. Low scores in this dimension are a documented "
                "root cause of shadow IT proliferation, application duplication and uncontrolled "
                "vendor spend -- the exact patterns identified in the Portfolio Rationalization "
                "section of this report. Strengthening governance maturity directly reduces the "
                "duplication risk surfaced in Section 2."
            ),
            (
                "4. Application Portfolio & Cost Rationalisation",
                "The Tools & Technology dimension measures whether the organisation has the EA "
                "tooling -- CMDB, application portfolio management, architecture repositories -- "
                "to manage landscape complexity at scale. Low scores explain why portfolio data is "
                "fragmented and why duplication goes undetected. Raising Tools & Technology maturity "
                "is a precondition for sustaining the cost savings identified in this report beyond "
                "the current rationalization cycle."
            ),
            (
                "5. Vision & Strategy Alignment",
                "The Vision & Strategy pillar assesses whether EA has a clearly articulated roadmap "
                "aligned to business objectives and backed by executive sponsorship. Without this "
                "alignment, EA becomes an internal IT governance exercise with limited influence "
                "over business decisions. High maturity in this pillar is the single strongest "
                "predictor of EA programme success and long-term cost avoidance."
            ),
            (
                "6. Benchmarking, Trend Tracking & Board Reporting",
                "Running the assessment annually or after major programmes creates a maturity trend "
                "line that ties EA investment to measurable organisational outcomes. The overall "
                "score (0-5 scale, Low/Medium/High band) is a concise, auditable metric for "
                "C-suite and board communications -- demonstrating that EA is managed as a "
                "programme with defined targets, not an ad-hoc practice. It also supports "
                "industry benchmarking against sector peers."
            ),
        ]

        for heading, body in use_case_paras:
            if pdf.get_y() > 258:
                pdf.add_page()
            pdf.set_x(14)
            pdf.set_font("Helvetica", "B", 8)
            pdf.set_text_color(*NAVY)
            pdf.cell(0, 5, _safe_str(heading), ln=True)
            pdf.set_x(16)
            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(*BLACK)
            pdf.multi_cell(178, 4.5, _safe_str(body))
            pdf.ln(2)

        pdf.ln(4)

        # ── Overall score — speedometer dial + band info ───────────────────────
        if pdf.get_y() > 225:
            pdf.add_page()
        dial_y0 = pdf.get_y()
        pdf.dial_gauge(score, x=14, y=dial_y0, r=18)

        info_x = 14 + 64
        info_w = 196 - info_x
        pdf.set_xy(info_x, dial_y0 + 6)
        pdf.set_font("Helvetica", "B", 12)
        pdf.set_text_color(*NAVY)
        pdf.cell(info_w, 7, "EA Maturity Score", ln=True)
        pdf.set_x(info_x)
        pdf.set_font("Helvetica", "", 8.5)
        pdf.set_text_color(*DGREY)
        pdf.cell(info_w, 5, "KPMG 4-Pillar / 8-Dimension Framework", ln=True)
        pdf.ln(2)
        pdf.set_x(info_x)
        pdf.set_fill_color(*band_fill)
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(*band_c)
        band_txt = f"  {band} Maturity  "
        band_w = pdf.get_string_width(band_txt) + 4
        pdf.cell(band_w, 8, band_txt, fill=True)
        pdf.set_y(dial_y0 + 50)

        # Visual gauge bar (Low / Medium / High zones with score marker)
        pdf.ln(3)
        gx, gy, gw, gh = 14, pdf.get_y(), 182, 7
        # Zone fills
        low_w = int(gw * 0.40)
        med_w = int(gw * 0.30)
        grn_w = gw - low_w - med_w
        pdf.set_fill_color(220, 53, 69)
        pdf.rect(gx, gy, low_w, gh, "F")
        pdf.set_fill_color(255, 170, 0)
        pdf.rect(gx + low_w, gy, med_w, gh, "F")
        pdf.set_fill_color(40, 167, 69)
        pdf.rect(gx + low_w + med_w, gy, grn_w, gh, "F")
        # Score marker
        mx = gx + (score / 5.0) * gw
        pdf.set_fill_color(*NAVY)
        pdf.rect(mx - 1.5, gy - 2, 3, gh + 4, "F")
        # Zone labels
        pdf.set_font("Helvetica", "", 6.5)
        pdf.set_text_color(*WHITE)
        pdf.set_xy(gx + 2, gy + 1)
        pdf.cell(low_w - 4, gh - 2, "LOW  (0 - 2.0)")
        pdf.set_xy(gx + low_w + 2, gy + 1)
        pdf.cell(med_w - 4, gh - 2, "MEDIUM  (2.0 - 3.5)")
        pdf.set_xy(gx + low_w + med_w + 2, gy + 1)
        pdf.cell(grn_w - 4, gh - 2, "HIGH  (3.5 - 5.0)")
        # Band description
        pdf.ln(gh + 4)
        band_desc = MATURITY_BAND_DESC.get(band, "")
        if band_desc:
            pdf.set_x(14)
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(*band_c)
            pdf.multi_cell(182, 4, _safe_str(band_desc))
        pdf.ln(4)

        # ── Pillar scores with description and visual bar ─────────────────────
        dims_for_pillar = maturity.get("dimensions", {}) or {}
        pillar_scores = maturity.get("pillar_scores", {}) or {}
        _PPDF_DIM_MAP = {
            "Vision & Strategy": ["vision_and_strategy"],
            "People":            ["organization", "leadership_and_governance", "behaviour_and_culture"],
            "Processes":         ["metrics_and_analysis", "policy_and_standards", "enabling_processes"],
            "Technology":        ["tools_and_technology"],
        }
        if not pillar_scores or all(float(pillar_scores.get(p) or 0) == 0 for p in pillar_scores):
            pillar_scores = {}
            for _pil, _keys in _PPDF_DIM_MAP.items():
                _ps = [float(dims_for_pillar[k].get("score") or 0) for k in _keys
                       if isinstance(dims_for_pillar.get(k), dict) and dims_for_pillar[k].get("score")]
                if _ps:
                    pillar_scores[_pil] = round(sum(_ps) / len(_ps), 2)
        PILLAR_ORDER = ["Vision & Strategy", "People", "Processes", "Technology"]
        if pillar_scores:
            pdf.sub_title("4-Pillar Scores -- KPMG EA Maturity Framework")
            for i, pillar in enumerate(PILLAR_ORDER):
                ps = float(pillar_scores.get(pillar, 0) or 0)
                pb = "High" if ps >= 3.5 else "Medium" if ps >= 2.0 else "Low"
                pc = {"High": GREEN, "Medium": AMBER, "Low": RED}.get(pb, SLATE)
                pf = {"High": (212,237,218), "Medium": (255,243,205), "Low": (248,215,218)}.get(pb, (226,227,229))
                pdesc = _safe_str(PILLAR_EA_DESC.get(pillar, ""))

                # Need ~28mm for header + bar + description
                if pdf.get_y() > 240:
                    pdf.add_page()

                y0 = pdf.get_y()
                # Pillar name + score badge
                pdf.set_x(14)
                pdf.set_fill_color(*NAVY)
                pdf.set_text_color(*WHITE)
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(100, 7, f"  {pillar}", fill=True)
                pdf.set_fill_color(*pf)
                pdf.set_text_color(*pc)
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(30, 7, f"  {ps:.1f}/5  {pb}", fill=True)
                pdf.ln(8)

                # Mini score bar
                bx, by, bw, bh = 14, pdf.get_y(), 130, 4
                pdf.set_fill_color(225, 230, 240)
                pdf.rect(bx, by, bw, bh, "F")
                filled = min(ps / 5.0, 1.0) * bw
                pdf.set_fill_color(*pc)
                pdf.rect(bx, by, filled, bh, "F")
                pdf.ln(bh + 2)

                # Pillar description
                pdf.set_x(16)
                pdf.set_font("Helvetica", "I", 7.5)
                pdf.set_text_color(*DGREY)
                pdf.multi_cell(178, 4, pdesc)
                pdf.ln(3)

        # ── 8-Dimension scorecard table ───────────────────────────────────────
        dims = maturity.get("dimensions", {})
        if dims:
            pdf.sub_title("8-Dimension Scorecard -- Evidence-Based Scores")
            pdf.table_header(["Dimension", "Pillar", "Score", "Band"], [62, 44, 20, 56])
            PILLAR_MAP = {
                "vision_and_strategy":       "Vision & Strategy",
                "organization":              "People",
                "leadership_and_governance": "People",
                "behaviour_and_culture":     "People",
                "metrics_and_analysis":      "Processes",
                "policy_and_standards":      "Processes",
                "enabling_processes":        "Processes",
                "tools_and_technology":      "Technology",
            }
            for i, dk in enumerate(DIM_ORDER):
                dv = dims.get(dk)
                if not isinstance(dv, dict):
                    continue
                s   = float(dv.get("score") or 0)
                b   = _safe_str(dv.get("band") or ("High" if s >= 3.5 else "Medium" if s >= 2.0 else "Low"))
                lbl = _safe_str(DIM_LABELS.get(dk, dk.replace("_", " ").title()))
                pil = _safe_str(PILLAR_MAP.get(dk, ""))
                pdf.table_row([lbl, pil, f"{s:.1f}/5", b], [62, 44, 20, 56], shade=i%2==0)
            pdf.ln(4)

        # ── Per-dimension detail: EA context + findings + improvements ─────────
        if dims:
            pdf.sub_title("Dimension Detail -- EA Context, Findings & Improvement Areas")
            for dk in DIM_ORDER:
                dv = dims.get(dk)
                if not isinstance(dv, dict):
                    continue
                s    = float(dv.get("score") or 0)
                b    = _safe_str(dv.get("band") or ("High" if s >= 3.5 else "Medium" if s >= 2.0 else "Low"))
                lbl  = _safe_str(DIM_LABELS.get(dk, dk.replace("_", " ").title()))
                ctx  = _safe_str(DIM_EA_CONTEXT.get(dk, ""))
                pos  = dv.get("positive_findings") or []
                imp  = dv.get("improvement_areas") or dv.get("gaps") or []

                # Need at least 60mm for header + bar + context; break early enough
                if pdf.get_y() > 190:
                    pdf.add_page()

                bc = {"High": GREEN, "Medium": AMBER, "Low": RED}.get(b, SLATE)
                bf = {"High": (212,237,218), "Medium": (255,243,205), "Low": (248,215,218)}.get(b, (226,227,229))

                # Dimension header row
                pdf.set_x(14)
                pdf.set_fill_color(*NAVY)
                pdf.set_text_color(*WHITE)
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(120, 7, f"  {lbl}", fill=True)
                pdf.set_fill_color(*bf)
                pdf.set_text_color(*bc)
                pdf.set_font("Helvetica", "B", 8)
                pdf.cell(62, 7, f"  {b}  --  {s:.1f} / 5", fill=True)
                pdf.ln(8)

                # Mini score bar — always drawn on same page as header
                bx2, by2, bw2, bh2 = 14, pdf.get_y(), 182, 3
                pdf.set_fill_color(225, 230, 240)
                pdf.rect(bx2, by2, bw2, bh2, "F")
                pdf.set_fill_color(*bc)
                pdf.rect(bx2, by2, min(s / 5.0, 1.0) * bw2, bh2, "F")
                pdf.ln(bh2 + 2)

                # EA context paragraph
                if ctx:
                    if pdf.get_y() > 260:
                        pdf.add_page()
                    pdf.set_x(16)
                    pdf.set_font("Helvetica", "I", 7.5)
                    pdf.set_text_color(*DGREY)
                    pdf.multi_cell(178, 3.8, ctx)
                    pdf.ln(1)

                # Positive findings
                if pos:
                    if pdf.get_y() > 255:
                        pdf.add_page()
                    pdf.set_x(16)
                    pdf.set_font("Helvetica", "B", 7.5)
                    pdf.set_text_color(21, 87, 36)
                    pdf.cell(0, 4, "Positive Findings:", ln=True)
                    for p in pos[:3]:
                        if pdf.get_y() > 268:
                            pdf.add_page()
                        pdf.set_x(20)
                        pdf.set_font("Helvetica", "", 7.5)
                        pdf.set_text_color(*BLACK)
                        pdf.cell(4, 4, "+")
                        pdf.multi_cell(174, 4, _safe_str(str(p)))

                # Improvement areas
                if imp:
                    if pdf.get_y() > 255:
                        pdf.add_page()
                    pdf.set_x(16)
                    pdf.set_font("Helvetica", "B", 7.5)
                    pdf.set_text_color(*RED)
                    pdf.cell(0, 4, "Improvement Areas:", ln=True)
                    for g in imp[:3]:
                        if pdf.get_y() > 268:
                            pdf.add_page()
                        pdf.set_x(20)
                        pdf.set_font("Helvetica", "", 7.5)
                        pdf.set_text_color(*BLACK)
                        pdf.cell(4, 4, "-")
                        pdf.multi_cell(174, 4, _safe_str(str(g)))

                pdf.ln(4)

        # ── Top priorities ────────────────────────────────────────────────────
        priorities = maturity.get("top_priorities", [])
        if priorities:
            pdf.sub_title("Top Improvement Priorities for EA")
            for i, p in enumerate(priorities[:6]):
                if pdf.get_y() > 270:
                    pdf.add_page()
                pdf.set_x(14)
                pdf.set_fill_color(*LGREY)
                pdf.set_font("Helvetica", "B", 8)
                pdf.set_text_color(*NAVY)
                pdf.cell(6, 5, f"{i+1}.", fill=True)
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*BLACK)
                pdf.multi_cell(176, 5, _safe_str(str(p)), fill=True)

        # ── Maturity improvement roadmap ──────────────────────────────────────
        roadmap = maturity.get("roadmap", [])
        if roadmap:
            pdf.sub_title("Maturity Improvement Roadmap")
            pdf.table_header(["Phase", "Key Actions"], [54, 128])
            for i, phase in enumerate(roadmap[:3]):
                acts = "; ".join(_safe_str(a) for a in phase.get("actions", [])[:3]) if isinstance(phase, dict) else _safe_str(str(phase))
                pdf.table_row(
                    [_safe_str(phase.get("phase",""))[:30] if isinstance(phase,dict) else f"Phase {i+1}", acts[:120]],
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
                pdf.multi_cell(174, 5, _safe_str(w, 110))

        # ── Maturity Insights subsection ─────────────────────────────────────
        mat_ins = insights.get("maturity_insights") or {}
        if mat_ins:
            if pdf.get_y() > 240:
                pdf.add_page()
            pdf.sub_title("EA Maturity Insights")

            # Summary narrative
            summary_text = _safe_str(mat_ins.get("summary", ""))
            if summary_text:
                pdf.set_x(14)
                pdf.set_font("Helvetica", "", 8)
                pdf.set_text_color(*BLACK)
                pdf.multi_cell(182, 5, summary_text)
                pdf.ln(3)

            # Target score + timeline banner
            target_score = mat_ins.get("target_maturity_score")
            timeline_str  = _safe_str(mat_ins.get("estimated_improvement_timeline", ""))
            if target_score or timeline_str:
                pdf.set_x(14)
                pdf.set_fill_color(*NAVY)
                pdf.set_text_color(255, 255, 255)
                pdf.set_font("Helvetica", "B", 8)
                banner = []
                if target_score:
                    banner.append(f"Target Maturity Score: {target_score}/5")
                if timeline_str:
                    banner.append(f"Improvement Timeline: {timeline_str}")
                pdf.cell(182, 7, "  " + "   |   ".join(banner), fill=True, ln=True)
                pdf.set_text_color(*BLACK)
                pdf.ln(3)

            # Capability Gaps
            gaps = mat_ins.get("capability_gaps", []) or []
            if gaps:
                pdf.sub_title("Key Capability Gaps")
                for g in gaps[:6]:
                    if pdf.get_y() > 275:
                        pdf.add_page()
                    pdf.set_x(18)
                    pdf.set_font("Helvetica", "", 8)
                    pdf.set_text_color(*BLACK)
                    pdf.cell(4, 5, "-")
                    pdf.multi_cell(174, 5, _safe_str(str(g)))

            # Dimension Priorities table
            dim_prios = mat_ins.get("dimension_priorities", []) or []
            if dim_prios:
                if pdf.get_y() > 220:
                    pdf.add_page()
                pdf.sub_title("Dimension Priorities")
                pdf.table_header(["Dimension", "Current", "Target", "Gap", "Action"], [54, 18, 18, 14, 78])
                for i, d in enumerate(dim_prios[:8]):
                    pdf.table_row([
                        _safe_str(str(d.get("dimension", "")))[:30],
                        str(d.get("current_score", "-")),
                        str(d.get("target_score", "-")),
                        str(d.get("gap", "-")),
                        _safe_str(str(d.get("action", "")))[:80],
                    ], [54, 18, 18, 14, 78], shade=i % 2 == 0)
                pdf.ln(3)

            # Maturity Recommendations
            mat_recs = mat_ins.get("maturity_recommendations", []) or []
            if mat_recs:
                if pdf.get_y() > 200:
                    pdf.add_page()
                pdf.sub_title("Maturity-Specific Recommendations")
                for r in mat_recs[:5]:
                    pdf.rec_card(
                        rank=str(r.get("rank", "-")),
                        title=_safe_str(str(r.get("recommendation", "")))[:80],
                        priority=_safe_str(str(r.get("pillar", ""))),
                        effort=_safe_str(str(r.get("pillar", ""))),
                        timeline=_safe_str(str(r.get("timeline", "-"))),
                        desc=_safe_str(str(r.get("expected_impact", "")))[:400],
                        impact="",
                    )

    def _pdf_methodology(self, pdf):
        pdf.section_title("A.", "Appendix -- Methodology & Scoring Framework")

        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(*NAVY)
        pdf.set_x(14)
        pdf.cell(0, 6, "Rationalization Framework", ln=True)
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
        gen_date    = _now().strftime("%d %B %Y  %H:%M")

        action_counts: Dict[str, int] = {}
        for t in tools:
            a = t.get("rationalization_action", "TBD")
            action_counts[a] = action_counts.get(a, 0) + 1

        assessment        = assessments[-1] if assessments else {}
        assessment_section = self._assessment_section([assessment] if assessment else [])
        tool_rows         = self._tool_rows(tools)
        dup_rows          = self._dup_rows(duplications)
        action_rows       = self._action_summary_rows(action_counts)
        time_rows         = self._time_summary_rows(tools)

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
.kpi{{background:#fff;padding:28px 16px;text-align:center;border-top:3px solid #0063DC;overflow:hidden}}
.kpi .val{{font-size:clamp(18px,2.2vw,30px);font-weight:700;color:#0a1628;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
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
  <div class="meta">Date of Issue: {gen_date}<br>Applications Assessed: {len(tools)}<br>Framework: 6R Rationalization Model<br>Classification: CONFIDENTIAL</div>
</div>
<div class="kpi-grid">
  <div class="kpi"><div class="val">{len(tools)}</div><div class="lbl">Applications Assessed</div></div>
  <div class="kpi"><div class="val">{_fmt_kpi(f"${total_cost:,.0f}")}</div><div class="lbl">Total Annual Spend</div></div>
  <div class="kpi"><div class="val">{len(duplications)}</div><div class="lbl">Overlap Pairs Found</div></div>
  <div class="kpi"><div class="val">{_fmt_kpi(f"${pot_savings:,.0f}")}</div><div class="lbl">Est. Annual Savings</div></div>
</div>
{assessment_section}
<div class="section">
  <h2><span class="num">2</span> Portfolio Classification Summary</h2>
  <div class="two-col">
    <table><thead><tr><th>Classification</th><th>Count</th><th>Portfolio %</th><th>Strategic Meaning</th></tr></thead><tbody>{time_rows}</tbody></table>
    <table><thead><tr><th>6R Action</th><th>Count</th><th>Portfolio %</th><th>Description</th></tr></thead><tbody>{action_rows}</tbody></table>
  </div>
</div>
<div class="section">
  <h2><span class="num">3</span> Application Portfolio Detail</h2>
  <table><thead><tr><th>Application</th><th>Vendor</th><th>Category</th><th>Annual Cost</th><th>Users</th><th>Score</th><th>TIME</th><th>6R Action</th><th>Confidence</th></tr></thead><tbody>{tool_rows}</tbody></table>
</div>
{self._dup_section(dup_rows) if duplications else ""}
<div class="footer">EA AI Intelligence  |  CONFIDENTIAL  |  {_now().strftime('%Y')}</div>
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
        # TIME framework removed — returns empty string, 6R breakdown used instead
        return ""

    _TIME_MEANING = {
        "Invest":    "High value & healthy tech -- retain and expand",
        "Tolerate":  "High value, aging tech -- keep but plan modernisation",
        "Migrate":   "Low value, healthy tech -- consolidate or repurpose",
        "Eliminate": "Low value & poor tech -- decommission priority",
    }

    def _time_summary_rows(self, tools):
        total = max(len(tools), 1)
        tc_counts: Dict[str, int] = {}
        for t in tools:
            tc = t.get("time_classification", "Eliminate")
            tc_counts[tc] = tc_counts.get(tc, 0) + 1
        rows = ""
        for tc in ["Invest", "Tolerate", "Migrate", "Eliminate"]:
            c = tc_counts.get(tc, 0)
            rows += (f'<tr><td><span class="badge badge-{tc.lower()}">{tc}</span></td>'
                     f'<td><strong>{c}</strong></td><td>{round(c/total*100)}%</td>'
                     f'<td>{self._TIME_MEANING.get(tc,"")}</td></tr>')
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
            tc   = t.get("time_classification","Eliminate")
            conf = t.get("confidence_level","Low")
            cost = f"${t.get('annual_cost',0):,.0f}" if t.get("annual_cost") else "-"
            rows += (f'<tr><td><strong>{t.get("name","-")}</strong></td>'
                     f'<td>{t.get("vendor") or "-"}</td><td>{t.get("category","-")}</td>'
                     f'<td>{cost}</td><td>{t.get("user_count","-")}</td>'
                     f'<td><strong>{t.get("composite_score","-")}</strong>/10</td>'
                     f'<td><span class="badge badge-{tc.lower()}">{tc}</span></td>'
                     f'<td><span class="badge badge-{act.lower()}">{act}</span></td>'
                     f'<td><span class="badge badge-{conf.lower()}">{conf}</span></td></tr>')
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

    # ── Full-pipeline HTML report ─────────────────────────────────────────────

    def generate_pipeline_html(self, pipeline: dict) -> str:
        """Return the full-pipeline HTML report as a string."""
        return self._build_pipeline_html(_deep_sanitize(pipeline))

    def _build_pipeline_html(self, pipeline: dict) -> str:  # noqa: C901
        """Build a comprehensive HTML report covering all 4 pipeline stages."""
        summary       = pipeline.get("pipeline_summary", {})
        time_data     = pipeline.get("TIME", {}) or {}
        arb_data      = pipeline.get("ARB", {}) or {}
        mapping_data  = pipeline.get("MAPPING", {}) or {}
        maturity_data = pipeline.get("MATURITY", {}) or {}
        insights_data = pipeline.get("INSIGHTS", {}) or {}

        apps          = time_data.get("applications", [])
        dups          = time_data.get("duplications", [])
        # /time/ingest returns "summary"; run_time() returns "portfolio_summary" — support both
        time_summary  = time_data.get("portfolio_summary") or time_data.get("summary", {}) or {}
        time_assess   = time_data.get("assessment", {}) or {}

        total_cost    = time_summary.get("total_annual_cost", 0) or sum(a.get("annual_cost") or 0 for a in apps)
        pot_savings   = time_summary.get("potential_savings", 0) or sum(d.get("potential_annual_savings", 0) for d in dups)
        dups_count    = time_summary.get("duplications_found", 0) or len(dups)
        mat_score     = maturity_data.get("overall_maturity_score") or maturity_data.get("overall_score") or "-"
        mat_band      = str(maturity_data.get("overall_band") or maturity_data.get("maturity_level") or "-")
        _rp_html      = (insights_data.get("risk_profile") or {}) if isinstance(insights_data.get("risk_profile"), dict) else {}
        overall_risk  = str(_rp_html.get("overall_risk") or insights_data.get("overall_risk") or "").strip().upper()
        if not overall_risk or overall_risk in ("-", "NONE", "N/A", "NA", "NULL"):
            _rh = sum(1 for a in apps if a.get("rationalization_action","") in ("Retire","Replace"))
            _eh = sum(1 for a in apps if a.get("end_of_life"))
            overall_risk = "HIGH" if (_rh >= 5 or _eh >= 3) else "MEDIUM" if (_rh >= 2 or _eh >= 1) else "LOW" if apps else "-"
        gen_date      = _now().strftime("%d %B %Y  %H:%M")
        industry      = summary.get("industry", "")
        ea_framework  = summary.get("ea_framework", "")

        # ── helpers ──────────────────────────────────────────────────────────
        def badge(text, css=""):
            t = str(text or "").strip()
            cls = css or f"badge-{t.lower().replace(' ','')}"
            return f'<span class="badge {cls}">{t}</span>'

        def risk_badge(r):
            m = {"LOW": "badge-low", "MEDIUM": "badge-medium",
                 "HIGH": "badge-high", "CRITICAL": "badge-critical"}
            return badge(r, m.get(str(r).upper(), "badge-medium"))

        def section(num, title, content):
            return (f'<div class="section" id="s{num}">'
                    f'<h2><span class="num">{num}</span>{title}</h2>'
                    f'{content}</div>')

        def exec_box(text, label=""):
            lbl = f'<div class="exec-label">{label}</div>' if label else ""
            return f'<div class="exec-box">{lbl}{str(text or "").strip()}</div>'

        def kv_table(rows):
            trs = "".join(
                f'<tr><td class="kv-key">{k}</td><td class="kv-val">{v}</td></tr>'
                for k, v in rows if v not in (None, "", {}, [])
            )
            return f'<table class="kv-table"><tbody>{trs}</tbody></table>' if trs else ""

        def data_table(headers, rows_html):
            ths = "".join(f"<th>{h}</th>" for h in headers)
            return (f'<div class="tbl-wrap"><table>'
                    f'<thead><tr>{ths}</tr></thead>'
                    f'<tbody>{rows_html}</tbody></table></div>')

        def list_items(items, icon="&rsaquo;"):
            if not items:
                return ""
            lis = "".join(f'<li><span class="li-icon">{icon}</span>{str(i)}</li>' for i in items if i)
            return f'<ul class="bullet-list">{lis}</ul>'

        def phase_block(color, phase, subtitle, items):
            lis = "".join(f"<li>{i}</li>" for i in (items if isinstance(items, list) else [items]) if i)
            return (f'<div class="phase-card" style="border-top-color:{color}">'
                    f'<strong>{phase}</strong>'
                    f'<small>{subtitle}</small>'
                    f'<ul>{lis}</ul></div>')

        # ── Section 1: Executive Intelligence Summary ─────────────────────────
        ins_exec   = insights_data.get("executive_summary", "")
        time_exec  = time_assess.get("executive_summary", "") or time_assess.get("overview", "")
        fin        = insights_data.get("financial_impact", {}) or {}
        quick_wins = insights_data.get("quick_wins", []) or []

        fin_rows = ""
        for k, v in fin.items():
            if v:
                if isinstance(v, dict):
                    v_str = "  |  ".join(f"{dk.replace('_',' ')}: {dv}" for dk, dv in v.items() if dv)
                elif isinstance(v, list):
                    v_str = ",  ".join(str(x) for x in v[:3])
                else:
                    v_str = str(v)
                fin_rows += f'<tr><td class="kv-key">{k.replace("_"," ").title()}</td><td class="kv-val">{v_str}</td></tr>'
        fin_block = (f'<div class="subsection"><h3>Financial Impact</h3>'
                     f'<table class="kv-table"><tbody>{fin_rows}</tbody></table></div>') if fin_rows else ""

        qw_block = ""
        if quick_wins:
            qw_block = (f'<div class="subsection"><h3>Quick Wins</h3>'
                        + list_items(quick_wins, "&rsaquo;") + "</div>")

        # ── Portfolio stats summary (always shown in Section 1) ──────────────────
        _action_counts_s1: Dict[str, int] = {}
        for _t in apps:
            _a = _t.get("rationalization_action", "TBD")
            _action_counts_s1[_a] = _action_counts_s1.get(_a, 0) + 1
        _action_badges = "".join(
            f'<span style="display:inline-block;margin:2px 4px;padding:3px 10px;border-radius:4px;font-size:11px;font-weight:700;background:#e0e7f0;color:#0a1628">{a}: {c}</span>'
            for a, c in _action_counts_s1.items() if c > 0
        )
        _portfolio_bar = ""
        if apps:
            _portfolio_bar = (
                f'<div class="subsection" style="background:#f8fbff;border:1px solid #dde4f0;border-radius:6px;padding:16px 20px;margin-bottom:16px">'
                f'<div style="display:flex;flex-wrap:wrap;gap:16px;align-items:center">'
                f'<div><div style="font-size:20px;font-weight:700;color:#0a1628">{len(apps)}</div><div style="font-size:10px;color:#666;text-transform:uppercase">Applications</div></div>'
                f'<div><div style="font-size:20px;font-weight:700;color:#0a1628">${total_cost:,.0f}</div><div style="font-size:10px;color:#666;text-transform:uppercase">Annual Spend</div></div>'
                f'<div><div style="font-size:20px;font-weight:700;color:#28a745">${pot_savings:,.0f}</div><div style="font-size:10px;color:#666;text-transform:uppercase">Est. Savings</div></div>'
                f'<div><div style="font-size:20px;font-weight:700;color:#dc3545">{dups_count}</div><div style="font-size:10px;color:#666;text-transform:uppercase">Duplications</div></div>'
                f'<div><div style="font-size:20px;font-weight:700;color:#0063DC">{mat_score}/5</div><div style="font-size:10px;color:#666;text-transform:uppercase">EA Maturity</div></div>'
                f'</div>'
                f'<div style="margin-top:10px;font-size:11px;font-weight:700;color:#555;text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px">6R Action Breakdown</div>'
                f'<div>{_action_badges}</div>'
                f'</div>'
            )

        s1_content = ""
        if ins_exec:
            s1_content += exec_box(ins_exec, "COMBINED INTELLIGENCE — EXECUTIVE SUMMARY (TIME · 6R · ARB · MAPPING · MATURITY)")
        if time_exec and time_exec != ins_exec:
            s1_content += exec_box(time_exec, "PORTFOLIO — RATIONALIZATION SUMMARY")
        if not ins_exec and not time_exec and apps:
            # Auto-generate a narrative summary from portfolio data
            _ret_n  = sum(1 for a in apps if a.get("rationalization_action","") in ("Retire","Replace"))
            _ref_n  = sum(1 for a in apps if a.get("rationalization_action","") in ("Refactor","Replatform","Rehost"))
            _rtn_n  = sum(1 for a in apps if a.get("rationalization_action","") == "Retain")
            _fallback_html = (
                f"This intelligence report consolidates AI-driven analysis of <strong>{len(apps)} enterprise applications</strong> "
                f"with a combined annual portfolio spend of <strong>${total_cost:,.0f}</strong>. "
                f"The analysis identifies <strong>${pot_savings:,.0f}</strong> in estimated annual savings through strategic rationalisation. "
                f"Portfolio breakdown: <strong>{_rtn_n}</strong> applications recommended for retention, "
                f"<strong>{_ret_n}</strong> flagged for retirement or replacement, and <strong>{_ref_n}</strong> earmarked for refactoring or migration. "
                f"EA Maturity is assessed at <strong>{mat_score}/5</strong> ({mat_band}). "
                f"Overall portfolio risk is classified as <strong>{overall_risk}</strong>."
            )
            s1_content += exec_box(_fallback_html, "PORTFOLIO — AI INTELLIGENCE SUMMARY")
        s1_content += _portfolio_bar + fin_block + qw_block

        # ── Section 2: Portfolio Rationalization (TIME) ───────────────────────
        action_counts: Dict[str, int] = {}
        for t in apps:
            a = t.get("rationalization_action", "TBD")
            action_counts[a] = action_counts.get(a, 0) + 1
        total_apps = max(len(apps), 1)

        act_rows = ""
        for a in ["Retain", "Rehost", "Replatform", "Refactor", "Replace", "Retire"]:
            c = action_counts.get(a, 0)
            if c == 0:
                continue
            pct = round(c / total_apps * 100)
            bar = f'<div class="pct-bar"><div class="pct-fill" style="width:{pct}%"></div></div>'
            act_rows += (f'<tr><td>{badge(a, f"badge-{a.lower()}")}</td>'
                         f'<td><strong>{c}</strong></td>'
                         f'<td>{bar} {pct}%</td>'
                         f'<td>{ACTION_DESC.get(a,"")}</td></tr>')

        action_table = data_table(["6R Action", "Count", "Portfolio %", "Description"], act_rows)

        app_rows = ""
        for t in apps:
            act  = t.get("rationalization_action", "TBD")
            conf = t.get("confidence_level", "Low")
            cost = f"${t.get('annual_cost',0):,.0f}" if t.get("annual_cost") else "—"
            app_rows += (f'<tr><td><strong>{t.get("name","—")}</strong></td>'
                         f'<td>{t.get("vendor") or "—"}</td>'
                         f'<td>{t.get("category","—")}</td>'
                         f'<td>{cost}</td>'
                         f'<td>{t.get("user_count","—")}</td>'
                         f'<td><strong>{t.get("composite_score","—")}</strong>/10</td>'
                         f'<td>{badge(act, f"badge-{act.lower()}")}</td>'
                         f'<td>{badge(conf, f"badge-{conf.lower()}")}</td></tr>')
        app_table = data_table(
            ["Application", "Vendor", "Category", "Annual Cost", "Users", "Score", "6R Action", "Confidence"],
            app_rows)

        dup_rows_html = ""
        for d in dups[:15]:
            prio = d.get("priority", "Low")
            dup_rows_html += (f'<tr><td>{d.get("category","—")}</td>'
                              f'<td>{d.get("tool_a","—")}</td>'
                              f'<td>{d.get("tool_b","—")}</td>'
                              f'<td><strong>{d.get("overlap_percentage",0)}%</strong></td>'
                              f'<td><strong>{d.get("retain_candidate","—")}</strong></td>'
                              f'<td>{d.get("consolidate_candidate","—")}</td>'
                              f'<td>${d.get("potential_annual_savings",0):,.0f}</td>'
                              f'<td>{badge(prio, f"badge-{prio.lower()}")}</td></tr>')
        dup_section_html = ""
        if dups:
            dup_section_html = (f'<div class="subsection"><h3>Duplication & Consolidation Opportunities</h3>'
                                + data_table(["Category","Tool A","Tool B","Overlap","Retain",
                                              "Consolidate","Est. Savings","Priority"], dup_rows_html)
                                + "</div>")

        roadmap_t = time_assess.get("roadmap", {}) or {}
        roadmap_block = ""
        if roadmap_t:
            roadmap_block = (f'<div class="subsection"><h3>Portfolio Transformation Roadmap</h3>'
                             f'<div class="phase-grid">'
                             + phase_block("#00A651", "Phase 1 — 0–6 Months", "Foundation & Quick Wins",
                                          roadmap_t.get("short_term", []))
                             + phase_block("#0063DC", "Phase 2 — 6–18 Months", "Execution & Migration",
                                          roadmap_t.get("medium_term", []))
                             + phase_block("#7B2FBE", "Phase 3 — 18–24 Months", "Optimisation & Embedding",
                                          roadmap_t.get("long_term", []))
                             + '</div></div>')

        # TIME quadrant summary table for Section 2
        tc_counts2: Dict[str, int] = {}
        for t in apps:
            tc_counts2[t.get("time_classification", "Eliminate")] = tc_counts2.get(t.get("time_classification", "Eliminate"), 0) + 1
        TIME_DESC2 = {
            "Invest":    "High business value + healthy tech — retain and grow",
            "Tolerate":  "High value, aging tech — maintain and plan modernisation",
            "Migrate":   "Low value, healthy tech — consolidate or repurpose",
            "Eliminate": "Low value + poor tech — decommission priority",
        }
        time_rows2 = ""
        for tc in ["Invest", "Tolerate", "Migrate", "Eliminate"]:
            c2 = tc_counts2.get(tc, 0)
            time_rows2 += (f'<tr><td>{badge(tc, f"badge-{tc.lower()}")}</td>'
                           f'<td><strong>{c2}</strong></td>'
                           f'<td>{round(c2/total_apps*100)}%</td>'
                           f'<td>{TIME_DESC2.get(tc,"")}</td></tr>')
        time_table2 = data_table(["TIME Quadrant", "Count", "Portfolio %", "Strategic Meaning"], time_rows2)

        s2_exec_html = (f'<div class="subsection">{exec_box(time_exec, "RATIONALIZATION — AI ANALYSIS")}</div>') if time_exec else ""
        s2_content = (
            s2_exec_html
            + f'<div class="subsection"><div style="display:grid;grid-template-columns:1fr 1fr;gap:16px"><div><h3>TIME Framework Classification</h3>{time_table2}</div><div><h3>6R Action Breakdown</h3>{action_table}</div></div></div>'
            + f'<div class="subsection"><h3>Application Portfolio Detail</h3>{app_table}</div>'
            + dup_section_html + roadmap_block
        )

        # ── Section 3: ARB Governance ─────────────────────────────────────────
        arb_decision  = str(arb_data.get("decision", "") or "").upper()
        arb_conf      = arb_data.get("confidence_score", 0)
        arb_comp      = arb_data.get("compliance_score", 0)
        arb_complex   = str(arb_data.get("integration_complexity", "—") or "—")
        arb_reasoning = str(arb_data.get("reasoning", "") or "")
        arb_conds     = arb_data.get("conditions", []) or []
        arb_risks     = arb_data.get("risks", []) or []
        arb_recs      = arb_data.get("recommendations", []) or []
        arb_patterns  = arb_data.get("anti_patterns_detected", []) or []

        dec_colors = {"APPROVED": "#155724", "REJECTED": "#721c24", "CONDITIONAL": "#856404"}
        dec_bg     = {"APPROVED": "#d4edda",  "REJECTED": "#f8d7da",  "CONDITIONAL": "#fff3cd"}
        dc  = dec_colors.get(arb_decision, "#383d41")
        dbg = dec_bg.get(arb_decision, "#e2e3e5")

        if arb_decision:
            arb_banner = (f'<div class="decision-banner" style="background:{dbg};color:{dc};border-color:{dc}">'
                          f'ARB Decision: <strong>{arb_decision}</strong></div>')
            arb_scores = (f'<div class="score-grid">'
                          f'<div class="score-card"><div class="score-val">{arb_conf}/100</div>'
                          f'<div class="score-lbl">Confidence Score</div></div>'
                          f'<div class="score-card"><div class="score-val">{arb_comp}/100</div>'
                          f'<div class="score-lbl">Compliance Score</div></div>'
                          f'<div class="score-card"><div class="score-val">{arb_complex}</div>'
                          f'<div class="score-lbl">Integration Complexity</div></div>'
                          f'</div>')
            arb_reason_html = (f'<div class="subsection"><h3>ARB Reasoning</h3>'
                               f'{exec_box(arb_reasoning)}</div>') if arb_reasoning else ""
            max_r = max(len(arb_conds), len(arb_risks), len(arb_recs), 1)
            cri_rows = ""
            for i in range(min(max_r, 6)):
                c   = arb_conds[i] if i < len(arb_conds) else ""
                r   = arb_risks[i]  if i < len(arb_risks)  else ""
                rec = arb_recs[i]   if i < len(arb_recs)   else ""
                cri_rows += f"<tr><td>{c}</td><td>{r}</td><td>{rec}</td></tr>"
            cri_html = ""
            if cri_rows:
                cri_html = (f'<div class="subsection"><h3>Conditions, Risks & Recommendations</h3>'
                            + data_table(["Conditions", "Risk Flags", "Recommendations"], cri_rows)
                            + "</div>")
            pat_html = ""
            if arb_patterns:
                pat_html = (f'<div class="subsection"><h3>Anti-Patterns Detected</h3>'
                            + list_items(arb_patterns, "⚠") + "</div>")
            # Sign-off audit trail
            signoff_h   = arb_data.get("signoff") or {}
            signoff_html = ""
            if signoff_h and not signoff_h.get("skipped"):
                eff_dec   = str(signoff_h.get("effective_decision", "—")).upper()
                ai_dec_h  = str(signoff_h.get("ai_decision", "—")).upper()
                signed_ts = str(signoff_h.get("signed_at", "—"))[:19].replace("T", " ")
                eff_bg    = {"APPROVED": "#d4edda", "REJECTED": "#f8d7da", "CONDITIONAL": "#fff3cd", "PENDING_MORE_INFO": "#e2e3e5"}.get(eff_dec, "#e2e3e5")
                eff_c     = {"APPROVED": "#155724", "REJECTED": "#721c24", "CONDITIONAL": "#856404", "PENDING_MORE_INFO": "#383d41"}.get(eff_dec, "#383d41")
                arch_h    = signoff_h.get("architect") or {}
                cio_h     = signoff_h.get("cio") or {}
                arch_dec_lbl = {
                    "accept": "Accepted AI Decision",
                    "override_approved": "Overrode → APPROVED",
                    "override_conditional": "Overrode → CONDITIONAL",
                    "override_rejected": "Overrode → REJECTED",
                }.get(arch_h.get("decision", "accept"), arch_h.get("decision", "—"))
                cio_dec_lbl = {
                    "approved": "Approved",
                    "rejected": "Rejected",
                    "more_info": "Requested More Info",
                }.get((cio_h or {}).get("decision", ""), (cio_h or {}).get("decision", "—"))
                signoff_rows = ""
                if arch_h.get("name"):
                    signoff_rows += f'<tr><td><strong>Architect</strong></td><td>{arch_h.get("name","—")}</td><td>{arch_dec_lbl}</td><td>{arch_h.get("notes","—")}</td></tr>'
                if cio_h and cio_h.get("name"):
                    signoff_rows += f'<tr><td><strong>CIO</strong></td><td>{cio_h.get("name","—")}</td><td>{cio_dec_lbl}</td><td>{cio_h.get("notes","—")}</td></tr>'
                signoff_html = (
                    f'<div class="subsection" style="border-left:4px solid #0063DC;padding-left:12px">'
                    f'<h3 style="color:#0063DC">Human Sign-off Audit Trail</h3>'
                    f'<div class="decision-banner" style="background:{eff_bg};color:{eff_c};border-color:{eff_c};margin-bottom:10px">'
                    f'Effective Decision: <strong>{eff_dec}</strong>&nbsp;&nbsp;|&nbsp;&nbsp;AI Recommended: {ai_dec_h}&nbsp;&nbsp;|&nbsp;&nbsp;Signed: {signed_ts}</div>'
                    + (data_table(["Role", "Name", "Decision", "Notes"], signoff_rows) if signoff_rows else "")
                    + "</div>"
                )
            s3_content = arb_banner + arb_scores + arb_reason_html + cri_html + pat_html + signoff_html
        else:
            s3_content = '<p class="muted">ARB governance review was not completed for this pipeline run.</p>'

        # ── Section 4: Dependency & Impact Analysis (MAPPING) ─────────────────
        if mapping_data.get("skipped"):
            s4_content = f'<p class="muted">{mapping_data.get("reason","No apps flagged for dependency analysis.")}</p>'
        else:
            overall_impact = str(mapping_data.get("overall_impact_level", "—") or "—")
            map_ctx = str(mapping_data.get("pipeline_context", "") or "")
            app_analyses = mapping_data.get("app_analyses", []) or []
            mig_order    = mapping_data.get("recommended_migration_order", []) or []

            impact_colors = {"LOW": "#155724", "MEDIUM": "#856404", "HIGH": "#721c24", "CRITICAL": "#5a0a12"}
            impact_bg     = {"LOW": "#d4edda",  "MEDIUM": "#fff3cd",  "HIGH": "#f8d7da",  "CRITICAL": "#f5c6cb"}
            ic  = impact_colors.get(overall_impact.upper(), "#383d41")
            ibg = impact_bg.get(overall_impact.upper(), "#e2e3e5")

            imp_banner = (f'<div class="decision-banner" style="background:{ibg};color:{ic};border-color:{ic}">'
                          f'Overall Portfolio Impact Level: <strong>{overall_impact}</strong></div>')

            ctx_html = f'<div class="subsection">{exec_box(map_ctx, "MAPPING CONTEXT")}</div>' if map_ctx else ""

            dep_rows = ""
            for i, a in enumerate(app_analyses):
                deps = ", ".join((a.get("direct_dependencies") or [])[:4])
                il   = str(a.get("impact_level", "—") or "—")
                dep_rows += (f'<tr><td><strong>{a.get("app_name","—")}</strong></td>'
                             f'<td>{badge(a.get("rationalization_action","—"), "badge-" + str(a.get("rationalization_action","")).lower())}</td>'
                             f'<td>{badge(il, "badge-" + il.lower())}</td>'
                             f'<td>{a.get("coupling_score","—")}/10</td>'
                             f'<td>{deps or "—"}</td>'
                             f'<td>{", ".join((a.get("single_points_of_failure") or [])[:2]) or "—"}</td></tr>')

            dep_table_html = ""
            if dep_rows:
                dep_table_html = (f'<div class="subsection"><h3>Per-Application Dependency Analysis</h3>'
                                  + data_table(["Application", "6R Action", "Impact", "Coupling",
                                                "Direct Dependencies", "SPOFs"], dep_rows)
                                  + "</div>")

            mig_html = ""
            if mig_order:
                mig_items = "".join(
                    f'<li><span class="step-num">{i+1}</span>{str(app)}</li>'
                    for i, app in enumerate(mig_order))
                mig_html = (f'<div class="subsection"><h3>Recommended Migration Sequence</h3>'
                            f'<ol class="migration-list">{mig_items}</ol></div>')

            s4_content = imp_banner + ctx_html + dep_table_html + mig_html

        # ── Section 4b: Compliance Gap Analysis ───────────────────────────────
        compliance_data  = pipeline.get("COMPLIANCE", {}) or {}
        has_compliance_h = bool(compliance_data) and not compliance_data.get("skipped")
        s4b_content      = ""
        if has_compliance_h:
            comp_score   = compliance_data.get("overall_compliance_score")
            regs_checked = compliance_data.get("regulations_checked", [])
            reg_sum      = compliance_data.get("regulation_summary", {}) or {}
            comp_app_map = compliance_data.get("app_compliance_map", []) or []
            comp_crit    = compliance_data.get("critical_gaps", []) or []
            comp_road    = compliance_data.get("remediation_roadmap", []) or []

            # Score badge
            score_html = ""
            if comp_score is not None:
                sc = int(comp_score)
                if sc >= 80:
                    sc_bg, sc_c = "#d4edda", "#155724"
                elif sc >= 50:
                    sc_bg, sc_c = "#fff3cd", "#856404"
                else:
                    sc_bg, sc_c = "#f8d7da", "#721c24"
                score_html = (f'<div class="decision-banner" style="background:{sc_bg};color:{sc_c};border-color:{sc_c}">'
                              f'Overall Compliance Score: <strong>{sc}/100</strong></div>')

            regs_html = (f'<p style="font-size:12px;color:#555;margin:4px 0 12px 0">'
                         f'Regulations assessed: <strong>{", ".join(regs_checked)}</strong></p>') if regs_checked else ""

            # Regulation summary table
            reg_rows = ""
            for reg, rd in reg_sum.items():
                risk = str(rd.get("risk", "—"))
                r_bg = {"HIGH": "#f8d7da", "CRITICAL": "#f5c6cb", "MEDIUM": "#fff3cd", "LOW": "#d4edda"}.get(risk.upper(), "#e2e3e5")
                r_c  = {"HIGH": "#721c24", "CRITICAL": "#5a0a12", "MEDIUM": "#856404", "LOW": "#155724"}.get(risk.upper(), "#383d41")
                reg_rows += (f'<tr><td><strong>{reg}</strong></td>'
                             f'<td style="text-align:center">{rd.get("apps_affected","—")}</td>'
                             f'<td style="text-align:center">{rd.get("gaps_count","—")}</td>'
                             f'<td style="text-align:center">{rd.get("non_compliant_count","—")}</td>'
                             f'<td><span style="background:{r_bg};color:{r_c};padding:2px 8px;border-radius:4px;font-size:11px;font-weight:700">{risk}</span></td></tr>')
            reg_table_html = ""
            if reg_rows:
                reg_table_html = (f'<div class="subsection"><h3>Regulation Summary</h3>'
                                  + data_table(["Regulation", "Apps Affected", "Gaps Found", "Non-Compliant", "Risk Level"], reg_rows)
                                  + "</div>")

            # Per-app compliance table
            app_rows = ""
            status_colors_h = {
                "COMPLIANT":     ("#d4edda", "#155724"),
                "PARTIAL":       ("#fff3cd", "#856404"),
                "NON_COMPLIANT": ("#f8d7da", "#721c24"),
                "UNKNOWN":       ("#e2e3e5", "#383d41"),
            }
            for a in comp_app_map:
                st = str(a.get("compliance_status", "UNKNOWN")).upper()
                st_bg, st_c = status_colors_h.get(st, ("#e2e3e5", "#383d41"))
                first_gap   = (a.get("gaps") or ["—"])[0]
                app_rows += (f'<tr><td><strong>{a.get("app_name","—")}</strong></td>'
                             f'<td><span style="background:{st_bg};color:{st_c};padding:2px 7px;border-radius:4px;font-size:11px;font-weight:700">{st}</span></td>'
                             f'<td>{badge(a.get("risk_level","—"), "badge-" + str(a.get("risk_level","")).lower())}</td>'
                             f'<td>{a.get("data_classification","—")}</td>'
                             f'<td>{first_gap}</td></tr>')
            app_table_html = ""
            if app_rows:
                app_table_html = (f'<div class="subsection"><h3>Per-Application Compliance Assessment</h3>'
                                  + data_table(["Application", "Status", "Risk", "Data Classification", "Key Gap"], app_rows)
                                  + "</div>")

            # Critical gaps box
            crit_html = ""
            if comp_crit:
                items = "".join(f"<li>{g}</li>" for g in comp_crit[:5])
                crit_html = (f'<div class="subsection" style="background:#fff5f5;border-left:4px solid #c0392b;padding:10px 14px">'
                             f'<h3 style="color:#c0392b">Critical Compliance Gaps</h3><ul>{items}</ul></div>')

            # Remediation roadmap
            road_html = ""
            if comp_road:
                items = "".join(f'<li><span class="step-num">{i+1}</span>{r}</li>' for i, r in enumerate(comp_road[:6]))
                road_html = (f'<div class="subsection"><h3>Remediation Roadmap</h3>'
                             f'<ol class="migration-list">{items}</ol></div>')

            s4b_content = score_html + regs_html + reg_table_html + app_table_html + crit_html + road_html

        # ── Section 5: EA Maturity Assessment ─────────────────────────────────
        DIM_ORDER = ["vision_and_strategy", "organization", "leadership_and_governance",
                     "behaviour_and_culture", "metrics_and_analysis", "policy_and_standards",
                     "enabling_processes", "tools_and_technology"]
        DIM_LABELS = {
            "vision_and_strategy":        "Vision & Strategy",
            "organization":               "Organization",
            "leadership_and_governance":  "Leadership & Governance",
            "behaviour_and_culture":      "Behaviour & Culture",
            "metrics_and_analysis":       "Metrics & Analysis",
            "policy_and_standards":       "Policy & Standards",
            "enabling_processes":         "Enabling Processes",
            "tools_and_technology":       "Tools & Technology",
        }
        PILLAR_MAP = {
            "vision_and_strategy":       "Vision & Strategy",
            "organization":              "People",
            "leadership_and_governance": "People",
            "behaviour_and_culture":     "People",
            "metrics_and_analysis":      "Processes",
            "policy_and_standards":      "Processes",
            "enabling_processes":        "Processes",
            "tools_and_technology":      "Technology",
        }

        if maturity_data or mat_score != "-":
            band_c  = {"High": "#155724", "Medium": "#856404", "Low": "#721c24"}.get(mat_band, "#383d41")
            band_bg = {"High": "#d4edda",  "Medium": "#fff3cd",  "Low": "#f8d7da" }.get(mat_band, "#e2e3e5")

            mat_score_f  = float(mat_score) if str(mat_score).replace('.','').isdigit() else 0
            bar_pct_ov   = round((mat_score_f / 5.0) * 100)
            band_desc_ov = MATURITY_BAND_DESC.get(mat_band, "")
            gauge_svg    = _svg_speedo_gauge(mat_score_f)
            mat_banner = (
                f'<div class="mat-banner">'
                f'<div class="mat-score" style="border:none;border-radius:0;padding:0;width:160px;height:auto;flex-shrink:0">'
                f'{gauge_svg}'
                f'</div>'
                f'<div style="flex:1">'
                f'<div class="mat-band" style="background:{band_bg};color:{band_c}">{mat_band} Maturity</div>'
                f'<div class="mat-lbl">EA Maturity Score — KPMG 4-Pillar Framework</div>'
                f'<div class="mat-gauge">'
                f'<div style="position:relative;height:10px;border-radius:6px;overflow:hidden;background:linear-gradient(to right,#dc3545 0%,#dc3545 40%,#ffa500 40%,#ffa500 70%,#28a745 70%,#28a745 100%)">'
                f'<div style="position:absolute;top:-2px;left:{bar_pct_ov}%;width:3px;height:14px;background:#0a1628;border-radius:2px;transform:translateX(-50%)"></div>'
                f'</div>'
                f'<div style="display:flex;justify-content:space-between;font-size:10px;color:#888;margin-top:2px">'
                f'<span>Low (0)</span><span>Medium (2.0)</span><span>High (3.5)</span><span>5.0</span></div>'
                f'</div>'
                + (f'<div style="font-size:11px;color:{band_c};font-style:italic;margin-top:6px;padding:6px 10px;background:{band_bg};border-radius:4px">{band_desc_ov}</div>' if band_desc_ov else '')
                + f'</div></div>'
                + f'<div class="mat-intro"><strong>Assessment basis:</strong> Evidence from a structured 30-question assessment covering 8 dimensions across 4 pillars (Vision &amp; Strategy, People, Processes, Technology). Scores are anchored to respondent evidence and directly drive the improvement roadmap below.</div>'
            )

            dims = maturity_data.get("dimensions", {}) or {}

            # ── Compute pillar scores from dimensions if not directly provided ──
            pillar_scores = maturity_data.get("pillar_scores", {}) or {}
            _PILLAR_DIM_MAP = {
                "Vision & Strategy": ["vision_and_strategy"],
                "People":            ["organization", "leadership_and_governance", "behaviour_and_culture"],
                "Processes":         ["metrics_and_analysis", "policy_and_standards", "enabling_processes"],
                "Technology":        ["tools_and_technology"],
            }
            if not pillar_scores or all(float(pillar_scores.get(p) or 0) == 0 for p in pillar_scores):
                pillar_scores = {}
                for pil, keys in _PILLAR_DIM_MAP.items():
                    pscores = [
                        float(dims[k].get("score") or 0)
                        for k in keys
                        if isinstance(dims.get(k), dict) and dims[k].get("score")
                    ]
                    if pscores:
                        pillar_scores[pil] = round(sum(pscores) / len(pscores), 2)

            PILLAR_ORDER_HTML = ["Vision & Strategy", "People", "Processes", "Technology"]
            pil_cards = ""
            for pillar in PILLAR_ORDER_HTML:
                ps = float(pillar_scores.get(pillar) or 0)
                if ps == 0:
                    continue
                pb  = "High" if ps >= 3.5 else "Medium" if ps >= 2.0 else "Low"
                pc  = {"High": "#155724", "Medium": "#856404", "Low": "#721c24"}.get(pb, "#383d41")
                pbg = {"High": "#d4edda",  "Medium": "#fff3cd",  "Low": "#f8d7da" }.get(pb, "#e2e3e5")
                pdesc = PILLAR_EA_DESC.get(pillar, "")
                pbarpct = round((ps / 5.0) * 100)
                pil_cards += (
                    f'<div class="pillar-card" style="border-top-color:{pc}">'
                    f'<div class="pillar-name">{pillar}</div>'
                    f'<div class="pillar-score" style="color:{pc}">{ps:.1f}/5</div>'
                    f'<div class="pillar-band" style="background:{pbg};color:{pc}">{pb}</div>'
                    f'<div class="pct-bar" style="margin-top:8px"><div class="pct-fill" style="width:{pbarpct}%;background:{pc}"></div></div>'
                    + (f'<div style="font-size:10px;color:#666;margin-top:6px;line-height:1.4">{pdesc}</div>' if pdesc else '')
                    + f'</div>'
                )
            pillar_html = ""
            if pil_cards:
                pillar_html = (f'<div class="subsection"><h3>4-Pillar Scores — KPMG EA Maturity Framework</h3>'
                               f'<div class="pillar-grid">{pil_cards}</div></div>')

            dim_rows = ""
            for dk in DIM_ORDER:
                dv = dims.get(dk)
                if not isinstance(dv, dict):
                    continue
                s   = dv.get("score", 0) or 0
                b   = str(dv.get("band") or ("High" if s >= 4 else "Medium" if s >= 3 else "Low"))
                lbl = DIM_LABELS.get(dk, dk.replace("_", " ").title())
                pil = PILLAR_MAP.get(dk, "")
                bc  = {"High": "#155724", "Medium": "#856404", "Low": "#721c24"}.get(b, "#383d41")
                bbg = {"High": "#d4edda",  "Medium": "#fff3cd",  "Low": "#f8d7da"}.get(b, "#e2e3e5")
                bar_w = round((s / 5) * 100)
                dim_rows += (f'<tr><td><strong>{lbl}</strong></td>'
                             f'<td>{pil}</td>'
                             f'<td><div class="pct-bar"><div class="pct-fill" style="width:{bar_w}%;background:{bc}"></div></div> {s:.1f}/5</td>'
                             f'<td><span class="badge" style="background:{bbg};color:{bc}">{b}</span></td></tr>')
            dim_table_html = ""
            if dim_rows:
                dim_table_html = (f'<div class="subsection"><h3>8 Dimensions — Maturity Scorecard</h3>'
                                  + data_table(["Dimension", "Pillar", "Score", "Band"], dim_rows)
                                  + "</div>")

            dim_cards_html = ""
            for dk in DIM_ORDER:
                dv = dims.get(dk)
                if not isinstance(dv, dict):
                    continue
                s    = float(dv.get("score") or 0)
                b    = str(dv.get("band") or ("High" if s >= 3.5 else "Medium" if s >= 2.0 else "Low"))
                lbl  = DIM_LABELS.get(dk, dk.replace("_", " ").title())
                ctx  = DIM_EA_CONTEXT.get(dk, "")
                pos  = dv.get("positive_findings") or []
                gaps = dv.get("improvement_areas") or dv.get("gaps") or []
                bc   = {"High": "#155724", "Medium": "#856404", "Low": "#721c24"}.get(b, "#383d41")
                bbg  = {"High": "#d4edda",  "Medium": "#fff3cd",  "Low": "#f8d7da"}.get(b, "#e2e3e5")
                bar_pct = round((s / 5.0) * 100)
                pos_li  = "".join(f'<li class="pos-item">&#43; {p}</li>' for p in pos[:3])
                gap_li  = "".join(f'<li class="gap-item">&#8722; {g}</li>' for g in gaps[:3])
                dim_cards_html += (
                    f'<div class="dim-card">'
                    f'<div class="dim-header">'
                    f'<span class="dim-name">{lbl}</span>'
                    f'<span class="dim-score" style="background:{bbg};color:{bc}">{b} · {s:.1f}/5</span>'
                    f'</div>'
                    f'<div class="pct-bar" style="margin-bottom:6px"><div class="pct-fill" style="width:{bar_pct}%;background:{bc}"></div></div>'
                    + (f'<p class="dim-ctx">{ctx}</p>' if ctx else '')
                    + (f'<ul class="dim-findings">{pos_li}{gap_li}</ul>' if (pos_li or gap_li) else '')
                    + f'</div>'
                )

            detail_html = ""
            if dim_cards_html:
                detail_html = (f'<div class="subsection"><h3>Dimension Detail — EA Context, Findings &amp; Improvement Areas</h3>'
                               f'<div class="dim-grid">{dim_cards_html}</div></div>')

            priorities = maturity_data.get("top_priorities", []) or []
            pri_html = ""
            if priorities:
                pri_html = (f'<div class="subsection"><h3>Top Improvement Priorities</h3>'
                            + list_items([str(p) for p in priorities[:6]], "→") + "</div>")

            mat_roadmap = maturity_data.get("roadmap", []) or []
            mat_roadmap_html = ""
            if mat_roadmap:
                rm_rows = ""
                for i, phase in enumerate(mat_roadmap[:4]):
                    if isinstance(phase, dict):
                        ph_name = phase.get("phase", f"Phase {i+1}")
                        acts = "; ".join(str(a) for a in phase.get("actions", [])[:3])
                    else:
                        ph_name = f"Phase {i+1}"
                        acts = str(phase)
                    rm_rows += f"<tr><td><strong>{ph_name}</strong></td><td>{acts}</td></tr>"
                mat_roadmap_html = (f'<div class="subsection"><h3>Maturity Improvement Roadmap</h3>'
                                    + data_table(["Phase", "Key Actions"], rm_rows) + "</div>")

            s5_content = mat_banner + pillar_html + dim_table_html + detail_html + pri_html + mat_roadmap_html
        else:
            s5_content = '<p class="muted">Maturity assessment data not available.</p>'

        # ── Section 6: Strategic Recommendations (INSIGHTS) ───────────────────
        strat_recs  = insights_data.get("strategic_recommendations", []) or []
        top_risks   = insights_data.get("risk_profile", {}).get("top_risks", []) or []
        kpis        = insights_data.get("kpis", []) or []
        outcomes    = time_assess.get("expected_outcomes", {}) or {}

        # Combined Intelligence narrative — if the INSIGHTS agent itself
        # returned no strategic_recommendations, synthesise an elaborated,
        # cross-stage view from TIME/ARB/MAPPING/MATURITY data (same logic
        # the PDF report uses) so this section is never left blank.
        synth_narrative_html = ""
        if not strat_recs:
            _synth = _synthesize_recommendations(
                apps, arb_data, mapping_data, maturity_data, total_cost, pot_savings, overall_risk
            )
            strat_recs = _synth["recommendations"]
            synth_narrative_html = exec_box(_synth["narrative"], "COMBINED INTELLIGENCE — CROSS-STAGE SYNTHESIS")

        rec_cards_html = ""
        for r in strat_recs[:7]:
            effort   = str(r.get("effort", "Medium") or "Medium")
            ec = {"LOW": "#155724", "MEDIUM": "#856404", "HIGH": "#721c24"}.get(effort.upper(), "#383d41")
            ebg= {"LOW": "#d4edda",  "MEDIUM": "#fff3cd",  "HIGH": "#f8d7da" }.get(effort.upper(), "#e2e3e5")
            rec_cards_html += (f'<div class="rec-card">'
                               f'<div class="rec-header">'
                               f'<span class="rec-rank">#{r.get("priority","—")}</span>'
                               f'<span class="rec-title">{r.get("recommendation","")}</span>'
                               f'<span class="rec-effort" style="background:{ebg};color:{ec}">{effort}</span>'
                               f'</div>'
                               f'<p class="rec-value">{r.get("business_value","")}</p>'
                               f'<div class="rec-meta">Timeline: {r.get("timeline","—")}</div>'
                               f'</div>')

        risk_rows = ""
        for i, r in enumerate(top_risks[:6]):
            risk_rows += (f'<tr><td>{r.get("risk","")}</td>'
                          f'<td>{r.get("impact","")}</td>'
                          f'<td>{r.get("mitigation","")}</td></tr>')
        risk_html = ""
        if risk_rows:
            risk_html = (f'<div class="subsection"><h3>Risk Register</h3>'
                         + data_table(["Risk", "Business Impact", "Mitigation"], risk_rows) + "</div>")

        kpi_rows = ""
        for k in kpis[:8]:
            kpi_rows += (f'<tr><td><strong>{k.get("metric","")}</strong></td>'
                         f'<td>{k.get("current","—")}</td>'
                         f'<td>{k.get("target","—")}</td>'
                         f'<td>{k.get("timeframe","—")}</td></tr>')
        kpi_html = ""
        if kpi_rows:
            kpi_html = (f'<div class="subsection"><h3>Key Performance Indicators</h3>'
                        + data_table(["KPI", "Current", "Target", "Timeframe"], kpi_rows) + "</div>")

        outcome_rows = ""
        for k, v in outcomes.items():
            outcome_rows += f'<tr><td class="kv-key">{k.replace("_"," ").title()}</td><td class="kv-val">{v}</td></tr>'
        outcome_html = ""
        if outcome_rows:
            outcome_html = (f'<div class="subsection"><h3>Expected Business Outcomes</h3>'
                            f'<table class="kv-table"><tbody>{outcome_rows}</tbody></table></div>')

        # ── Maturity Insights (HTML) ──────────────────────────────────────────
        mat_ins = insights_data.get("maturity_insights") or {}
        mat_ins_html = ""
        if mat_ins:
            mi_summary = mat_ins.get("summary", "")
            mi_target  = mat_ins.get("target_maturity_score", "")
            mi_tl      = mat_ins.get("estimated_improvement_timeline", "")
            mi_gaps    = mat_ins.get("capability_gaps", []) or []
            mi_dims    = mat_ins.get("dimension_priorities", []) or []
            mi_recs    = mat_ins.get("maturity_recommendations", []) or []

            banner_parts = []
            if mi_target:
                banner_parts.append(f'<span class="mi-badge" style="background:#0a1628;color:#fff">Target Score: {mi_target}/5</span>')
            if mi_tl:
                banner_parts.append(f'<span class="mi-badge" style="background:#0063DC;color:#fff">{mi_tl}</span>')
            banner_html = "".join(banner_parts)

            gap_pills = "".join(
                f'<span class="mi-gap-pill">{g}</span>' for g in mi_gaps[:6]
            )

            dim_rows = ""
            for d in mi_dims[:8]:
                cur  = d.get("current_score", "-")
                tgt  = d.get("target_score", "-")
                gap  = d.get("gap", "-")
                try:
                    bar_w = min(100, int(float(cur) / 5 * 100))
                except Exception:
                    bar_w = 0
                dim_rows += (
                    f'<tr>'
                    f'<td><strong>{d.get("dimension","")}</strong></td>'
                    f'<td><div style="display:flex;align-items:center;gap:6px">'
                    f'<div style="width:80px;background:#e0e7f0;border-radius:4px;height:8px">'
                    f'<div style="width:{bar_w}%;background:#0063DC;height:8px;border-radius:4px"></div></div>'
                    f'<span>{cur}</span></div></td>'
                    f'<td>{tgt}</td>'
                    f'<td><strong style="color:#dc3545">{gap}</strong></td>'
                    f'<td style="font-size:11.5px">{d.get("action","")}</td>'
                    f'</tr>'
                )
            dim_table = ""
            if dim_rows:
                dim_table = (
                    f'<div class="subsection"><h3>Dimension Priorities</h3>'
                    + data_table(["Dimension", "Current Score", "Target", "Gap", "Action"], dim_rows)
                    + "</div>"
                )

            pillar_colors = {
                "vision & strategy": "#7c3aed", "people": "#1d4ed8",
                "processes": "#16a34a", "technology": "#d97706",
            }
            mr_cards = ""
            for r in mi_recs[:5]:
                pillar = str(r.get("pillar", "")).strip()
                pc = pillar_colors.get(pillar.lower(), "#383d41")
                mr_cards += (
                    f'<div class="rec-card" style="border-left:4px solid {pc}">'
                    f'<div class="rec-header">'
                    f'<span class="rec-rank">#{r.get("rank","—")}</span>'
                    f'<span class="rec-title">{r.get("recommendation","")}</span>'
                    f'<span class="rec-effort" style="background:{pc}22;color:{pc}">{pillar}</span>'
                    f'</div>'
                    f'<p class="rec-value">{r.get("expected_impact","")}</p>'
                    f'<div class="rec-meta">Timeline: {r.get("timeline","—")}</div>'
                    f'</div>'
                )

            mat_ins_html = f"""
<div class="subsection" style="border-top:2px solid #0063DC;padding-top:20px;margin-top:28px">
  <h3 style="color:#0a1628;font-size:15px;margin-bottom:12px">EA Maturity Insights</h3>
  <div style="display:flex;gap:8px;flex-wrap:wrap;margin-bottom:14px">{banner_html}</div>
  <div class="exec-box" style="margin-bottom:16px">{mi_summary}</div>
  {'<div class="subsection"><h3>Key Capability Gaps</h3><div style="display:flex;flex-wrap:wrap;gap:8px">' + gap_pills + '</div></div>' if gap_pills else ''}
  {dim_table}
  {'<div class="subsection"><h3>Maturity Recommendations</h3>' + mr_cards + '</div>' if mr_cards else ''}
</div>
<style>
.mi-badge{{display:inline-block;padding:5px 14px;border-radius:20px;font-size:12px;font-weight:600}}
.mi-gap-pill{{background:#fde8e8;color:#c0392b;padding:4px 12px;border-radius:20px;font-size:11.5px;font-weight:600}}
</style>"""

        # ── Section 6 coverage banner ─────────────────────────────────────────
        stages_covered_s6 = []
        if apps:
            stages_covered_s6.append("Portfolio Rationalization (TIME · 6R)")
        if arb_data.get("decision"):
            stages_covered_s6.append("ARB Governance")
        if mapping_data and not mapping_data.get("skipped"):
            stages_covered_s6.append("Dependency Analysis (MAPPING)")
        if maturity_data or mat_score != "-":
            stages_covered_s6.append("EA Maturity Assessment")
        cov_chips = "".join(
            f'<span style="display:inline-block;padding:3px 12px;border-radius:12px;font-size:11px;font-weight:700;background:#e8eeff;color:#0a1628;margin:2px 4px">{s}</span>'
            for s in stages_covered_s6
        )
        cov_bar = (
            f'<div style="background:#f0f4ff;border:1px solid #dde4f0;border-radius:6px;padding:12px 16px;margin-bottom:20px">'
            f'<div style="font-size:10px;font-weight:700;color:#0063DC;text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px">Intelligence synthesised from all pipeline stages</div>'
            f'<div>{cov_chips}</div>'
            f'</div>'
        ) if stages_covered_s6 else ""

        s6_content = cov_bar + synth_narrative_html
        if rec_cards_html:
            s6_content += f'<div class="subsection"><h3>Strategic Recommendations — Combined Intelligence</h3>{rec_cards_html}</div>'
        s6_content += risk_html + kpi_html + outcome_html + mat_ins_html

        # ── KPI grid ─────────────────────────────────────────────────────────
        risk_cls = {"LOW": "kpi-low", "MEDIUM": "kpi-medium",
                    "HIGH": "kpi-high", "CRITICAL": "kpi-critical"}.get(overall_risk.upper(), "")

        kpi_grid = f"""<div class="kpi-grid">
  <div class="kpi"><div class="val">{len(apps)}</div><div class="lbl">Applications Assessed</div></div>
  <div class="kpi"><div class="val">{_fmt_kpi(f"${total_cost:,.0f}")}</div><div class="lbl">Annual Portfolio Spend</div></div>
  <div class="kpi"><div class="val">{_fmt_kpi(f"${pot_savings:,.0f}")}</div><div class="lbl">Est. Annual Savings</div></div>
  <div class="kpi"><div class="val">{dups_count}</div><div class="lbl">No. of Duplications</div></div>
  <div class="kpi"><div class="val">{mat_score}/5</div><div class="lbl">EA Maturity Score</div></div>
  <div class="kpi {risk_cls}"><div class="val">{overall_risk}</div><div class="lbl">Overall Risk Level</div></div>
</div>"""

        meta_chips = ""
        for label, val in [("Industry", industry), ("Framework", ea_framework),
                            ("Cloud Strategy", summary.get("cloud_strategy","")),
                            ("Governance", summary.get("governance",""))]:
            if val:
                meta_chips += f'<span class="chip">{label}: {val}</span>'

        stages_done = " &rarr; ".join(summary.get("stages_completed", []))

        # ── Dynamic section numbering — skipped stages (ARB / MAPPING) are
        # omitted entirely, not shown with a placeholder, so numbering never
        # has gaps and always matches what's actually in the report.
        has_arb      = bool(arb_decision)
        has_mapping  = bool(mapping_data) and not mapping_data.get("skipped")
        has_maturity = bool(maturity_data) or mat_score != "-"

        sections_html = []
        _n = 1
        sections_html.append(section(str(_n), "Executive Intelligence Summary", s1_content)); _n += 1
        sections_html.append(section(str(_n), "Portfolio Rationalization <small style='font-weight:400;font-size:13px;margin-left:6px'>TIME · 6R Framework</small>", s2_content)); _n += 1
        if has_arb:
            sections_html.append(section(str(_n), "Architecture Review Board &mdash; Governance Decision", s3_content)); _n += 1
        if has_mapping:
            sections_html.append(section(str(_n), "Dependency &amp; Impact Analysis <small style='font-weight:400;font-size:13px;margin-left:6px'>MAPPING</small>", s4_content)); _n += 1
        if has_compliance_h:
            sections_html.append(section(str(_n), "Compliance Gap Analysis <small style='font-weight:400;font-size:13px;margin-left:6px'>REGULATORY MAPPING</small>", s4b_content)); _n += 1
        if has_maturity:
            sections_html.append(section(str(_n), "EA Maturity Assessment <small style='font-weight:400;font-size:13px;margin-left:6px'>KPMG 4-Pillar / 8-Dimension Framework</small>", s5_content)); _n += 1
        sections_html.append(section(str(_n), "Strategic Recommendations &amp; Intelligence <small style='font-weight:400;font-size:13px;margin-left:6px'>INSIGHTS</small>", s6_content)); _n += 1
        sections_joined = "\n".join(sections_html)

        return f"""<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>EA Full Intelligence Report</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
body{{font-family:'Segoe UI',Arial,sans-serif;background:#f0f4fa;color:#1a2340;font-size:14px;line-height:1.6}}
.report{{max-width:1380px;margin:0 auto;background:#fff;box-shadow:0 0 40px rgba(0,0,0,.12)}}
.cover{{background:#0a1628;color:#fff;padding:52px 44px 40px;border-top:6px solid #0063DC}}
.cover h1{{font-size:28px;font-weight:700;line-height:1.3;margin-bottom:10px}}
.cover .sub{{opacity:.7;font-size:13px;margin-bottom:16px}}
.cover .meta{{font-size:12px;opacity:.55;line-height:2}}
.stages-bar{{background:#0d1f3c;padding:10px 44px;font-size:12px;color:#6b8ab0;letter-spacing:.5px}}
.chips{{padding:12px 44px;background:#f8fbff;border-bottom:1px solid #e0e7f0;display:flex;flex-wrap:wrap;gap:8px}}
.chip{{background:#e8eeff;color:#0a1628;padding:4px 12px;border-radius:12px;font-size:11px;font-weight:600}}
.kpi-grid{{display:grid;grid-template-columns:repeat(6,1fr);gap:1px;background:#e0e7f0}}
@media(max-width:900px){{.kpi-grid{{grid-template-columns:repeat(3,1fr)}}}}
.kpi{{background:#fff;padding:22px 14px;text-align:center;border-top:3px solid #0063DC;overflow:hidden}}
.kpi.kpi-high{{border-top-color:#dc3545}}.kpi.kpi-critical{{border-top-color:#7b0d1e}}
.kpi.kpi-medium{{border-top-color:#ffc107}}.kpi.kpi-low{{border-top-color:#28a745}}
.kpi .val{{font-size:clamp(16px,1.8vw,26px);font-weight:700;color:#0a1628;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.kpi .lbl{{font-size:10px;color:#666;text-transform:uppercase;letter-spacing:.8px;margin-top:5px}}
.section{{padding:36px 44px;border-bottom:1px solid #eef1f8}}
h2{{font-size:17px;font-weight:700;color:#0a1628;margin-bottom:20px;padding-bottom:10px;
    border-bottom:2px solid #0063DC;display:flex;align-items:center;gap:10px}}
.num{{background:#0a1628;color:#fff;min-width:28px;height:28px;border-radius:4px;
      display:inline-flex;align-items:center;justify-content:center;font-size:12px;padding:0 6px}}
h3{{font-size:14px;font-weight:700;color:#0a1628;margin:0 0 12px}}
.subsection{{margin-top:24px}}
.exec-box{{background:#f8fbff;border-left:4px solid #0063DC;padding:20px 24px;
           line-height:1.8;white-space:pre-wrap;font-size:13px;border-radius:0 4px 4px 0}}
.exec-label{{font-size:10px;font-weight:700;letter-spacing:1px;color:#0063DC;
             text-transform:uppercase;margin-bottom:8px}}
.tbl-wrap{{overflow-x:auto}}
table{{width:100%;border-collapse:collapse;font-size:12.5px}}
thead th{{background:#0a1628;color:#fff;padding:10px 12px;text-align:left;
          font-weight:600;font-size:11px;letter-spacing:.3px;white-space:nowrap}}
tbody td{{padding:9px 12px;border-bottom:1px solid #f0f3fa;vertical-align:top}}
tbody tr:nth-child(even){{background:#f8fbff}}
.kv-table{{width:auto;min-width:340px}}
.kv-table .kv-key{{font-weight:600;color:#555;width:220px;white-space:nowrap}}
.kv-table .kv-val{{color:#1a2340}}
.badge{{display:inline-block;padding:2px 9px;border-radius:3px;font-size:11px;font-weight:700;letter-spacing:.2px;white-space:nowrap}}
.badge-retain,.badge-invest{{color:#155724;background:#d4edda}}
.badge-rehost{{color:#004085;background:#cce5ff}}
.badge-replatform{{color:#856404;background:#fff3cd}}
.badge-refactor{{color:#7d3c00;background:#fde8d8}}
.badge-replace,.badge-eliminate{{color:#721c24;background:#f8d7da}}
.badge-retire{{color:#383d41;background:#e2e3e5}}
.badge-high,.badge-critical{{color:#721c24;background:#f8d7da}}
.badge-medium{{color:#856404;background:#fff3cd}}
.badge-low{{color:#155724;background:#d4edda}}
.pct-bar{{display:inline-block;width:80px;height:8px;background:#e0e7f0;
           border-radius:4px;vertical-align:middle;margin-right:6px}}
.pct-fill{{height:100%;border-radius:4px;background:#0063DC}}
.decision-banner{{padding:14px 20px;border-radius:4px;border-left:5px solid;
                  font-size:15px;margin-bottom:18px;font-weight:600}}
.score-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:12px;margin-bottom:20px}}
.score-card{{background:#f8fbff;border:1px solid #dde4f0;border-radius:6px;padding:16px;text-align:center}}
.score-val{{font-size:22px;font-weight:700;color:#0a1628}}
.score-lbl{{font-size:11px;color:#666;margin-top:4px;text-transform:uppercase;letter-spacing:.5px}}
.phase-grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin-top:8px}}
@media(max-width:800px){{.phase-grid{{grid-template-columns:1fr}}}}
.phase-card{{padding:16px;background:#f8fbff;border-top:4px solid #0063DC;border-radius:0 0 4px 4px}}
.phase-card strong{{display:block;margin-bottom:2px;font-size:13px;color:#0a1628}}
.phase-card small{{display:block;font-size:11px;color:#666;margin-bottom:10px}}
.phase-card ul{{padding-left:18px;font-size:12.5px;color:#333}}
.phase-card li{{margin-bottom:4px}}
.mat-banner{{display:flex;align-items:flex-start;gap:20px;padding:20px;
             background:#f8fbff;border:1px solid #dde4f0;border-radius:8px;margin-bottom:16px}}
.mat-score{{border:4px solid #0063DC;border-radius:50%;width:80px;height:80px;
            display:flex;align-items:center;justify-content:center;flex-shrink:0;flex-direction:column;background:#fff}}
.mat-val{{font-size:26px;font-weight:700;color:#0a1628;line-height:1}}
.mat-max{{font-size:11px;color:#666}}
.mat-band{{display:inline-block;padding:4px 14px;border-radius:12px;font-weight:700;
           font-size:13px;margin-bottom:4px}}
.mat-lbl{{font-size:12px;color:#666;margin-bottom:8px}}
.mat-gauge{{margin:6px 0 2px}}
.mat-intro{{font-size:11.5px;color:#445;padding:10px 14px;background:#eef4ff;border-left:4px solid #0063DC;border-radius:0 6px 6px 0;margin-bottom:16px;line-height:1.6}}
.pillar-grid{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}
@media(max-width:700px){{.pillar-grid{{grid-template-columns:repeat(2,1fr)}}}}
.pillar-card{{padding:16px;background:#f8fbff;border:1px solid #dde4f0;
              border-top:4px solid;border-radius:0 0 6px 6px;text-align:center}}
.pillar-name{{font-size:12px;color:#555;margin-bottom:6px;font-weight:600}}
.pillar-score{{font-size:22px;font-weight:700;margin-bottom:6px}}
.pillar-band{{display:inline-block;padding:2px 10px;border-radius:10px;font-size:11px;font-weight:700}}
.dim-grid{{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}}
@media(max-width:700px){{.dim-grid{{grid-template-columns:1fr}}}}
.dim-card{{border:1px solid #dde4f0;border-radius:4px;padding:14px}}
.dim-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:8px}}
.dim-name{{font-weight:700;font-size:13px;color:#0a1628}}
.dim-score{{padding:2px 10px;border-radius:10px;font-size:11px;font-weight:700}}
.dim-findings{{padding-left:0;list-style:none;font-size:12px}}
.dim-findings li{{padding:2px 0;}}
.pos-item{{color:#155724}}.gap-item{{color:#721c24}}
.rec-card{{border:1px solid #dde4f0;border-left:4px solid #0063DC;padding:16px;
           margin-bottom:10px;background:#f8fbff;border-radius:0 4px 4px 0}}
.rec-header{{display:flex;align-items:flex-start;gap:10px;margin-bottom:6px;flex-wrap:wrap}}
.rec-rank{{background:#0a1628;color:#fff;padding:2px 8px;border-radius:3px;font-size:11px;font-weight:700;white-space:nowrap}}
.rec-title{{font-weight:700;font-size:13px;color:#0a1628;flex:1}}
.rec-effort{{padding:2px 9px;border-radius:10px;font-size:11px;font-weight:700;white-space:nowrap}}
.rec-value{{font-size:12.5px;color:#444;margin-bottom:4px}}
.rec-meta{{font-size:11px;color:#0063DC}}
.bullet-list{{padding-left:0;list-style:none;font-size:13px}}
.bullet-list li{{padding:4px 0;display:flex;gap:8px}}
.li-icon{{color:#0063DC;font-weight:700;flex-shrink:0}}
.migration-list{{padding-left:0;list-style:none;font-size:13px}}
.migration-list li{{display:flex;align-items:center;gap:12px;padding:6px 0;
                    border-bottom:1px solid #f0f3fa}}
.step-num{{background:#0063DC;color:#fff;width:24px;height:24px;border-radius:50%;
           display:inline-flex;align-items:center;justify-content:center;
           font-size:11px;font-weight:700;flex-shrink:0}}
.muted{{color:#888;font-style:italic;padding:12px 0}}
.footer{{background:#0a1628;color:#8899bb;padding:20px 44px;font-size:12px;text-align:center}}
</style></head><body>
<div class="report">
<div class="cover">
  <h1>EA AI Intelligence<br>Full Enterprise Architecture Report</h1>
  <div class="sub">Portfolio Rationalization &nbsp;|&nbsp; Dependency Analysis &nbsp;|&nbsp; EA Maturity Assessment &nbsp;|&nbsp; Executive Intelligence</div>
  <div class="meta">Date of Issue: {gen_date} &nbsp;|&nbsp; Applications Assessed: {len(apps)} &nbsp;|&nbsp; Classification: CONFIDENTIAL</div>
</div>
<div class="stages-bar">Pipeline Stages Completed: &nbsp;<strong>{stages_done}</strong></div>
{f'<div class="chips">{meta_chips}</div>' if meta_chips else ""}
{kpi_grid}
{sections_joined}
<div class="footer">EA AI Intelligence &nbsp;|&nbsp; CONFIDENTIAL &nbsp;|&nbsp; {_now().strftime("%Y")} &nbsp;|&nbsp; KPMG EA Maturity Framework &nbsp;|&nbsp; 6R Cloud Migration Model</div>
</div></body></html>"""

