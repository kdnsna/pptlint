from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path


MAX_REPORT_BYTES = 100 * 1024 * 1024
SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


class ComparisonError(ValueError):
    """Raised when audit reports cannot be compared safely."""


@dataclass(frozen=True)
class FindingMatch:
    resolved: list[dict[str, object]]
    persistent: list[dict[str, object]]
    new: list[dict[str, object]]


def _group_key(item: dict[str, object]) -> tuple[str, int]:
    return (str(item.get("rule_id", "")), int(item.get("slide_index") or 0))


def _sort_key(item: dict[str, object]) -> tuple[object, ...]:
    candidate = item.get("bbox")
    bbox = candidate if isinstance(candidate, dict) else {}
    return (
        float(bbox.get("x", 0)),
        float(bbox.get("y", 0)),
        float(bbox.get("w", 0)),
        float(bbox.get("h", 0)),
        str(item.get("shape_id") or ""),
        str(item.get("evidence", "")),
        str(item.get("id", "")),
    )


def match_findings(
    before: list[dict[str, object]],
    after: list[dict[str, object]],
) -> FindingMatch:
    grouped_before: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    grouped_after: dict[tuple[str, int], list[dict[str, object]]] = defaultdict(list)
    for item in before:
        grouped_before[_group_key(item)].append(item)
    for item in after:
        grouped_after[_group_key(item)].append(item)

    resolved: list[dict[str, object]] = []
    persistent: list[dict[str, object]] = []
    new: list[dict[str, object]] = []
    for key in sorted(set(grouped_before) | set(grouped_after)):
        left = sorted(grouped_before[key], key=_sort_key)
        right = sorted(grouped_after[key], key=_sort_key)
        paired = min(len(left), len(right))
        persistent.extend(
            {"before": left[index], "after": right[index]}
            for index in range(paired)
        )
        resolved.extend(left[paired:])
        new.extend(right[paired:])
    return FindingMatch(resolved=resolved, persistent=persistent, new=new)


def _dict_field(container: dict[str, object], key: str) -> dict[str, object]:
    value = container.get(key)
    if not isinstance(value, dict):
        raise ComparisonError(f"Audit report field must be an object: {key}")
    return value


def _list_field(container: dict[str, object], key: str) -> list[dict[str, object]]:
    value = container.get(key)
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise ComparisonError(f"Audit report field must be an object array: {key}")
    return value


def _delta_map(
    before: dict[str, object],
    after: dict[str, object],
) -> dict[str, dict[str, int]]:
    return {
        key: {
            "before": int(before.get(key, 0)),
            "after": int(after.get(key, 0)),
            "delta": int(after.get(key, 0)) - int(before.get(key, 0)),
        }
        for key in sorted(set(before) | set(after))
    }


def compare_reports(
    before: dict[str, object],
    after: dict[str, object],
    *,
    threshold: str = "high",
) -> dict[str, object]:
    if threshold not in {"none", *SEVERITY_RANK}:
        raise ComparisonError(f"Unsupported regression threshold: {threshold}")
    before_findings = _list_field(before, "findings")
    after_findings = _list_field(after, "findings")
    matches = match_findings(before_findings, after_findings)
    before_scores = _dict_field(before, "scores")
    after_scores = _dict_field(after, "scores")
    score_before = int(before_scores.get("overall", 0))
    score_after = int(after_scores.get("overall", 0))
    reasons: list[str] = []
    if threshold != "none" and score_after < score_before:
        reasons.append("overall-score-decreased")
    if threshold != "none":
        threshold_rank = SEVERITY_RANK[threshold]
        if any(
            item.get("confidence") == "high"
            and SEVERITY_RANK.get(str(item.get("severity")), 0) >= threshold_rank
            for item in matches.new
        ):
            reasons.append("new-high-confidence-finding")
    return {
        "schemaVersion": "decklint-comparison/v1",
        "scores": {
            "overall": {
                "before": score_before,
                "after": score_after,
                "delta": score_after - score_before,
            },
            "categories": _delta_map(
                _dict_field(before_scores, "categories"),
                _dict_field(after_scores, "categories"),
            ),
        },
        "severity": _delta_map(
            _dict_field(before, "summary"),
            _dict_field(after, "summary"),
        ),
        "resolved": matches.resolved,
        "persistent": matches.persistent,
        "new": matches.new,
        "gate": {
            "threshold": threshold,
            "passed": not reasons,
            "failureReasons": reasons,
        },
    }


def load_audit_report(path: Path) -> dict[str, object]:
    path = Path(path)
    if not path.is_file():
        raise ComparisonError(f"Audit report not found: {path.name}")
    if path.stat().st_size > MAX_REPORT_BYTES:
        raise ComparisonError("Audit report exceeds the 100 MiB safety limit")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ComparisonError(f"Invalid audit report JSON: {path.name}") from exc
    if not isinstance(payload, dict):
        raise ComparisonError("Audit report root must be a JSON object")
    if payload.get("schemaVersion") != "decklint-report/v1":
        raise ComparisonError("Audit report must use decklint-report/v1")
    for key in (
        "file",
        "scores",
        "summary",
        "findings",
        "slides",
        "profile",
        "renderer",
    ):
        if key not in payload:
            raise ComparisonError(f"Audit report is missing required field: {key}")
    return payload
