from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from pptlint.edit_eval import (
    EditEvalError,
    build_guidance_context,
    build_run_plan,
    evaluate_case_by_id,
    evaluate_guidance_case,
    read_json_object,
    resolve_private_source,
    source_map,
    validate_suite,
    verify_case_source,
    verify_private_source,
)


DEFAULT_SUITE = Path("benchmark/editing/cases.json")
DEFAULT_SOURCES = Path("benchmark/editing/sources.json")
DEFAULT_GUIDANCE_RESULT = Path("benchmark/editing/results/pptlint-guidance-optimized.json")
DEFAULT_GUIDANCE_MARKDOWN = Path("benchmark/editing/results/pptlint-guidance-optimized.md")


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def parse_source_overrides(values: list[str]) -> dict[str, Path]:
    overrides: dict[str, Path] = {}
    for value in values:
        source_id, separator, path = value.partition("=")
        if not separator or not source_id or not path:
            raise EditEvalError("Source overrides must use source-id=/absolute/path.pptx")
        overrides[source_id] = Path(path).expanduser()
    return overrides


def validate_command(args: argparse.Namespace) -> int:
    suite = read_json_object(args.suite)
    sources = read_json_object(args.sources)
    validate_suite(suite, sources)
    checks = []
    registry = source_map(sources)
    overrides = parse_source_overrides(args.source)
    case_checks = []
    for source_id, path in overrides.items():
        if source_id not in registry:
            raise EditEvalError(f"Unknown source override: {source_id}")
        checks.append(verify_private_source(registry[source_id], path))
        case_checks.extend(
            verify_case_source(case, path)
            for case in suite["cases"]
            if case.get("sourceId") == source_id and case.get("mode") == "edit"
        )
    payload = {
        "schemaVersion": "pptlint-edit-eval-validation/v1",
        "cases": len(suite["cases"]),
        "sources": len(registry),
        "privateSourceChecks": checks,
        "caseInputChecks": case_checks,
        "passed": all(item["passed"] for item in checks + case_checks),
    }
    if args.output:
        write_json(args.output, payload)
    else:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["passed"] else 1


def plan_command(args: argparse.Namespace) -> int:
    suite = read_json_object(args.suite)
    sources = read_json_object(args.sources)
    validate_suite(suite, sources)
    write_json(args.output, build_run_plan(suite))
    return 0


def evaluate_command(args: argparse.Namespace) -> int:
    suite = read_json_object(args.suite)
    sources = read_json_object(args.sources)
    validate_suite(suite, sources)
    result = evaluate_case_by_id(
        suite,
        sources,
        args.case_id,
        args.source,
        args.output_pptx,
        duration_seconds=args.duration,
        human_score=args.human_score,
    )
    write_json(args.result, result)
    return 0 if result["hardGatePassed"] else 1


