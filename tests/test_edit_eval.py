from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from decklint.model import load_deck
from pptlint.edit_eval import (
    build_guidance_context,
    build_run_plan,
    evaluate_edit_case,
    evaluate_guidance_case,
    evaluate_source_grounded_case,
    guidance_scope,
    validate_suite,
)
from decklint.repair_catalog import REPAIR_CATALOG

from .pptx_factory import slide_xml, write_pptx


ROOT = Path(__file__).resolve().parents[1]
EDITING = ROOT / "benchmark" / "editing"


def load_json(name: str) -> dict[str, object]:
    payload = json.loads((EDITING / name).read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def test_editing_suite_has_separate_real_edit_and_source_grounded_tracks() -> None:
    suite = load_json("cases.json")
    sources = load_json("sources.json")

    validate_suite(suite, sources)
    cases = suite["cases"]

    assert isinstance(cases, list)
    assert len(cases) == 24
    assert sum(case["track"] == "business-edit" for case in cases) == 20
    assert sum(case["track"] == "paper-to-deck" for case in cases) == 2
    assert sum(case["track"] == "article-to-deck" for case in cases) == 2
    assert sum(case["mode"] == "edit" for case in cases) == 20
    assert sum(case["mode"] == "source-grounded-revision" for case in cases) == 2
    business = [case for case in cases if case["track"] == "business-edit"]
    assert sum(guidance_scope(case) == "lint-detectable" for case in business) == 14
    assert sum(guidance_scope(case) == "instruction-only" for case in business) == 6


def test_editing_suite_matches_published_schema() -> None:
    jsonschema.validate(load_json("cases.json"), load_json("case-v1.schema.json"))


def test_private_source_registry_does_not_store_local_paths() -> None:
    sources = load_json("sources.json")["sources"]
    private_sources = [source for source in sources if source["type"] == "private-pptx"]

    assert len(private_sources) == 6
    assert all("path" not in source and "filePath" not in source for source in private_sources)
    assert all(source["locatorEnv"].startswith("PPTLINT_EDIT_SOURCE_") for source in private_sources)
    assert "/Users/" not in json.dumps(private_sources, ensure_ascii=False)


def test_run_plan_keeps_source_paths_out_and_dependencies_explicit() -> None:
    plan = build_run_plan(load_json("cases.json"))
    runs = plan["runs"]

    assert isinstance(runs, list)
    assert len({run["runId"] for run in runs}) == 24
    assert all("path" not in run for run in runs)
    revision = next(run for run in runs if run["runId"] == "paper-ppt-eval-revise")
    assert revision["dependsOn"] == "paper-ppt-eval-create"


def test_representative_baseline_is_anonymized_and_rejects_all_no_ops() -> None:
    path = EDITING / "results" / "pptlint-1.3.1-representative-baseline.json"
    baseline = json.loads(path.read_text(encoding="utf-8"))
    serialized = json.dumps(baseline, ensure_ascii=False)

    assert baseline["summary"]["requestedEditCompleted"] == "0/3"
    assert baseline["summary"]["hardGatePassed"] == "0/3"
    assert all(case["evaluation"]["machineScore"] == 40 for case in baseline["cases"])
    assert "/Users/" not in serialized
    assert "01-工作资料" not in serialized


def make_case() -> dict[str, object]:
    return {
        "id": "test-title-update",
        "sourceId": "test-source",
        "mode": "edit",
        "acceptance": {
            "allowedSlideChanges": [1],
            "preserveSlideCount": True,
            "preserveUntouchedSlides": True,
            "requiredText": [{"slide": 1, "contains": "New title"}],
            "forbiddenText": [{"slide": 1, "contains": "Old title"}],
            "noNewHighConfidenceFindings": True,
            "maxNativeObjectRatioDrop": 0,
            "maxDurationSeconds": 60,
        },
    }


def test_edit_evaluator_rewards_scoped_change_and_preserves_untouched_slide(tmp_path: Path) -> None:
    source_path = write_pptx(
        tmp_path / "source.pptx",
        slides=[slide_xml(title="Old title"), slide_xml(title="Untouched")],
    )
    output_path = write_pptx(
        tmp_path / "output.pptx",
        slides=[slide_xml(title="New title"), slide_xml(title="Untouched")],
    )
    source = {
        "id": "test-source",
        "type": "private-pptx",
        "sha256": load_deck(source_path).sha256,
        "slides": 2,
    }

    result = evaluate_edit_case(
        make_case(), source, source_path, output_path, duration_seconds=12
    )

    assert result["hardGatePassed"] is True
    assert result["status"] == "review"
    assert result["changedSlides"] == [1]
    assert result["outOfScopeSlides"] == []
    assert result["score"]["machine"] == 85


def test_edit_evaluator_blocks_change_to_non_target_slide(tmp_path: Path) -> None:
    source_path = write_pptx(
        tmp_path / "source.pptx",
        slides=[slide_xml(title="Old title"), slide_xml(title="Untouched")],
    )
    output_path = write_pptx(
        tmp_path / "output.pptx",
        slides=[slide_xml(title="New title"), slide_xml(title="Also changed")],
    )
    source = {
        "id": "test-source",
        "type": "private-pptx",
        "sha256": load_deck(source_path).sha256,
        "slides": 2,
    }

    result = evaluate_edit_case(
        make_case(), source, source_path, output_path, duration_seconds=12
    )

    assert result["hardGatePassed"] is False
    assert result["status"] == "blocked"
    assert result["outOfScopeSlides"] == [2]
    assert result["checks"]["untouchedSlidesPreserved"] is False


def test_edit_evaluator_caps_safe_no_op_below_a_completed_edit(tmp_path: Path) -> None:
    source_path = write_pptx(
        tmp_path / "source.pptx",
        slides=[slide_xml(title="Old title"), slide_xml(title="Untouched")],
    )
    source = {
        "id": "test-source",
        "type": "private-pptx",
        "sha256": load_deck(source_path).sha256,
        "slides": 2,
    }

    result = evaluate_edit_case(
        make_case(), source, source_path, source_path, duration_seconds=12
    )

    assert result["hardGatePassed"] is False
    assert result["score"]["rawMachine"] == 60
    assert result["score"]["machine"] == 40
    assert result["score"]["capReasons"] == ["requested-edit-not-completed"]


def test_guidance_evaluator_requires_detection_manual_steps_and_recheck(tmp_path: Path) -> None:
    source_path = write_pptx(
        tmp_path / "source.pptx",
        slides=[slide_xml(body_size=900)],
    )
    source = {
        "id": "test-source",
        "type": "private-pptx",
        "sha256": load_deck(source_path).sha256,
        "slides": 1,
    }
    case = {
        "id": "small-font-guidance",
        "track": "business-edit",
        "mode": "edit",
        "sourceId": "test-source",
        "operationClass": "single-slide-readability",
        "acceptance": {
            "mustReduceRules": [
                {
                    "ruleId": "readability.small-font",
                    "slides": [1],
                    "minimumReduction": 1,
                }
            ]
        },
    }
    plan, duration = build_guidance_context(source_path)

    result = evaluate_guidance_case(
        case,
        source,
        source_path,
        plan=plan,
        duration_seconds=duration,
    )

    assert result["scopeClass"] == "lint-detectable"
    assert result["targetDetected"] is True
    assert result["hasLocation"] is True
    assert result["hasManualSteps"] is True
    assert result["hasVerificationStep"] is True
    assert result["routeCorrect"] is True
    assert result["falseAutomationPromise"] is False
    assert result["passed"] is True


def test_guidance_evaluator_marks_explicit_content_edits_outside_lint_scope(
    tmp_path: Path,
) -> None:
    source_path = write_pptx(tmp_path / "source.pptx")
    source = {
        "id": "test-source",
        "type": "private-pptx",
        "sha256": load_deck(source_path).sha256,
        "slides": 1,
    }
    case = {
        "id": "cover-date",
        "track": "business-edit",
        "mode": "edit",
        "sourceId": "test-source",
        "operationClass": "atomic-text-update",
        "acceptance": {"requiredText": [{"slide": 1, "contains": "2025 年 10 月"}]},
    }
    plan, duration = build_guidance_context(source_path)

    result = evaluate_guidance_case(
        case,
        source,
        source_path,
        plan=plan,
        duration_seconds=duration,
    )

    assert result["scopeClass"] == "instruction-only"
    assert result["targetDetected"] is None
    assert result["falseAutomationPromise"] is False
    assert result["passed"] is True


def test_high_risk_repairs_never_claim_pptlint_execution() -> None:
    high_risk = [recipe for recipe in REPAIR_CATALOG.values() if recipe.risk == "high"]

    assert high_risk
    assert all(recipe.mode != "cleanup-copy" for recipe in high_risk)
    assert all("pptlint" not in recipe.executors for recipe in high_risk)


def test_source_grounded_evaluator_requires_fact_and_attribution_anchors(tmp_path: Path) -> None:
    output_path = write_pptx(
        tmp_path / "brief.pptx",
        slides=[
            slide_xml(
                title="PPT-Eval research brief",
                body_text="120 PowerPoint tasks across 12 files. Source: arXiv:2606.31154",
            )
        ],
    )
    case = {
        "id": "paper-brief",
        "mode": "source-grounded-authoring",
        "sourceId": "paper-ppt-eval",
        "acceptance": {
            "slideRange": {"minimum": 1, "maximum": 1},
            "requiredFacts": ["120 PowerPoint tasks", "12 files"],
            "requiredAttribution": ["PPT-Eval", "arXiv:2606.31154"],
            "maxDurationSeconds": 60,
        },
    }

    result = evaluate_source_grounded_case(case, output_path, duration_seconds=20)

    assert result["hardGatePassed"] is True
    assert result["status"] == "review"
    assert result["score"]["machine"] == 70
