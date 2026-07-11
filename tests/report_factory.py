from __future__ import annotations

from copy import deepcopy


def make_report(
    *,
    name: str = "deck.pptx",
    score: int = 100,
    findings: list[dict[str, object]] | None = None,
    slides: list[dict[str, object]] | None = None,
) -> dict[str, object]:
    categories = {
        category: score
        for category in (
            "integrity",
            "readability",
            "editability",
            "consistency",
            "accessibility",
        )
    }
    report: dict[str, object] = {
        "schemaVersion": "decklint-report/v1",
        "toolVersion": "0.2.0",
        "profile": "ai-generated",
        "file": {"name": name, "sha256": "a" * 64, "slides": 1},
        "renderer": {
            "requested": "wireframe",
            "used": "wireframe",
            "status": "ok",
            "detail": "",
        },
        "scores": {"overall": score, "categories": categories},
        "summary": {"critical": 0, "high": 0, "medium": 0, "low": 0},
        "findings": list(findings or []),
        "slides": slides
        or [
            {
                "index": 1,
                "title": "标题",
                "titleSource": "inferred",
                "preview": "",
            }
        ],
    }
    return deepcopy(report)
