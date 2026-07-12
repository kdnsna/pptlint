from __future__ import annotations

import hashlib
import json
from pathlib import Path

from . import __version__
from .repair_catalog import RepairRecipe, recipe_for


ADAPTERS = ("generic-agent", "ultimate-ppt-master", "powerpoint-copilot", "powerpoint-manual")


def _object(container: dict[str, object], key: str) -> dict[str, object]:
    value = container.get(key)
    if not isinstance(value, dict):
        raise ValueError(f"Report field must be an object: {key}")
    return value


def _task_id(finding: dict[str, object]) -> str:
    identity = "|".join(
        str(finding.get(key) or "")
        for key in ("id", "rule_id", "slide_index", "shape_id")
    )
    return f"repair-{hashlib.sha256(identity.encode('utf-8')).hexdigest()[:16]}"


def _location(finding: dict[str, object]) -> dict[str, object]:
    bbox = finding.get("bbox")
    return {
        "slideIndex": finding.get("slide_index"),
        "shapeId": finding.get("shape_id"),
        "bbox": bbox if isinstance(bbox, dict) else None,
    }


def _acceptance(finding: dict[str, object], source_sha256: str) -> list[dict[str, object]]:
    return [
        {
            "type": "finding-absent",
            "findingId": str(finding.get("id", "")),
            "ruleId": str(finding.get("rule_id", "")),
            "slideIndex": finding.get("slide_index"),
            "shapeId": finding.get("shape_id"),
        },
        {"type": "no-new-high-confidence", "value": True},
        {"type": "source-hash-unchanged", "sha256": source_sha256},
    ]


def _task(finding: dict[str, object], source_sha256: str) -> dict[str, object]:
    rule_id = str(finding.get("rule_id", ""))
    recipe: RepairRecipe = recipe_for(rule_id)
    steps = finding.get("fixSteps")
    if not isinstance(steps, list) or not all(isinstance(step, str) for step in steps):
        steps = [str(finding.get("remediation") or "Review this item before changing the file.")]
    return {
        "taskId": _task_id(finding),
        "findingId": str(finding.get("id", "")),
        "ruleId": rule_id,
        "location": _location(finding),
        "consequence": str(finding.get("impact") or finding.get("message") or ""),
        "target": str(finding.get("remediation") or steps[0]),
        "steps": steps,
        "repairMode": recipe.mode,
        "risk": recipe.risk,
        "recommendedExecutors": list(recipe.executors),
        "acceptanceCriteria": _acceptance(finding, source_sha256),
    }


def build_repair_plan(report: dict[str, object]) -> dict[str, object]:
    file_info = _object(report, "file")
    findings = report.get("findings")
    if not isinstance(findings, list) or not all(isinstance(item, dict) for item in findings):
        raise ValueError("Report findings must be an object array")
    source_sha256 = str(file_info.get("sha256", ""))
    tasks = [_task(finding, source_sha256) for finding in findings]
    tasks.sort(
        key=lambda item: (
            int(_object(item, "location").get("slideIndex") or 0),
            str(item.get("ruleId", "")),
            str(item.get("findingId", "")),
        )
    )
    counts = {mode: 0 for mode in ("cleanup-copy", "guided-powerpoint", "agent-rebuild", "human-decision")}
    for task in tasks:
        counts[str(task["repairMode"])] += 1
    return {
        "schemaVersion": "pptlint-repair-plan/v1",
        "toolVersion": __version__,
        "source": {
            "name": Path(str(file_info.get("name", "presentation.pptx"))).name,
            "sha256": source_sha256,
            "slides": int(file_info.get("slides", 0)),
            "reportSchema": str(report.get("schemaVersion", "")),
            "profile": str(report.get("profile", "")),
            "scenario": str(report.get("scenario", "present")),
        },
        "summary": {"taskCount": len(tasks), "byRepairMode": counts},
        "tasks": tasks,
    }


