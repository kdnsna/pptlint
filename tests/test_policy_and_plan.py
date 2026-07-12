from __future__ import annotations

import json
from pathlib import Path

from decklint.cli import main
from decklint.model import load_deck
from decklint.policy import apply_policy, load_policy

from .pptx_factory import slide_xml, write_pptx


def test_policy_loads_safely_and_finds_explicit_delivery_violations(tmp_path: Path) -> None:
    policy_path = tmp_path / "company.yml"
    policy_path.write_text(
        """version: 1
name: Company external delivery
allowedFonts: [Arial]
minimumFontSize: 20
forbidExternalLinks: true
forbidNotes: true
""",
        encoding="utf-8",
    )
    source = write_pptx(
        tmp_path / "deck.pptx",
        slides=[slide_xml(body_font="Aptos", body_size=1800)],
        notes_text="internal only",
        external_url="https://intranet.example",
    )

    findings = apply_policy(load_deck(source), load_policy(policy_path))
    ids = {item.rule_id for item in findings}

    assert ids == {
        "policy.external-link-forbidden",
        "policy.font-not-allowed",
        "policy.font-size-below-minimum",
        "policy.notes-forbidden",
    }


def test_policy_rejects_unknown_fields(tmp_path: Path) -> None:
    policy_path = tmp_path / "bad.yml"
    policy_path.write_text("version: 1\nmagicFix: true\n", encoding="utf-8")

    try:
        load_policy(policy_path)
    except ValueError as exc:
        assert "Unsupported policy fields" in str(exc)
    else:
        raise AssertionError("Unknown policy fields must fail closed")


def test_cli_policy_init_does_not_overwrite_existing_file(tmp_path: Path) -> None:
    output = tmp_path / "policy.yml"

    assert main(["policy", "init", str(output)]) == 0
    first = output.read_text(encoding="utf-8")
    assert "forbidExternalLinks" in first
    assert main(["policy", "init", str(output)]) == 2
    assert output.read_text(encoding="utf-8") == first


def test_cli_applies_policy_and_records_its_name(tmp_path: Path) -> None:
    policy_path = tmp_path / "company.yml"
    policy_path.write_text(
        "version: 1\nname: Board delivery\nminimumFontSize: 20\n",
        encoding="utf-8",
    )
    source = write_pptx(tmp_path / "deck.pptx", slides=[slide_xml(body_size=1800)])
    output = tmp_path / "report"

    assert (
        main(
            [
                "check",
                str(source),
                "--renderer",
                "wireframe",
                "--policy",
                str(policy_path),
                "--output",
                str(output),
            ]
        )
        == 1
    )
    report = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
    assert report["policy"] == {"applied": True, "name": "Board delivery"}
    assert report["readiness"]["status"] == "blocked"


def test_plan_writes_agent_ready_brief_from_current_report(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "deck.pptx", broken_relationship=True)
    report = tmp_path / "report"
    brief = tmp_path / "repair.md"
    main(
        [
            "check",
            str(source),
            "--renderer",
            "wireframe",
            "--lang",
            "zh-CN",
            "--output",
            str(report),
        ]
    )

    assert main(["plan", str(report.with_suffix(".json")), "--output", str(brief)]) == 0
    text = brief.read_text(encoding="utf-8")
    assert "# PPTLint 修复简报" in text
    assert "保留原文件" in text
    assert "integrity.broken-relationship" in text
    assert "pptlint check deck.pptx" in text
