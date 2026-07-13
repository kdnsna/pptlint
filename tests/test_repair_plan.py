from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema

from decklint.cli import main
from decklint.repair_catalog import REPAIR_CATALOG
from decklint.repair_plan import ADAPTERS, build_repair_plan, render_repair_brief

from .report_factory import make_report


ROOT = Path(__file__).resolve().parents[1]


def _finding(*, rule_id: str = "readability.small-font", finding_id: str = "finding-1") -> dict[str, object]:
    return {
        "id": finding_id,
        "rule_id": rule_id,
        "category": "readability",
        "severity": "high",
        "confidence": "high",
        "message": "Text is too small.",
        "evidence": "private evidence that must not enter the repair plan",
        "remediation": "Increase the font size.",
        "slide_index": 2,
        "shape_id": "7",
        "bbox": {"x": 0.1, "y": 0.2, "w": 0.3, "h": 0.1},
        "disposition": "blocker",
        "impact": "People in the room may not be able to read this text.",
        "fixSteps": ["Open slide 2.", "Increase the text size.", "Run PPTLint again."],
    }


def test_repair_plan_covers_every_finding_and_is_stable() -> None:
    report = make_report(
        findings=[
            _finding(finding_id="first"),
            _finding(rule_id="privacy.speaker-notes", finding_id="second"),
            _finding(rule_id="editability.full-slide-image", finding_id="third"),
            _finding(rule_id="plugin.unknown", finding_id="fourth"),
        ]
    )

    first = build_repair_plan(report)
    second = build_repair_plan(report)

    assert first == second
    assert first["summary"]["taskCount"] == len(report["findings"])
    assert len({task["taskId"] for task in first["tasks"]}) == len(report["findings"])
    unknown = next(task for task in first["tasks"] if task["ruleId"] == "plugin.unknown")
    assert unknown["repairMode"] == "human-decision"
    jsonschema.validate(
        first,
        json.loads((ROOT / "schema/pptlint-repair-plan-v1.schema.json").read_text(encoding="utf-8")),
    )


def test_repair_plan_does_not_copy_evidence_or_absolute_source_paths() -> None:
    report = make_report(name="/Users/example/Secret/customer-deck.pptx", findings=[_finding()])
    plan = build_repair_plan(report)
    serialized = json.dumps(plan, ensure_ascii=False)

    assert plan["source"]["name"] == "customer-deck.pptx"
    assert "/Users/example" not in serialized
    assert "private evidence" not in serialized


def test_every_builtin_rule_has_an_explicit_recipe() -> None:
    source = "\n".join(
        (ROOT / path).read_text(encoding="utf-8")
        for path in ("src/decklint/rules.py", "src/decklint/policy.py")
    )
    discovered = set(
        re.findall(
            r'"((?:integrity|readability|editability|consistency|accessibility|privacy|policy)\.[a-z0-9.-]+)"',
            source,
        )
    )

    assert discovered == set(REPAIR_CATALOG)


def test_every_adapter_renders_all_tasks() -> None:
    plan = build_repair_plan(
        make_report(findings=[_finding(finding_id="a"), _finding(finding_id="b")])
    )

    for adapter in ADAPTERS:
        brief = render_repair_brief(plan, adapter=adapter, language="zh-CN")
        assert brief.count("- 任务 ID:") == 2
        assert "原文件 SHA-256" in brief


def test_chinese_repair_plan_describes_the_visible_result_not_the_first_action() -> None:
    report = make_report(findings=[_finding()])
    report["language"] = "zh-CN"

    plan = build_repair_plan(report)

    assert "目标观看距离下清楚可读" in plan["tasks"][0]["target"]
    assert plan["tasks"][0]["steps"][0] == "Open slide 2."


def test_cli_writes_machine_readable_plan_with_all_report_findings(tmp_path: Path) -> None:
    report = make_report(findings=[_finding(finding_id=str(index)) for index in range(5)])
    report_path = tmp_path / "report.json"
    plan_path = tmp_path / "repair-plan.json"
    report_path.write_text(json.dumps(report), encoding="utf-8")

    assert main(["plan", str(report_path), "--format", "json", "--output", str(plan_path)]) == 0
    plan = json.loads(plan_path.read_text(encoding="utf-8"))

    assert len(plan["tasks"]) == 5
    assert plan["schemaVersion"] == "pptlint-repair-plan/v1"