def _location_text(task: dict[str, object], *, zh: bool) -> str:
    location = _object(task, "location")
    slide = location.get("slideIndex")
    shape = location.get("shapeId")
    if slide:
        text = f"第 {slide} 页" if zh else f"Slide {slide}"
    else:
        text = "整个文件" if zh else "Whole file"
    if shape:
        text += f" · 对象 {shape}" if zh else f" · object {shape}"
    return text


def render_repair_brief(plan: dict[str, object], *, adapter: str, language: str) -> str:
    if adapter not in ADAPTERS:
        raise ValueError(f"Unsupported repair adapter: {adapter}")
    zh = language == "zh-CN"
    source = _object(plan, "source")
    tasks = plan.get("tasks")
    if not isinstance(tasks, list):
        raise ValueError("Repair plan tasks must be an array")
    adapter_intro = {
        "generic-agent": "请在独立副本中处理以下交付问题。" if zh else "Repair the following delivery issues in a separate copy.",
        "ultimate-ppt-master": "请使用 Ultimate PPT Master 重建或重排需要的页面，并保留可编辑对象。" if zh else "Use Ultimate PPT Master to rebuild or reflow the required slides while preserving editable objects.",
        "powerpoint-copilot": "请在 PowerPoint 的独立副本中按下列任务辅助修改；涉及隐私或删除的任务先让我确认。" if zh else "Assist with these tasks in a separate PowerPoint copy; ask before privacy or deletion decisions.",
        "powerpoint-manual": "请在 PowerPoint 中按页码逐项处理，每完成一项就保存独立副本。" if zh else "Handle each task in PowerPoint by slide number and keep a separate copy.",
    }[adapter]
    lines = [
        "# PPTLint 完整修复任务" if zh else "# PPTLint complete repair brief",
        "",
        adapter_intro,
        "",
        f"- {'文件' if zh else 'File'}: `{source.get('name', '')}`",
        f"- {'原文件 SHA-256' if zh else 'Source SHA-256'}: `{source.get('sha256', '')}`",
        f"- {'任务数' if zh else 'Tasks'}: {len(tasks)}",
        "- 约束：不覆盖原文件，不为了分数改变内容含义，高风险任务先确认。" if zh else "- Constraints: never overwrite the source, do not change meaning for a score, and confirm high-risk tasks first.",
        "",
    ]
    for index, task in enumerate(tasks, 1):
        if not isinstance(task, dict):
            continue
        lines.extend(
            [
                f"## {index}. {task.get('consequence', '')}",
                "",
                f"- {'任务 ID' if zh else 'Task ID'}: `{task.get('taskId', '')}`",
                f"- {'位置' if zh else 'Location'}: {_location_text(task, zh=zh)}",
                f"- {'规则' if zh else 'Rule'}: `{task.get('ruleId', '')}`",
                f"- {'处理方式' if zh else 'Repair mode'}: `{task.get('repairMode', '')}`",
                f"- {'风险' if zh else 'Risk'}: `{task.get('risk', '')}`",
                f"- {'目标' if zh else 'Target'}: {task.get('target', '')}",
            ]
        )
        steps = task.get("steps")
        if isinstance(steps, list):
            lines.extend(f"  {number}. {step}" for number, step in enumerate(steps, 1))
        lines.extend(
            [
                "- 验收：原问题消失，不新增高把握问题，原文件哈希保持不变。" if zh else "- Accept: the original finding is absent, no new high-confidence problem appears, and the source hash is unchanged.",
                "",
            ]
        )
    lines.extend(
        [
            "## 复检" if zh else "## Verify",
            "",
            "```bash",
            f"pptlint check {source.get('name', 'presentation.pptx')} --scenario {source.get('scenario', 'present')} --output pptlint-after",
            "```",
            "",
            "只有复检报告能确认任务是否真正完成。" if zh else "Only the verification report can confirm whether the tasks are complete.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_repair_plan(path: Path, plan: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path
