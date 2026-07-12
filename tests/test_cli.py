from __future__ import annotations

import json
from pathlib import Path

import pytest

from decklint import __version__
from decklint.cli import main

from .pptx_factory import slide_xml, write_pptx
from .report_factory import make_report


def test_cli_prints_current_version(capsys) -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--version"])

    assert exc.value.code == 0
    assert capsys.readouterr().out.strip() == f"PPTLint {__version__}"


def test_cli_writes_html_and_json_for_valid_deck(tmp_path: Path, monkeypatch) -> None:
    source = write_pptx(tmp_path / "valid.pptx")
    monkeypatch.chdir(tmp_path)

    exit_code = main(["audit", str(source), "--renderer", "wireframe"])

    assert exit_code == 0
    assert (tmp_path / "decklint-report.html").is_file()
    payload = json.loads((tmp_path / "decklint-report.json").read_text(encoding="utf-8"))
    assert payload["file"]["name"] == "valid.pptx"


def test_cli_can_write_a_shareable_report(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "sensitive-name.pptx")
    output = tmp_path / "safe"

    exit_code = main(
        [
            "check",
            str(source),
            "--renderer",
            "wireframe",
            "--report-mode",
            "shareable",
            "--output",
            str(output),
        ]
    )

    payload = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
    assert exit_code in {0, 1}
    assert payload["reportMode"] == "shareable"
    assert payload["file"]["name"] == "presentation.pptx"


def test_start_checks_and_opens_the_local_report(tmp_path: Path, monkeypatch) -> None:
    source = write_pptx(tmp_path / "deck.pptx")
    output = tmp_path / "opened-report"
    opened: list[str] = []
    monkeypatch.setattr("decklint.cli.webbrowser.open", opened.append)

    exit_code = main(
        ["start", str(source), "--renderer", "wireframe", "--output", str(output)]
    )

    assert exit_code in {0, 1}
    assert opened == [output.with_suffix(".html").resolve().as_uri()]


def test_doctor_and_version_expose_supportable_diagnostics(capsys) -> None:
    assert main(["doctor", "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["version"] == __version__
    assert payload["wireframeRenderer"] is True
    assert payload["supportedInput"] == [".pptx"]

    with pytest.raises(SystemExit) as exc:
        main(["--version"])
    assert exc.value.code == 0
    assert f"PPTLint {__version__}" in capsys.readouterr().out


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


def test_proof_cli_checks_two_pptx_files_and_writes_complete_evidence(
    tmp_path: Path,
    capsys,
) -> None:
    before = write_pptx(tmp_path / "before.pptx", broken_relationship=True)
    after = write_pptx(tmp_path / "after.pptx")
    output = tmp_path / "proof"

    exit_code = main(
        [
            "proof",
            str(before),
            str(after),
            "--renderer",
            "wireframe",
            "--lang",
            "zh-CN",
            "--output",
            str(output),
        ]
    )

    comparison = json.loads(output.with_suffix(".json").read_text(encoding="utf-8"))
    terminal = capsys.readouterr().out
    assert exit_code == 0
    assert (tmp_path / "proof-before.html").is_file()
    assert (tmp_path / "proof-before.json").is_file()
    assert (tmp_path / "proof-after.html").is_file()
    assert (tmp_path / "proof-after.json").is_file()
    assert output.with_suffix(".html").is_file()
    assert comparison["gate"]["passed"] is True
    assert len(comparison["resolved"]) >= 1
    assert "PPTLint 对比" in terminal
    assert "新增高把握问题 0 项" in terminal
    assert "不代表审美满分" in terminal


def test_proof_cli_returns_two_without_outputs_when_an_input_is_invalid(tmp_path: Path) -> None:
    before = write_pptx(tmp_path / "before.pptx")
    after = tmp_path / "invalid.pptx"
    after.write_text("not a zip", encoding="utf-8")
    output = tmp_path / "proof"

    exit_code = main(
        [
            "proof",
            str(before),
            str(after),
            "--renderer",
            "wireframe",
            "--output",
            str(output),
        ]
    )

    assert exit_code == 2
    assert not output.with_suffix(".json").exists()
    assert not (tmp_path / "proof-before.json").exists()
    assert not (tmp_path / "proof-after.json").exists()
