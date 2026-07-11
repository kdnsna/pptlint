from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import yaml

import decklint
from decklint.model import load_deck
from decklint.render import render_deck
from decklint.report import build_report
from decklint.rules import audit_deck
from decklint.schema import Finding
from decklint.scoring import score_findings

from .pptx_factory import write_pptx


ROOT = Path(__file__).resolve().parents[1]


def test_report_matches_published_json_schema(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "deck.pptx")
    deck = load_deck(source)
    findings = audit_deck(deck, profile="baseline")
    report = build_report(
        deck,
        findings,
        score_findings(findings),
        render_deck(deck, source=source, renderer="wireframe"),
        profile="baseline",
    )
    schema = json.loads((ROOT / "schema/decklint-report-v1.schema.json").read_text(encoding="utf-8"))

    jsonschema.validate(report, schema)


def test_report_schema_accepts_category_floor_deductions(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "deck.pptx")
    deck = load_deck(source)
    findings = [
        Finding(
            rule_id=f"integrity.synthetic-{index}",
            category="integrity",
            severity="critical",
            confidence="high",
            message="Synthetic integrity failure",
            evidence=str(index),
            remediation="Repair the package.",
        )
        for index in range(5)
    ]
    report = build_report(
        deck,
        findings,
        score_findings(findings),
        render_deck(deck, source=source, renderer="wireframe"),
        profile="baseline",
    )
    schema = json.loads((ROOT / "schema/decklint-report-v1.schema.json").read_text(encoding="utf-8"))

    jsonschema.validate(report, schema)


def test_committed_proof_reports_match_schema_and_scoring_contract() -> None:
    schema = json.loads((ROOT / "schema/decklint-report-v1.schema.json").read_text(encoding="utf-8"))

    for name in ("good-deck", "bad-deck"):
        report = json.loads((ROOT / f"examples/reports/{name}.json").read_text(encoding="utf-8"))
        jsonschema.validate(report, schema)
        assert "deductions" in report["scores"]
        assert "Scoring policy" in (ROOT / f"examples/reports/{name}.html").read_text(encoding="utf-8")


def test_github_action_exposes_the_cli_contract() -> None:
    action = yaml.safe_load((ROOT / "action.yml").read_text(encoding="utf-8"))

    assert {"path", "profile", "fail-on", "min-score", "renderer"} <= set(action["inputs"])
    assert {"score", "html-report", "json-report"} <= set(action["outputs"])
    run_scripts = "\n".join(step.get("run", "") for step in action["runs"]["steps"])
    assert "pip install" in run_scripts
    assert "decklint audit" in run_scripts
    assert "upload-artifact" in json.dumps(action)
    assert "mktemp -d" in run_scripts
    assert "$RUNNER_TEMP" in run_scripts
    upload_step = next(step for step in action["runs"]["steps"] if step.get("uses") == "actions/upload-artifact@v4")
    assert "steps.audit.outputs.html-report" in upload_step["with"]["path"]
    assert "steps.audit.outputs.json-report" in upload_step["with"]["path"]
    assert action["outputs"]["exit-code"]["value"] == "${{ steps.audit.outputs.exit-code }}"


def test_agent_skill_is_short_and_delegates_to_cli() -> None:
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert len(skill.splitlines()) <= 100
    assert "decklint audit" in skill
    assert "Do not" in skill and "modify" in skill


def test_readme_leads_with_single_product_promise() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert any("Lighthouse for PowerPoint" in line for line in readme.splitlines()[2:12])
    assert "uvx decklint audit" in readme
    assert "does not upload" in readme.lower()
    assert "examples/reports/good-deck.html" in readme
    assert "examples/reports/bad-deck.html" in readme


def test_v02_public_surface_is_chinese_first_and_exposes_compare() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    first_screen = "\n".join(readme.splitlines()[:40])
    skill = (ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "PPT 质量基础设施" in first_screen
    assert "decklint compare" in readme
    assert "GitHub Release" in first_screen
    assert "uvx decklint audit" not in first_screen
    assert "decklint compare" in skill
    assert len(skill.splitlines()) <= 100


def test_proof_loop_case_is_schema_valid_and_matches_public_claims() -> None:
    report_schema = json.loads((ROOT / "schema/decklint-report-v1.schema.json").read_text(encoding="utf-8"))
    comparison_schema = json.loads(
        (ROOT / "schema/decklint-comparison-v1.schema.json").read_text(encoding="utf-8")
    )
    before = json.loads((ROOT / "site/proof-loop/before.json").read_text(encoding="utf-8"))
    after = json.loads((ROOT / "site/proof-loop/after.json").read_text(encoding="utf-8"))
    comparison = json.loads((ROOT / "site/proof-loop/comparison.json").read_text(encoding="utf-8"))

    jsonschema.validate(before, report_schema)
    jsonschema.validate(after, report_schema)
    jsonschema.validate(comparison, comparison_schema)
    assert before["scores"]["overall"] == 49
    assert after["scores"]["overall"] == 100
    assert comparison["scores"]["overall"] == {"before": 49, "after": 100, "delta": 51}
    assert len(comparison["resolved"]) == 103
    assert len(comparison["new"]) == 0
    assert comparison["gate"]["passed"] is True

    site = (ROOT / "site/index.html").read_text(encoding="utf-8")
    assert "49→100" in site
    assert "proof-loop/comparison.html" in site
    assert "http://" not in site and "https://" in site


def test_version_is_020() -> None:
    assert decklint.__version__ == "0.2.0"


def test_corpus_contains_thirty_public_synthetic_pptx_files() -> None:
    manifest = json.loads((ROOT / "tests/fixtures/corpus/manifest.json").read_text(encoding="utf-8"))

    assert len(manifest["cases"]) >= 30
    for case in manifest["cases"]:
        fixture = ROOT / "tests/fixtures/corpus" / case["file"]
        assert fixture.is_file(), case["file"]
        deck = load_deck(fixture)
        assert deck.filename == case["file"]
        findings = audit_deck(deck, profile="ai-generated" if "flattened" in case["label"] else "baseline")
        if case["expectedRule"]:
            assert case["expectedRule"] in {finding.rule_id for finding in findings}, case["file"]


def test_clean_corpus_has_no_high_confidence_delivery_blockers() -> None:
    manifest = json.loads((ROOT / "tests/fixtures/corpus/manifest.json").read_text(encoding="utf-8"))
    clean_cases = [case for case in manifest["cases"] if case["label"] == "clean native deck"]

    blockers = []
    for case in clean_cases:
        deck = load_deck(ROOT / "tests/fixtures/corpus" / case["file"])
        blockers.extend(
            finding
            for finding in audit_deck(deck, profile="baseline")
            if finding.confidence == "high" and finding.severity in {"high", "critical"}
        )

    assert not blockers
