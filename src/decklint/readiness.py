from __future__ import annotations

from dataclasses import dataclass

from .schema import Finding


BLOCKER_RULES = {
    "integrity.broken-relationship",
    "integrity.empty-deck",
    "integrity.missing-content-type",
    "privacy.comments",
    "privacy.external-relationship",
    "readability.off-canvas-text",
    "readability.text-overlap",
}

RULE_IMPACTS = {
    "integrity.broken-relationship": "PowerPoint may repair the file, omit content, or refuse to open it.",
    "integrity.empty-deck": "The file contains no slide that can be presented.",
    "integrity.missing-content-type": "PowerPoint may repair or omit the undeclared package part.",
    "privacy.comments": "Internal review comments can leave the organization with the file.",
    "privacy.external-relationship": "The presentation depends on or exposes an external URL or file.",
    "privacy.speaker-notes": "Speaker notes may contain information that was not intended for recipients.",
    "readability.off-canvas-text": "Audience-visible text may be clipped or disappear during presentation.",
    "readability.text-overlap": "Two text regions may cover each other in the delivered slide.",
    "readability.small-font": "The audience may not be able to read the affected text at presentation distance.",
    "readability.low-contrast": "The affected text may be unreadable on a projector or low-quality display.",
    "editability.full-slide-image": "Important content cannot be edited as native PowerPoint objects.",
}

RULE_FIX_STEPS = {
    "integrity.broken-relationship": [
        "Open a duplicate of the file in PowerPoint and note any repair warning.",
        "Restore the missing media or object, then save the duplicate as a new PPTX.",
        "Run PPTLint again and confirm that the broken relationship is gone.",
    ],
    "integrity.empty-deck": [
        "Open the source project or template used to generate the presentation.",
        "Export at least one valid slide to a new PPTX.",
        "Run PPTLint again before delivery.",
    ],
    "privacy.comments": [
        "In PowerPoint, open Review and inspect every comment.",
        "Delete comments that must not leave the organization.",
        "Save a delivery copy and run PPTLint again.",
    ],
    "privacy.external-relationship": [
        "Open File > Info and inspect linked files or external content.",
        "Embed, remove, or explicitly approve the external reference.",
        "Save a delivery copy and run PPTLint again.",
    ],
    "privacy.speaker-notes": [
        "Open Notes view and review the notes on the reported slide.",
        "Remove confidential or draft-only text from the delivery copy.",
        "Run PPTLint again to confirm the intended result.",
    ],
    "readability.off-canvas-text": [
        "Open the reported slide and select the highlighted text box.",
        "Move or resize it until the complete box remains inside the slide canvas.",
        "Run PPTLint again and inspect the rendered preview.",
    ],
}


@dataclass(frozen=True)
class ReadinessResult:
    status: str
    reasons: list[dict[str, object]]
    priority_actions: list[dict[str, object]]


def classify_finding(finding: Finding) -> dict[str, object]:
    if finding.confidence != "high":
        disposition = "advisory"
    elif finding.rule_id in BLOCKER_RULES:
        disposition = "blocker"
    else:
        disposition = "review"
    impact = RULE_IMPACTS.get(
        finding.rule_id,
        "This issue may reduce delivery quality or requires a human decision before sharing.",
    )
    steps = RULE_FIX_STEPS.get(
        finding.rule_id,
        [
            finding.remediation,
            "Save changes to a separate delivery copy.",
            "Run PPTLint again and confirm that the finding is resolved.",
        ],
    )
    return {"disposition": disposition, "impact": impact, "fixSteps": steps}


def assess_readiness(findings: list[Finding], *, renderer_status: str) -> ReadinessResult:
    enriched = [(finding, classify_finding(finding)) for finding in findings]
    blockers = [(finding, detail) for finding, detail in enriched if detail["disposition"] == "blocker"]
    reviews = [(finding, detail) for finding, detail in enriched if detail["disposition"] == "review"]
    if blockers:
        status = "blocked"
        deciding = blockers
    elif reviews or renderer_status == "degraded":
        status = "review"
        deciding = reviews
    else:
        status = "ready"
        deciding = []

    reasons = [
        {
            "ruleId": finding.rule_id,
            "slideIndex": finding.slide_index,
            "evidence": finding.evidence,
            "impact": detail["impact"],
        }
        for finding, detail in deciding
    ]
    if renderer_status == "degraded" and not blockers:
        reasons.append(
            {
                "ruleId": "runtime.rendering-degraded",
                "slideIndex": None,
                "evidence": "A real LibreOffice preview was unavailable; structural wireframes were used.",
                "impact": "Visual delivery risks could not be verified with a real renderer.",
            }
        )

    severity_rank = {"critical": 4, "high": 3, "medium": 2, "low": 1}
    disposition_rank = {"blocker": 3, "review": 2, "advisory": 1}
    ordered = sorted(
        enriched,
        key=lambda item: (
            -disposition_rank[str(item[1]["disposition"])],
            -severity_rank[item[0].severity],
            item[0].slide_index or 0,
            item[0].rule_id,
        ),
    )
    actions = [
        {
            "ruleId": finding.rule_id,
            "slideIndex": finding.slide_index,
            "disposition": detail["disposition"],
            "impact": detail["impact"],
            "fixSteps": detail["fixSteps"],
        }
        for finding, detail in ordered[:3]
    ]
    return ReadinessResult(status=status, reasons=reasons, priority_actions=actions)
