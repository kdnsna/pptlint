from __future__ import annotations

import json
from pathlib import Path

import jsonschema
import pytest

from pptlint.benchmark import (
    BenchmarkError,
    build_run_plan,
    metrics_from_report,
    summarize_runs,
    validate_run,
)


ROOT = Path(__file__).resolve().parents[1]


def test_public_benchmark_plan_contains_forty_five_unique_runs() -> None:
    config = json.loads((ROOT / "benchmark/benchmark.json").read_text(encoding="utf-8"))

    runs = build_run_plan(config)

    assert len(runs) == 45
    assert len({run["runId"] for run in runs}) == 45
    assert {run["projectId"] for run in runs} == {
        "ppt-master",
        "presenton",
        "pptagent",
        "codex-ppt-skill",
        "ultimate-ppt-master",
    }
    assert {run["taskId"] for run in runs} == {"qbr-cn", "technical-en", "launch-cn"}


def test_completed_run_manifest_requires_reproducible_evidence() -> None:
    run = {
        "schemaVersion": "pptlint-benchmark-run/v1",
        "runId": "ppt-master--qbr-cn--01",
        "projectId": "ppt-master",
        "taskId": "qbr-cn",
        "repetition": 1,
        "status": "complete",
        "projectCommit": "a" * 40,
        "model": "default",
        "provider": "default",
        "environment": {},
        "durationSeconds": 1,
    }

    with pytest.raises(BenchmarkError, match="outputPptx"):
        validate_run(run)


def test_run_manifest_schema_accepts_complete_evidence() -> None:
    schema = json.loads((ROOT / "benchmark/run-manifest-v1.schema.json").read_text(encoding="utf-8"))
    run = {
        "schemaVersion": "pptlint-benchmark-run/v1",
        "runId": "ppt-master--qbr-cn--01",
        "projectId": "ppt-master",
        "taskId": "qbr-cn",
        "repetition": 1,
        "status": "complete",
        "projectCommit": "a" * 40,
        "model": "project recommended default",
        "provider": "project recommended default",
        "environment": {"os": "macOS", "python": "3.13", "notes": "documented run"},
        "durationSeconds": 120,
        "outputPptx": {"path": "outputs/ppt-master--qbr-cn--01.pptx", "sha256": "b" * 64},
        "reportJson": {"path": "reports/ppt-master--qbr-cn--01.json", "sha256": "c" * 64},
        "metrics": {
            "slides": 10,
            "readiness": "review",
            "highConfidenceIssues": 2,
            "renderSucceeded": True,
            "nativeObjectRatio": 0.8,
            "privacyIssues": 0,
            "repairPassed": None,
        },
    }

    validate_run(run)
    jsonschema.validate(run, schema)


def test_summary_reports_evidence_matrix_without_winner() -> None:
    runs = [
        {
            "status": "complete",
            "projectId": "alpha",
            "metrics": {
                "slides": 10,
                "readiness": "blocked",
                "highConfidenceIssues": 3,
                "renderSucceeded": False,
                "nativeObjectRatio": 0.5,
                "privacyIssues": 1,
                "repairPassed": False,
            },
        },
        {
            "status": "complete",
            "projectId": "alpha",
            "metrics": {
                "slides": 10,
                "readiness": "ready",
                "highConfidenceIssues": 1,
                "renderSucceeded": True,
                "nativeObjectRatio": 0.9,
                "privacyIssues": 0,
                "repairPassed": True,
            },
        },
    ]

    summary = summarize_runs(runs)

    assert "winner" not in summary
    assert summary["projects"]["alpha"]["blockedRate"] == 0.5
    assert summary["projects"]["alpha"]["highConfidenceIssuesPer10Slides"] == 2.0
    assert summary["projects"]["alpha"]["renderSuccessRate"] == 0.5


def test_metrics_are_derived_from_the_published_pptlint_report() -> None:
    report = {
        "file": {"slides": 10},
        "readiness": {"status": "review"},
        "renderer": {"status": "ok", "used": "libreoffice"},
        "metrics": {"editability": {"nativeObjectRatio": 0.75}},
        "findings": [
            {"confidence": "high", "category": "readability"},
            {"confidence": "low", "category": "readability"},
            {"confidence": "high", "category": "privacy"},
        ],
    }

    metrics = metrics_from_report(report)

    assert metrics == {
        "slides": 10,
        "readiness": "review",
        "highConfidenceIssues": 2,
        "renderSucceeded": True,
        "nativeObjectRatio": 0.75,
        "privacyIssues": 1,
        "repairPassed": None,
    }
