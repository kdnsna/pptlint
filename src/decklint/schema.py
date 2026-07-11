from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from typing import Literal


Severity = Literal["low", "medium", "high", "critical"]
Confidence = Literal["low", "high"]
Category = Literal["integrity", "readability", "editability", "consistency", "accessibility", "privacy"]


@dataclass(frozen=True)
class NormalizedBBox:
    x: float
    y: float
    w: float
    h: float


@dataclass(frozen=True)
class BBox:
    x: int
    y: int
    w: int
    h: int

    def normalized(self, width: int, height: int) -> NormalizedBBox:
        if width <= 0 or height <= 0:
            return NormalizedBBox(0.0, 0.0, 0.0, 0.0)
        return NormalizedBBox(
            round(self.x / width, 6),
            round(self.y / height, 6),
            round(self.w / width, 6),
            round(self.h / height, 6),
        )


@dataclass(frozen=True)
class Finding:
    rule_id: str
    category: Category
    severity: Severity
    confidence: Confidence
    message: str
    evidence: str
    remediation: str
    slide_index: int | None = None
    shape_id: str | None = None
    bbox: BBox | None = None

    @property
    def finding_id(self) -> str:
        location = f"s{self.slide_index or 0}-{self.shape_id or 'deck'}"
        fingerprint = hashlib.sha256(
            f"{self.rule_id}|{location}|{self.evidence}|{self.message}".encode("utf-8")
        ).hexdigest()[:10]
        return f"{self.rule_id}:{location}:{fingerprint}"

    def to_dict(
        self,
        *,
        finding_id: str | None = None,
        deck_width: int = 0,
        deck_height: int = 0,
    ) -> dict[str, object]:
        payload = asdict(self)
        payload["id"] = finding_id or self.finding_id
        if self.bbox is not None:
            payload["bbox"] = asdict(self.bbox.normalized(deck_width, deck_height))
        return payload


def identified_findings(findings: list[Finding]) -> list[tuple[str, Finding]]:
    counts: dict[str, int] = {}
    identified: list[tuple[str, Finding]] = []
    for finding in findings:
        base_id = finding.finding_id
        counts[base_id] = counts.get(base_id, 0) + 1
        suffix = "" if counts[base_id] == 1 else f":{counts[base_id]}"
        identified.append((f"{base_id}{suffix}", finding))
    return identified
