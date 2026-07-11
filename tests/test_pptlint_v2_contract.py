from __future__ import annotations

import json
import importlib
from pathlib import Path

from pptlint.cli import main
from pptlint.readiness import assess_readiness
from pptlint.schema import Finding

from .pptx_factory import write_pptx


def finding(rule_id: str, *, confidence: str = "high") -> Finding:
    return Finding(
        rule_id=rule_id,
        category="integrity",
        severity="critical",
        confidence=confidence,
        message="Package relationship is broken.",
        evidence="ppt/slides/slide1.xml#rId9",
        remediation="Restore the missing part.",
        slide_index=1,
    )


def test_readiness_blocks_only_high_confidence_blockers() -> None:
    blocked = assess_readiness([finding("integrity.broken-relationship")], renderer_status="ok")
    advisory = assess_readiness(
        [finding("integrity.broken-relationship", confidence="low")],
        renderer_status="ok",
    )

    assert blocked.status == "blocked"
    assert blocked.reasons[0]["ruleId"] == "integrity.broken-relationship"
    assert advisory.status == "ready"


def test_readiness_uses_review_for_non_blocking_delivery_risks() -> None:
    review_finding = Finding(
        rule_id="privacy.speaker-notes",
        category="privacy",
        severity="medium",
        confidence="high",
        message="Speaker notes are present.",
        evidence="Slide 1 contains notes",
        remediation="Review the notes.",
        slide_index=1,
    )

    result = assess_readiness([review_finding], renderer_status="ok")

    assert result.status == "review"
    assert result.priority_actions[0]["disposition"] == "review"
    assert len(result.priority_actions) <= 3


def test_pptlint_check_writes_v2_report_with_actionable_findings(
    tmp_path: Path,
    capsys,
) -> None:
    source = write_pptx(tmp_path / "broken.pptx", broken_relationship=True)
    output = tmp_path / "pptlint-report"

    exit_code = main(["check", str(source), "--renderer", "wireframe", "--output", str(output)])

    payload = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
    assert exit_code == 1
    assert payload["schemaVersion"] == "pptlint-report/v2"
    assert payload["language"] == "en"
    assert [item["id"] for item in payload["deliveryChecklist"]] == [
        "file",
        "presentation",
        "editability",
        "privacy",
    ]
    assert payload["deliveryChecklist"][0]["status"] == "fix"
    assert payload["readiness"]["status"] == "blocked"
    assert len(payload["priorityActions"]) <= 3
    assert payload["findings"][0]["disposition"] in {"blocker", "review", "advisory"}
    assert payload["findings"][0]["impact"]
    assert payload["findings"][0]["fixSteps"]
    output_text = capsys.readouterr().out
    first_line = output_text.splitlines()[0]
    assert first_line == "PPTLint result: Fix before sending"
    assert "score" not in first_line.lower()
    assert "Whole file" in output_text
    assert "Open the HTML report for the highlighted slides" in output_text
    assert "not an aesthetic grade" in output_text


def test_pptlint_check_can_write_plain_chinese_delivery_guidance(
    tmp_path: Path,
    capsys,
) -> None:
    source = write_pptx(tmp_path / "broken.pptx", broken_relationship=True)
    output = tmp_path / "zh-report"

    exit_code = main(
        [
            "check",
            str(source),
            "--renderer",
            "wireframe",
            "--lang",
            "zh-CN",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
    html = output.with_suffix(".html").read_text(encoding="utf-8")
    terminal = capsys.readouterr().out
    assert exit_code == 1
    assert payload["language"] == "zh-CN"
    assert payload["deliveryChecklist"][0]["label"] == "文件能否正常打开"
    assert "PPTLint 结果：先处理再发送" in terminal
    assert "100 分仅表示本次规则检查结果" in terminal
    assert "发出去之前，先回答这四个问题" in html


def test_pptlint_check_uses_new_default_output_prefix(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    source = write_pptx(tmp_path / "valid.pptx")
    monkeypatch.chdir(tmp_path)

    assert main(["check", str(source), "--renderer", "wireframe"]) == 0
    assert (tmp_path / "pptlint-report.html").is_file()
    assert (tmp_path / "pptlint-report.json").is_file()
    assert capsys.readouterr().out.splitlines()[0] == "PPTLint result: Ready to send"


def test_pptlint_exposes_the_supported_analysis_modules() -> None:
    for name in ("comparison", "model", "render", "report", "rules", "scoring"):
        assert importlib.import_module(f"pptlint.{name}")


def test_legacy_decklint_entrypoint_emits_migration_notice(tmp_path: Path, capsys) -> None:
    from decklint.compat import main as legacy_main

    source = write_pptx(tmp_path / "valid.pptx")
    exit_code = legacy_main(
        ["audit", str(source), "--renderer", "wireframe", "--output", str(tmp_path / "legacy")]
    )

    assert exit_code == 0
    assert "PPTLint" in capsys.readouterr().err
