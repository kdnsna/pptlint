from __future__ import annotations

import json
from pathlib import Path

from . import __version__


def load_repair_plan(path: Path) -> dict[str, object]:
    if not path.is_file():
        raise ValueError(f"Repair plan not found: {path.name}")
    if path.stat().st_size > 100 * 1024 * 1024:
        raise ValueError("Repair plan exceeds the 100 MiB safety limit")
    try:
        plan = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid repair plan JSON: {path.name}") from exc
    if not isinstance(plan, dict) or plan.get("schemaVersion") != "pptlint-repair-plan/v1":
        raise ValueError("Repair plan must use pptlint-repair-plan/v1")
    if not isinstance(plan.get("tasks"), list) or not isinstance(plan.get("source"), dict):
        raise ValueError("Repair plan is missing source or tasks")
    return plan


def build_repair_verification(
    plan: dict[str, object],
    comparison: dict[str, object],
) -> dict[str, object]:
    source = plan["source"]
    before = comparison.get("before")
    after = comparison.get("after")
    if not isinstance(source, dict) or not isinstance(before, dict) or not isinstance(after, dict):
        raise ValueError("Repair verification requires source, before, and after identities")
    before_file = before.get("file")
    after_file = after.get("file")
    if not isinstance(before_file, dict) or not isinstance(after_file, dict):
        raise ValueError("Repair verification requires file identities")
    tasks = plan["tasks"]
    assert isinstance(tasks, list)
    resolved = comparison.get("resolved", [])
    persistent = comparison.get("persistent", [])
    new = comparison.get("new", [])
    if not all(isinstance(items, list) for items in (resolved, persistent, new)):
        raise ValueError("Repair verification requires comparison finding arrays")

    resolved_ids = {
        str(item.get("id", "")) for item in resolved if isinstance(item, dict)
    }
    persistent_ids = {
        str(item.get("before", {}).get("id", ""))
        for item in persistent
        if isinstance(item, dict) and isinstance(item.get("before"), dict)
    }
    before_sha_matches = str(source.get("sha256", "")) == str(before_file.get("sha256", ""))
    completed: list[str] = []
    remaining: list[str] = []
    unable: list[str] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = str(task.get("taskId", ""))
        finding_id = str(task.get("findingId", ""))
        if not before_sha_matches:
            unable.append(task_id)
        elif finding_id in resolved_ids:
            completed.append(task_id)
        elif finding_id in persistent_ids:
            remaining.append(task_id)
        else:
            unable.append(task_id)
    regressions = [
        {
            "findingId": str(item.get("id", "")),
            "ruleId": str(item.get("rule_id", "")),
            "slideIndex": item.get("slide_index"),
            "severity": str(item.get("severity", "")),
            "confidence": str(item.get("confidence", "")),
        }
        for item in new
        if isinstance(item, dict)
        and item.get("confidence") == "high"
        and item.get("severity") in {"high", "critical"}
    ]
    passed = (
        before_sha_matches
        and not remaining
        and not unable
        and not regressions
        and bool(comparison.get("gate", {}).get("passed"))
        if isinstance(comparison.get("gate"), dict)
        else False
    )
    return {
        "schemaVersion": "pptlint-repair-verification/v1",
        "toolVersion": __version__,
        "planSourceSha256": str(source.get("sha256", "")),
        "beforeSha256": str(before_file.get("sha256", "")),
        "afterSha256": str(after_file.get("sha256", "")),
        "sourceHashMatched": before_sha_matches,
        "passed": passed,
        "completedTaskIds": completed,
        "remainingTaskIds": remaining,
        "unableToConfirmTaskIds": unable,
        "regressions": regressions,
    }


def write_repair_verification(path: Path, verification: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
