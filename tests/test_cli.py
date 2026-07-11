from __future__ import annotations

import json
from pathlib import Path

from decklint.cli import main

from .pptx_factory import slide_xml, write_pptx
from .report_factory import make_report


def test_cli_writes_html_and_json_for_valid_deck(tmp_path: Path, monkeypatch) -> None:
    source = write_pptx(tmp_path / "valid.pptx")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["audit", str(source), "--renderer", "wireframe"])

    assert exit_code == 0
    assert (tmp_path / "decklint-report.html").is_file()
    payload = json.loads((tmp_path / "decklint-report.json").read_text(encoding="utf-8"))
    assert payload["file"]["name"] == "valid.pptx"


def test_cli_returns_one_when_high_confidence_finding_reaches_threshold(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "broken.pptx", broken_relationship=True)

    exit_code = main(
        ["audit", str(source), "--renderer", "wireframe", "--output", str(tmp_path / "report")]
    )

    assert exit_code == 1


def test_cli_fail_on_none_allows_findings(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "broken.pptx", broken_relationship=True)

    exit_code = main(
        [
            "audit",
            str(source),
            "--renderer",
            "wireframe",
            "--fail-on",
            "none",
            "--output",
            str(tmp_path / "report"),
        ]
    )

    assert exit_code == 0


def test_cli_min_score_can_fail_a_report_without_high_findings(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "valid.pptx", slides=[slide_xml(body_size=1300)])

    exit_code = main(
        [
            "audit",
            str(source),
            "--renderer",
            "wireframe",
            "--min-score",
            "100",
            "--output",
            str(tmp_path / "report"),
        ]
    )

    assert exit_code == 1


def test_cli_returns_two_for_invalid_pptx(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.pptx"
    invalid.write_text("not a zip", encoding="utf-8")

    exit_code = main(["audit", str(invalid), "--output", str(tmp_path / "report")])

    assert exit_code == 2
    assert not (tmp_path / "report.json").exists()


def test_cli_returns_two_when_explicit_libreoffice_is_unavailable(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "valid.pptx")

    exit_code = main(
        [
            "audit",
            str(source),
            "--renderer",
            "libreoffice",
            "--soffice-path",
            "/missing/soffice",
            "--output",
            str(tmp_path / "report"),
        ]
    )

    assert exit_code == 2


def test_compare_cli_writes_html_and_json(tmp_path: Path) -> None:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    before.write_text(json.dumps(make_report(score=80)), encoding="utf-8")
    after.write_text(json.dumps(make_report(score=95)), encoding="utf-8")

    exit_code = main(
        [
            "compare",
            str(before),
            str(after),
            "--output",
            str(tmp_path / "comparison"),
        ]
    )

    assert exit_code == 0
    assert (tmp_path / "comparison.html").is_file()
    assert (tmp_path / "comparison.json").is_file()


def test_compare_cli_returns_one_for_regression(tmp_path: Path) -> None:
    before = tmp_path / "before.json"
    after = tmp_path / "after.json"
    before.write_text(json.dumps(make_report(score=90)), encoding="utf-8")
    after.write_text(json.dumps(make_report(score=80)), encoding="utf-8")

    exit_code = main(
        [
            "compare",
            str(before),
            str(after),
            "--output",
            str(tmp_path / "comparison"),
        ]
    )

    assert exit_code == 1


def test_compare_cli_returns_two_without_partial_outputs(tmp_path: Path) -> None:
    invalid = tmp_path / "invalid.json"
    invalid.write_text("[]", encoding="utf-8")

    exit_code = main(
        [
            "compare",
            str(invalid),
            str(invalid),
            "--output",
            str(tmp_path / "comparison"),
        ]
    )

    assert exit_code == 2
    assert not (tmp_path / "comparison.html").exists()
    assert not (tmp_path / "comparison.json").exists()
