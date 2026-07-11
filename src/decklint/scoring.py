from __future__ import annotations

from dataclasses import dataclass

from .schema import Finding


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

    def to_dict(self) -> dict[str, object]:
        return {"overall": self.overall, "categories": self.categories}


def score_findings(findings: list[Finding]) -> ScoreCard:
    categories = {category: 100 for category in CATEGORY_WEIGHTS}
    rule_deductions: dict[tuple[str, str], int] = {}
    for finding in findings:
        if finding.confidence != "high" or finding.category not in categories:
            continue
        key = (finding.category, finding.rule_id)
        previous = rule_deductions.get(key, 0)
        deduction = min(SEVERITY_DEDUCTIONS[finding.severity], 30 - previous)
        if deduction <= 0:
            continue
        categories[finding.category] = max(0, categories[finding.category] - deduction)
        rule_deductions[key] = previous + deduction
    overall = round(sum(categories[name] * weight for name, weight in CATEGORY_WEIGHTS.items()))
    if any(f.category == "integrity" and f.severity == "critical" and f.confidence == "high" for f in findings):
        overall = min(overall, 49)
    return ScoreCard(overall=overall, categories=categories)

