from __future__ import annotations

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
        return f"{self.rule_id}:{location}"

    def to_dict(self, *, deck_width: int = 0, deck_height: int = 0) -> dict[str, object]:
        payload = asdict(self)
        payload["id"] = self.finding_id
        if self.bbox is not None:
            payload["bbox"] = asdict(self.bbox.normalized(deck_width, deck_height))
        return payload