def guidance_markdown(payload: dict[str, object]) -> str:
    summary = payload["summary"]
    cases = payload["cases"]
    assert isinstance(summary, dict) and isinstance(cases, list)
    lines = [
        "# PPTLint 人工指导质量评测",
        "",
        "这项研发评测只检查问题定位、处理路线、人工步骤和复检说明，不把未执行的修改记为完成。",
        "",
        f"- 业务案例：{summary['businessCases']}",
        f"- 规则内问题：{summary['lintDetectable']}，正确定位 {summary['targetDetected']}",
        f"- 指令型修改：{summary['instructionOnly']}，不计为 PPTLint 漏检",
        f"- 错误自动化承诺：{summary['falseAutomationPromises']}",
        f"- 结论：{'PASS' if payload['passed'] else 'BLOCKED'}",
        "",
        "| 案例 | 范围 | 定位 | 路线 | 人工步骤 | 复检 | 自动化误导 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for case in cases:
        assert isinstance(case, dict)

        def value(key: str) -> str:
            if case.get(key) is None:
                return "—"
            return "是" if case.get(key) else "否"

        lines.append(
            "| {case} | {scope} | {detected} | {route} | {steps} | {verify} | {promise} |".format(
                case=case["caseId"],
                scope="规则内" if case["scopeClass"] == "lint-detectable" else "指令型",
                detected=value("targetDetected"),
                route=value("routeCorrect"),
                steps=value("hasManualSteps"),
                verify=value("hasVerificationStep"),
                promise="是" if case["falseAutomationPromise"] else "否",
            )
        )
    return "\n".join(lines) + "\n"


def guidance_command(args: argparse.Namespace) -> int:
    suite = read_json_object(args.suite)
    sources = read_json_object(args.sources)
    validate_suite(suite, sources)
    registry = source_map(sources)
    overrides = parse_source_overrides(args.source)
    cases = [
        case
        for case in suite["cases"]
        if case.get("track") == "business-edit" and case.get("mode") == "edit"
    ]
    source_ids = sorted({str(case["sourceId"]) for case in cases})
    contexts: dict[str, tuple[Path, dict[str, object], float]] = {}
    source_runs = []
    for source_id in source_ids:
        source = registry[source_id]
        path = resolve_private_source(source, overrides=overrides)
        verification = verify_private_source(source, path)
        plan, duration = build_guidance_context(path)
        contexts[source_id] = (path, plan, duration)
        source_runs.append(
            {
                "sourceId": source_id,
                "sha256": verification["sha256"],
                "slides": verification["slides"],
                "durationSeconds": duration,
                "passed": verification["passed"],
            }
        )
    results = []
    for case in cases:
        source_id = str(case["sourceId"])
        path, plan, duration = contexts[source_id]
        results.append(
            evaluate_guidance_case(
                case,
                registry[source_id],
                path,
                plan=plan,
                duration_seconds=duration,
            )
        )
    lint_results = [case for case in results if case["scopeClass"] == "lint-detectable"]
    instruction_results = [case for case in results if case["scopeClass"] == "instruction-only"]
    payload = {
        "schemaVersion": "pptlint-guidance-eval/v1",
        "summary": {
            "businessCases": len(results),
            "lintDetectable": len(lint_results),
            "instructionOnly": len(instruction_results),
            "targetDetected": sum(case["targetDetected"] is True for case in lint_results),
            "guidancePassed": sum(case["passed"] is True for case in results),
            "falseAutomationPromises": sum(
                case["falseAutomationPromise"] is True for case in results
            ),
        },
        "sourceRuns": source_runs,
        "cases": results,
        "passed": all(run["passed"] for run in source_runs)
        and all(case["passed"] for case in results),
    }
    write_json(args.output, payload)
    args.markdown.parent.mkdir(parents=True, exist_ok=True)
    args.markdown.write_text(guidance_markdown(payload), encoding="utf-8")
    return 0 if payload["passed"] else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate and score PPT editing evaluation runs.")
    commands = parser.add_subparsers(dest="command", required=True)

    validate = commands.add_parser("validate", help="Validate definitions and optional private inputs.")
    validate.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    validate.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    validate.add_argument(
        "--source",
        action="append",
        default=[],
        metavar="ID=PATH",
        help="Verify a private source without storing its local path.",
    )
    validate.add_argument("--output", type=Path)
    validate.set_defaults(handler=validate_command)

    plan = commands.add_parser("plan", help="Create a path-free run plan.")
    plan.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    plan.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    plan.add_argument("--output", type=Path, default=Path("benchmark/editing/run-plan.json"))
    plan.set_defaults(handler=plan_command)

    evaluate = commands.add_parser("evaluate", help="Score one fixed-source editing output.")
    evaluate.add_argument("case_id")
    evaluate.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    evaluate.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    evaluate.add_argument(
        "--source",
        type=Path,
        help="Original PPTX for edit cases; prior-run PPTX for source-grounded revisions.",
    )
    evaluate.add_argument("--output-pptx", type=Path, required=True)
    evaluate.add_argument("--duration", type=float, required=True)
    evaluate.add_argument("--human-score", type=float)
    evaluate.add_argument("--result", type=Path, required=True)
    evaluate.set_defaults(handler=evaluate_command)

    guidance = commands.add_parser(
        "guidance", help="Audit detection, routes, manual steps and verification guidance."
    )
    guidance.add_argument("--suite", type=Path, default=DEFAULT_SUITE)
    guidance.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    guidance.add_argument(
        "--source",
        action="append",
        default=[],
        metavar="ID=PATH",
        help="Private source override; all six business sources are required via flags or env.",
    )
    guidance.add_argument("--output", type=Path, default=DEFAULT_GUIDANCE_RESULT)
    guidance.add_argument("--markdown", type=Path, default=DEFAULT_GUIDANCE_MARKDOWN)
    guidance.set_defaults(handler=guidance_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        args = build_parser().parse_args(argv)
        return args.handler(args)
    except (EditEvalError, OSError, ValueError) as exc:
        print(f"Editing evaluation command failed: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
