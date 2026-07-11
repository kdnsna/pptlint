from __future__ import annotations

from dataclasses import dataclass

from .schema import Finding, identified_findings


CATEGORY_WEIGHTS = {
    "integrity": 0.30,
    "readability": 0.25,
    "editability": 0.20,
    "consistency": 0.15,
    "accessibility": 0.10,
}
SEVERITY_DEDUCTIONS = {"critical": 30, "high": 15, "medium": 5, "low": 1}


@dataclass(frozen=True)
class ScoreCard:
    overall: int
    categories: dict[str, int]
    weights: dict[str, float]
    policy: dict[str, object]
    deductions: list[dict[str, object]]
    calculation: dict[str, object]

    def to_dict(self) -> dict[str, object]:
        return {
            "overall": self.overall,
            "categories": self.categories,
            "weights": self.weights,
            "policy": self.policy,
            "deductions": self.deductions,
            "calculation": self.calculation,
        }


def score_findings(findings: list[Finding]) -> ScoreCard:
    categories = {category: 100 for category in CATEGORY_WEIGHTS}
    rule_deductions: dict[tuple[str, str], int] = {}
    deductions: list[dict[str, object]] = []
    for finding_id, finding in identified_findings(findings):
        requested = SEVERITY_DEDUCTIONS[finding.severity]
        applied = 0
        reason = "applied"
        if finding.category not in categories:
            reason = "unscored-category"
        elif finding.confidence != "high":
            reason = "low-confidence"
        else:
            key = (finding.category, finding.rule_id)
            previous = rule_deductions.get(key, 0)
            rule_remaining = 30 - previous
            category_remaining = categories[finding.category]
            applied = min(requested, rule_remaining, category_remaining)
            if applied <= 0:
                reason = "category-floor" if category_remaining <= 0 else "per-rule-cap"
            else:
                categories[finding.category] = max(0, categories[finding.category] - applied)
                rule_deductions[key] = previous + applied
                if applied < requested:
                    reason = (
                        "category-floor"
                        if category_remaining <= rule_remaining
                        else "per-rule-cap"
                    )
        deductions.append(
            {
                "findingId": finding_id,
                "category": finding.category,
                "ruleId": finding.rule_id,
                "severity": finding.severity,
                "confidence": finding.confidence,
                "requested": requested,
                "applied": applied,
                "reason": reason,
            }
        )
    weighted_total = sum(categories[name] * weight for name, weight in CATEGORY_WEIGHTS.items())
    overall = round(weighted_total)
    integrity_cap_applied = any(
        f.category == "integrity" and f.severity == "critical" and f.confidence == "high"
        for f in findings
    )
    if integrity_cap_applied:
        overall = min(overall, 49)
    return ScoreCard(
        overall=overall,
        categories=categories,
        weights=dict(CATEGORY_WEIGHTS),
        policy={
            "startingScore": 100,
            "severityDeductions": dict(SEVERITY_DEDUCTIONS),
            "perRuleCap": 30,
            "integrityCriticalOverallCap": 49,
            "lowConfidenceAffectsScore": False,
            "privacyAffectsScore": False,
        },
        deductions=deductions,
        calculation={
            "method": "weighted-average-rounded",
            "weightedTotal": round(weighted_total, 3),
            "integrityCriticalCapApplied": integrity_cap_applied,
        },
    )
