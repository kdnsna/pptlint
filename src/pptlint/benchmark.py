from __future__ import annotations

from collections import defaultdict


class BenchmarkError(ValueError):
    """Raised when public benchmark evidence is incomplete or inconsistent."""


def build_run_plan(config: dict[str, object]) -> list[dict[str, object]]:
    projects = config.get("projects")
    tasks = config.get("tasks")
    repetitions = config.get("repetitions")
    if not isinstance(projects, list) or not isinstance(tasks, list) or not isinstance(repetitions, int):
        raise BenchmarkError("Benchmark config requires projects, tasks, and repetitions")
    runs: list[dict[str, object]] = []
    for project in projects:
        if not isinstance(project, dict) or not isinstance(project.get("id"), str):
            raise BenchmarkError("Every benchmark project requires an id")
        for task in tasks:
            if not isinstance(task, dict) or not isinstance(task.get("id"), str):
                raise BenchmarkError("Every benchmark task requires an id")
            for repetition in range(1, repetitions + 1):
                run_id = f"{project['id']}--{task['id']}--{repetition:02d}"
                runs.append(
                    {
                        "schemaVersion": "pptlint-benchmark-run/v1",
                        "runId": run_id,
                        "projectId": project["id"],
                        "taskId": task["id"],
                        "repetition": repetition,
                        "status": "pending",
                        "projectCommit": project.get("commit"),
                    }
                )
    return runs


def validate_run(run: dict[str, object]) -> None:
    for field in ("schemaVersion", "runId", "projectId", "taskId", "repetition", "status"):
        if field not in run:
            raise BenchmarkError(f"Benchmark run is missing {field}")
    if run["schemaVersion"] != "pptlint-benchmark-run/v1":
        raise BenchmarkError("Benchmark run uses an unsupported schemaVersion")
    if run["status"] not in {"pending", "running", "complete", "excluded"}:
        raise BenchmarkError("Benchmark run has an unsupported status")
    if run["status"] == "complete":
        for field in (
            "projectCommit",
            "model",
            "provider",
            "environment",
            "durationSeconds",
            "outputPptx",
            "reportJson",
            "metrics",
        ):
            if field not in run:
                raise BenchmarkError(f"Completed benchmark run is missing {field}")


def metrics_from_report(report: dict[str, object]) -> dict[str, object]:
    try:
        file_info = report["file"]
        readiness = report["readiness"]
        renderer = report["renderer"]
        editability = report["metrics"]["editability"]  # type: ignore[index]
        findings = report["findings"]
        assert isinstance(file_info, dict)
        assert isinstance(readiness, dict)
        assert isinstance(renderer, dict)
        assert isinstance(editability, dict)
        assert isinstance(findings, list)
    except (KeyError, TypeError, AssertionError) as exc:
        raise BenchmarkError("PPTLint report is missing benchmark metrics") from exc
    return {
        "slides": int(file_info["slides"]),
        "readiness": str(readiness["status"]),
        "highConfidenceIssues": sum(
            isinstance(item, dict) and item.get("confidence") == "high" for item in findings
        ),
        "renderSucceeded": renderer.get("status") == "ok" and renderer.get("used") == "libreoffice",
        "nativeObjectRatio": float(editability["nativeObjectRatio"]),
        "privacyIssues": sum(
            isinstance(item, dict) and item.get("category") == "privacy" for item in findings
        ),
        "repairPassed": None,
    }


def summarize_runs(runs: list[dict[str, object]]) -> dict[str, object]:
    grouped: dict[str, list[dict[str, object]]] = defaultdict(list)
    for run in runs:
        if run.get("status") == "complete" and isinstance(run.get("metrics"), dict):
            grouped[str(run["projectId"])].append(run["metrics"])  # type: ignore[arg-type]
    projects: dict[str, dict[str, object]] = {}
    for project_id, metrics in sorted(grouped.items()):
        run_count = len(metrics)
        slides = sum(int(item["slides"]) for item in metrics)
        high_confidence = sum(int(item["highConfidenceIssues"]) for item in metrics)
        repairs = [item["repairPassed"] for item in metrics if item.get("repairPassed") is not None]
        projects[project_id] = {
            "completedRuns": run_count,
            "blockedRate": round(sum(item["readiness"] == "blocked" for item in metrics) / run_count, 4),
            "highConfidenceIssuesPer10Slides": round(high_confidence * 10 / max(1, slides), 4),
            "renderSuccessRate": round(sum(bool(item["renderSucceeded"]) for item in metrics) / run_count, 4),
            "averageNativeObjectRatio": round(
                sum(float(item["nativeObjectRatio"]) for item in metrics) / run_count,
                4,
            ),
            "privacyIssues": sum(int(item["privacyIssues"]) for item in metrics),
            "repairPassRate": (
                round(sum(bool(value) for value in repairs) / len(repairs), 4) if repairs else None
            ),
        }
    return {
        "schemaVersion": "pptlint-benchmark-summary/v1",
        "method": "evidence-matrix-without-overall-winner",
        "projects": projects,
    }
