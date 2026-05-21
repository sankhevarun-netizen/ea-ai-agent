from collections import defaultdict
from typing import List, Dict


class DuplicationDetector:

    def detect_duplications(self, tools: List[Dict]) -> List[Dict]:
        by_category: Dict[str, List[Dict]] = defaultdict(list)
        for t in tools:
            by_category[t.get("category", "Other")].append(t)

        duplications = []
        for category, group in by_category.items():
            if len(group) < 2:
                continue
            for i in range(len(group)):
                for j in range(i + 1, len(group)):
                    a, b = group[i], group[j]
                    overlap = self._overlap_score(a, b)
                    if overlap >= 0.45:
                        duplications.append(self._build_record(a, b, overlap, category))

        return sorted(duplications, key=lambda x: x["overlap_percentage"], reverse=True)

    def _overlap_score(self, a: Dict, b: Dict) -> float:
        score = 0.35  # same category baseline
        sub_a = (a.get("subcategory") or "").lower()
        sub_b = (b.get("subcategory") or "").lower()
        if sub_a and sub_b and sub_a == sub_b:
            score += 0.25
        bu_a = (a.get("business_unit") or "").lower()
        bu_b = (b.get("business_unit") or "").lower()
        if bu_a and bu_b and bu_a == bu_b:
            score += 0.15
        v_a = (a.get("vendor") or "").lower()
        v_b = (b.get("vendor") or "").lower()
        if v_a and v_b and v_a != v_b:
            score += 0.10
        u_a = a.get("user_count") or 0
        u_b = b.get("user_count") or 0
        if u_a > 0 and u_b > 0 and min(u_a, u_b) / max(u_a, u_b) > 0.5:
            score += 0.10
        return min(1.0, score)

    def _build_record(self, a: Dict, b: Dict, overlap: float, category: str) -> Dict:
        overlap_pct = round(overlap * 100)
        score_a = a.get("composite_score") or 5.0
        score_b = b.get("composite_score") or 5.0
        retain, consolidate = (a, b) if score_a >= score_b else (b, a)
        retain_score = max(score_a, score_b)
        consol_score = min(score_a, score_b)

        cost_a = a.get("annual_cost") or 0
        cost_b = b.get("annual_cost") or 0
        potential_savings = round(min(cost_a, cost_b) * (overlap / 2))
        priority = "High" if overlap_pct >= 70 else "Medium" if overlap_pct >= 55 else "Low"

        uid_a = (a.get("id") or "xxxx")[:8]
        uid_b = (b.get("id") or "yyyy")[:8]

        return {
            "id": f"dup-{uid_a}-{uid_b}",
            "category": category,
            "tool_a": a.get("name", "Unknown"),
            "tool_b": b.get("name", "Unknown"),
            "overlap_percentage": overlap_pct,
            "retain_candidate": retain.get("name"),
            "consolidate_candidate": consolidate.get("name"),
            "rationale": (
                f"{a.get('name')} and {b.get('name')} show {overlap_pct}% functional overlap "
                f"in the {category} domain. {retain.get('name')} is the strategic retention "
                f"candidate (score: {retain_score:.1f} vs {consol_score:.1f}). "
                f"Consolidating onto {retain.get('name')} could yield ~${potential_savings:,}/year."
            ),
            "potential_annual_savings": potential_savings,
            "priority": priority,
        }
