from typing import Dict, Optional


CATEGORY_BASE_VALUE = {
    "BSS": 9.0, "OSS": 9.0, "CRM": 8.5, "ERP": 8.5,
    "Security": 8.5, "Network": 8.0, "Database": 8.0,
    "Cloud": 7.5, "Analytics": 7.5, "ITSM": 7.0,
    "Monitoring": 6.5, "Logging": 6.5, "APM": 6.5,
    "DevOps": 6.0, "Collaboration": 5.5, "Storage": 6.0,
    "Other": 4.5,
}

CRITICALITY_MODIFIER = {
    "Critical": +2.0, "High": +1.0, "Medium": 0.0, "Low": -1.5, None: 0.0,
}

TIER1_VENDORS = {
    "microsoft", "aws", "amazon", "google", "oracle", "sap", "salesforce",
    "servicenow", "splunk", "dynatrace", "datadog", "ibm", "cisco",
    "vmware", "palo alto", "crowdstrike", "zscaler", "elastic",
}

# 6R → TIME mapping
SIX_R_TO_TIME = {
    "Retain": "INVEST",
    "Rehost": "MIGRATE",
    "Replatform": "MIGRATE",
    "Refactor": "MIGRATE",
    "Replace": "ELIMINATE",
    "Retire": "ELIMINATE",
}


class ScoringEngine:

    def score_tool(self, tool: Dict) -> Dict[str, float]:
        return {
            "business_value": self._business_value(tool),
            "adoption_rate": self._adoption_rate(tool),
            "integration_depth": self._integration_depth(tool),
            "vendor_support": self._vendor_support(tool),
            "cost_efficiency": self._cost_efficiency(tool),
            "technical_health": self._technical_health(tool),
            "risk_score": self._risk_score(tool),
        }

    def composite_score(self, scores: Dict[str, float]) -> float:
        weights = {
            "business_value": 0.25,
            "adoption_rate": 0.15,
            "integration_depth": 0.15,
            "vendor_support": 0.15,
            "cost_efficiency": 0.15,
            "technical_health": 0.15,
        }
        weighted = sum(scores.get(k, 5.0) * w for k, w in weights.items())
        risk = scores.get("risk_score", 5.0)
        penalty = max(0.0, (risk - 5.0) * 0.15)
        return round(min(10.0, max(0.0, weighted - penalty)), 2)

    def determine_6r_action(self, scores: Dict[str, float], tool: Dict) -> str:
        composite = self.composite_score(scores)
        risk = scores.get("risk_score", 5.0)
        adoption = scores.get("adoption_rate", 5.0)
        cost_eff = scores.get("cost_efficiency", 5.0)
        tech = scores.get("technical_health", 5.0)
        eol = tool.get("end_of_life", False)
        deployment = (tool.get("deployment") or "").lower()

        if eol or composite < 2.5:
            return "Retire"
        if composite < 3.5 and adoption < 3.0:
            return "Retire"
        if composite < 4.5 and cost_eff < 3.0:
            return "Replace"
        if risk >= 8.5 and composite < 6.0:
            return "Replace"
        if composite >= 7.5 and risk <= 4.0:
            return "Retain"
        if composite >= 6.5 and risk <= 5.0:
            return "Retain"
        if composite >= 6.0 and "on-prem" in deployment and tech >= 5.0:
            return "Rehost"
        if composite >= 5.5 and tech < 5.5:
            return "Replatform"
        if composite >= 4.0 and tech < 4.5:
            return "Refactor"
        if composite >= 6.0:
            return "Retain"
        return "Replatform"

    def determine_time_classification(self, scores: Dict[str, float], tool: Dict) -> str:
        """Map 6R action to TIME classification."""
        action_6r = self.determine_6r_action(scores, tool)
        composite = self.composite_score(scores)

        # Tolerate: functional but not strategic — mid-range scores, no urgent action
        if action_6r in ("Rehost", "Replatform", "Refactor"):
            if composite >= 5.0:
                return "TOLERATE"
            return "MIGRATE"

        return SIX_R_TO_TIME.get(action_6r, "TOLERATE")

    def confidence_level(self, tool: Dict) -> str:
        known_fields = sum(
            1 for f in ["annual_cost", "user_count", "criticality", "vendor",
                        "integrations", "age_years", "deployment"]
            if tool.get(f) is not None
        )
        if known_fields >= 5:
            return "High"
        if known_fields >= 3:
            return "Medium"
        return "Low"

    # --- Dimension Scorers ---

    def _business_value(self, tool: Dict) -> float:
        base = CATEGORY_BASE_VALUE.get(tool.get("category", "Other"), 4.5)
        mod = CRITICALITY_MODIFIER.get(tool.get("criticality"), 0.0)
        return round(min(10.0, max(0.0, base + mod)), 2)

    def _adoption_rate(self, tool: Dict) -> float:
        users = tool.get("user_count") or 0
        if users == 0:
            return 5.0
        if users >= 2000: return 9.5
        if users >= 1000: return 9.0
        if users >= 500:  return 8.0
        if users >= 200:  return 7.0
        if users >= 100:  return 6.0
        if users >= 50:   return 5.0
        if users >= 20:   return 4.0
        if users >= 10:   return 3.0
        return 2.0

    def _integration_depth(self, tool: Dict) -> float:
        integrations = tool.get("integrations") or 0
        if integrations == 0:  return 5.0
        if integrations >= 25: return 9.5
        if integrations >= 15: return 8.5
        if integrations >= 10: return 7.5
        if integrations >= 5:  return 6.5
        if integrations >= 3:  return 5.5
        return 4.0

    def _vendor_support(self, tool: Dict) -> float:
        if tool.get("end_of_life"):
            return 1.0
        vendor = (tool.get("vendor") or "").lower()
        if any(v in vendor for v in TIER1_VENDORS):
            return 8.5
        if vendor:
            return 6.5
        return 5.0

    def _cost_efficiency(self, tool: Dict) -> float:
        cost = tool.get("annual_cost") or 0
        users = max(tool.get("user_count") or 1, 1)
        if cost == 0: return 5.0
        cpu = cost / users
        if cpu < 50:     return 9.5
        if cpu < 200:    return 8.5
        if cpu < 500:    return 7.5
        if cpu < 1000:   return 6.0
        if cpu < 3000:   return 4.5
        if cpu < 8000:   return 3.0
        if cpu < 20000:  return 1.5
        return 0.5

    def _technical_health(self, tool: Dict) -> float:
        if tool.get("end_of_life"):
            return 1.0
        age = tool.get("age_years") or 0
        if age == 0:   return 6.0
        if age <= 1:   return 9.5
        if age <= 3:   return 8.5
        if age <= 5:   return 7.0
        if age <= 8:   return 5.5
        if age <= 12:  return 3.5
        if age <= 15:  return 2.5
        return 1.5

    def _risk_score(self, tool: Dict) -> float:
        risk = 4.0
        if tool.get("end_of_life"):       risk += 3.5
        if tool.get("compliance_required"): risk += 1.0
        age = tool.get("age_years") or 0
        if age > 12:   risk += 2.0
        elif age > 8:  risk += 1.0
        criticality = tool.get("criticality") or ""
        if criticality == "Critical": risk += 0.5
        integrations = tool.get("integrations") or 0
        if integrations >= 20:  risk += 1.0
        elif integrations >= 10: risk += 0.5
        if not (tool.get("vendor") or "").strip():
            risk += 0.5
        return round(min(10.0, max(0.0, risk)), 2)
