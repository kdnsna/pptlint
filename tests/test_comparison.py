from __future__ import annotations

import json
from pathlib import Path

import pytest

from decklint.comparison import (
    ComparisonError,
    compare_reports,
    load_audit_report,
    match_findings,
)

from .report_factory import make_report


def test_load_audit_report_rejects_wrong_schema(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    report = make_report()
    report["schemaVersion"] = "unknown/v9"
    path.write_text(json.dumps(report), encoding="utf-8")

    with pytest.raises(ComparisonError, match="decklint-report/v1"):
        load_audit_report(path)


def test_load_audit_report_rejects_non_object_root(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ComparisonError, match="JSON object"):
        load_audit_report(path)


def finding(
    rule: str,
    slide: int,
    finding_id: str,
    *,
    shape: str = "1",
    severity: str = "high",
) -> dict[str, object]:
    return {
        "id": finding_id,
        "rule_id": rule,
        "category": "readability",
        "severity": severity,
        "confidence": "high",
        "message": "问题",
        "evidence": finding_id,
        "remediation": "修复",
        "slide_index": slide,
        "shape_id": shape,
        "bbox": {"x": 0.1, "y": 0.1, "w": 0.5, "h": 0.2},
    }


def test_match_findings_uses_rule_and_slide_multisets() -> None:
    before = [
        finding("readability.small-font", 1, "a"),
        finding("readability.small-font", 1, "b"),
    ]
    after = [finding("readability.small-font", 1, "c", shape="99")]

    result = match_findings(before, after)

    assert len(result.persistent) == 1
    assert len(result.resolved) == 1
    assert result.new == []


def test_moved_finding_is_resolved_then_new() -> None:
    result = match_findings(
        [finding("readability.small-font", 1, "a")],
        [finding("readability.small-font", 2, "b")],
    )

    assert len(result.resolved) == len(result.new) == 1
    assert result.persistent == []


def test_compare_reports_fails_for_score_drop() -> None:
    result = compare_reports(
        make_report(score=90),
        make_report(score=89),
        threshold="high",
    )

    assert result["gate"]["passed"] is False
    assert "overall-score-decreased" in result["gate"]["failureReasons"]


def test_compare_reports_fails_for_new_high_confidence_finding() -> None:
    new_item = finding("readability.small-font", 1, "new-high")

    result = compare_reports(
        make_report(score=90),
        make_report(score=95, findings=[new_item]),
        threshold="high",
    )

    assert result["gate"]["passed"] is False
    assert "new-high-confidence-finding" in result["gate"]["failureReasons"]


def test_none_threshold_is_observational() -> None:
    result = compare_reports(
        make_report(score=90),
        make_report(score=80),
        threshold="none",
    )

    assert result["gate"]["passed"] is True
