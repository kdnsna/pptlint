from __future__ import annotations

import argparse
import json
import shutil
import sys
import webbrowser
from pathlib import Path

from . import __version__
from .cleanup import CleanupError, CleanupNotApplicable, OPERATIONS, create_cleanup_copy, sha256_path
from .comparison import ComparisonError, load_audit_report
from .comparison_report import build_comparison_report, write_comparison_reports
from .model import DeckLoadError, load_deck
from .policy import POLICY_TEMPLATE, apply_exceptions, apply_policy, load_policy
from .render import RenderError, render_deck
from .repair_plan import ADAPTERS, build_repair_plan, render_repair_brief, write_repair_plan
from .repair_verification import (
    build_repair_verification,
    load_repair_plan,
    write_repair_verification,
)
from .report import build_report, write_reports
from .rules import audit_deck
from .scoring import score_findings


SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _score_value(value: str) -> int:
    score = int(value)
    if not 0 <= score <= 100:
        raise argparse.ArgumentTypeError("score must be between 0 and 100")
    return score


def _add_check_arguments(command: argparse.ArgumentParser, *, output: str, fail_on: str) -> None:
    command.add_argument("input", type=Path, help="PPTX file to check")
    command.add_argument("--output", type=Path, default=Path(output), help="Report filename prefix")
    command.add_argument("--profile", choices=("baseline", "ai-generated"), default="baseline")
    command.add_argument(
        "--scenario",
        choices=("present", "screen", "document"),
        default="present",
        help="Intended use: room presentation, screen reading, or document-style deck",
    )
    command.add_argument("--renderer", choices=("auto", "wireframe", "libreoffice"), default="auto")
    command.add_argument("--soffice-path", help="Optional path to the LibreOffice soffice executable")
    command.add_argument("--fail-on", choices=("none", "low", "medium", "high", "critical"), default=fail_on)
    command.add_argument("--min-score", type=_score_value, default=None)
    command.add_argument("--lang", choices=("en", "zh-CN"), default="en", help="Report language")
    command.add_argument(
        "--report-mode",
        choices=("full", "shareable"),
        default="full",
        help="Full local evidence or a redacted report that is safer to share",
    )
    command.add_argument("--policy", type=Path, default=None, help="Optional YAML delivery policy")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="pptlint",
        description="Local PowerPoint preflight, explicit cleanup copies, and repair verification.",
    )
    parser.add_argument("--version", action="version", version=f"PPTLint {__version__}")
    subcommands = parser.add_subparsers(dest="command", required=True)
    check = subcommands.add_parser("check", help="Check whether a PPTX is ready to deliver.")
    _add_check_arguments(check, output="pptlint-report", fail_on="none")
    start = subcommands.add_parser("start", help="Check a PPTX and open the local HTML report.")
    _add_check_arguments(start, output="pptlint-report", fail_on="none")
    start.add_argument("--no-open", action="store_true", help="Write reports without opening a browser")
    audit = subcommands.add_parser("audit", help="Audit a PPTX and write offline HTML and JSON reports.")
    _add_check_arguments(audit, output="decklint-report", fail_on="high")
    compare = subcommands.add_parser("compare", help="Compare two PPTLint audit reports.")
    compare.add_argument("before", type=Path, help="Before audit JSON report")
    compare.add_argument("after", type=Path, help="After audit JSON report")
    compare.add_argument(
        "--output",
        type=Path,
        default=Path("decklint-comparison"),
        help="Comparison report filename prefix",
    )
    compare.add_argument(
        "--fail-on-regression",
        choices=("none", "low", "medium", "high", "critical"),
        default="high",
    )
    proof = subcommands.add_parser(
        "proof", help="Check two PPTX files and create a complete before/after proof report."
    )
    proof.add_argument("before", type=Path, help="PPTX before changes")
    proof.add_argument("after", type=Path, help="PPTX after changes")
    proof.add_argument(
        "--output", type=Path, default=Path("pptlint-proof"), help="Proof report filename prefix"
    )
    proof.add_argument("--profile", choices=("baseline", "ai-generated"), default="baseline")
    proof.add_argument(
        "--scenario", choices=("present", "screen", "document"), default="present"
    )
    proof.add_argument("--renderer", choices=("auto", "wireframe", "libreoffice"), default="auto")
    proof.add_argument("--soffice-path", help="Optional path to the LibreOffice soffice executable")
    proof.add_argument("--lang", choices=("en", "zh-CN"), default="en", help="Report language")
    proof.add_argument("--report-mode", choices=("full", "shareable"), default="full")
    proof.add_argument("--policy", type=Path, default=None, help="Optional YAML delivery policy")
    proof.add_argument("--plan", type=Path, default=None, help="Optional pptlint-repair-plan/v1 JSON")
    proof.add_argument(
        "--fail-on-regression",
        choices=("none", "low", "medium", "high", "critical"),
        default="high",
    )
    plan = subcommands.add_parser(
        "plan", help="Turn a PPTLint JSON report into an agent-ready repair brief."
    )
    plan.add_argument("report", type=Path, help="PPTLint JSON report")
    plan.add_argument("--output", type=Path, default=Path("pptlint-repair-brief.md"))
    plan.add_argument("--lang", choices=("en", "zh-CN"), default=None)
    plan.add_argument("--format", choices=("markdown", "json"), default="markdown")
    plan.add_argument("--adapter", choices=ADAPTERS, default="generic-agent")
    fix = subcommands.add_parser(
        "fix", help="Create a separate copy with explicitly approved privacy cleanup."
    )
    fix.add_argument("input", type=Path, help="Source PPTX; it is never modified")
    fix.add_argument("--output", type=Path, required=True, help="New cleaned PPTX path")
    fix.add_argument("--apply", action="append", choices=OPERATIONS, required=True)
    fix.add_argument("--profile", choices=("baseline", "ai-generated"), default="baseline")
    fix.add_argument("--scenario", choices=("present", "screen", "document"), default="present")
    fix.add_argument("--renderer", choices=("wireframe", "libreoffice"), default="wireframe")
    fix.add_argument("--soffice-path", default=None)
    fix.add_argument("--lang", choices=("en", "zh-CN"), default="en")
    fix.add_argument("--policy", type=Path, default=None)
    policy = subcommands.add_parser("policy", help="Create a delivery policy template.")
    policy.add_argument("action", choices=("init",))
    policy.add_argument("output", type=Path, nargs="?", default=Path("pptlint-policy.yml"))
    doctor = subcommands.add_parser("doctor", help="Show local PPTLint capabilities.")
    doctor.add_argument("--json", action="store_true", dest="as_json")
    app = subcommands.add_parser("app", help="Open the token-protected local drag-and-drop app.")
    app.add_argument("--port", type=int, default=0, help="Loopback port; 0 chooses a random port")
    app.add_argument("--no-open", action="store_true", help="Do not open the browser automatically")
    return parser


def _threshold_failed(findings, threshold: str) -> bool:
    if threshold == "none":
        return False
    threshold_rank = SEVERITY_RANK[threshold]
    return any(
        finding.confidence == "high" and SEVERITY_RANK[finding.severity] >= threshold_rank
        for finding in findings
    )


def _action_location(action: dict[str, object], *, zh: bool) -> str:
    slides = action.get("affectedSlides")
    if isinstance(slides, list) and slides:
        numbers = [str(value) for value in slides[:5]]
        suffix = "等" if zh and len(slides) > 5 else ("…" if len(slides) > 5 else "")
        return f"第 {'、'.join(numbers)} 页{suffix}" if zh else f"Slides {', '.join(numbers)}{suffix}"
    slide = action.get("slideIndex")
    if slide:
        return f"第 {slide} 页" if zh else f"Slide {slide}"
    return "整个文件" if zh else "Whole file"


def _build_audit_report(
    source: Path,
    *,
    profile: str,
    renderer: str,
    soffice_path: str | None,
    language: str,
    scenario: str,
    policy_path: Path | None,
    report_mode: str,
) -> tuple[dict[str, object], list[object]]:
    source = source.expanduser()
    deck = load_deck(source)
    findings = audit_deck(deck, profile=profile, scenario=scenario)
    policy = load_policy(policy_path) if policy_path is not None else None
    waiver_records: list[dict[str, object]] = []
    if policy is not None:
        findings.extend(apply_policy(deck, policy))
        findings, waiver_records = apply_exceptions(findings, policy)
        findings.sort(key=lambda item: (item.slide_index or 0, item.rule_id, item.shape_id or ""))
    scores = score_findings(findings)
    rendering = render_deck(
        deck,
        source=source,
        renderer=renderer,
        soffice_path=soffice_path,
    )
    report = build_report(
        deck,
        findings,
        scores,
        rendering,
        profile=profile,
        language=language,
        scenario=scenario,
        policy_name=policy.name if policy is not None else None,
        policy_waivers=waiver_records,
        report_mode=report_mode,
    )
    return report, findings


def _run_audit(args: argparse.Namespace) -> int:
    try:
        report, findings = _build_audit_report(
            args.input,
            profile=args.profile,
            renderer=args.renderer,
            soffice_path=args.soffice_path,
            language=args.lang,
            scenario=args.scenario,
            policy_path=args.policy,
            report_mode=args.report_mode,
        )
        html_path, json_path = write_reports(args.output.expanduser(), report)
    except (DeckLoadError, RenderError, OSError, ValueError) as exc:
        print(f"PPTLint could not check the file: {exc}", file=sys.stderr)
        return 2

    status = report["readiness"]["status"]
    zh = args.lang == "zh-CN"
    result_label = (
        {"ready": "可以发送", "review": "发送前再看一眼", "blocked": "先处理再发送"}
        if zh
        else {"ready": "Ready to send", "review": "Check before sending", "blocked": "Fix before sending"}
    )[status]
    print(f"PPTLint 结果：{result_label}" if zh else f"PPTLint result: {result_label}")
    actions = report["priorityActions"]
    if actions:
        print("先做这几件事：" if zh else "Next actions:")
        for action in actions:
            location = _action_location(action, zh=zh)
            print(f"- {location}: {action['impact']}")
    else:
        print("没有发现必须处理的高把握交付问题。" if zh else "No high-confidence delivery problem was found.")
    if zh:
        print(f"打开 HTML 报告查看高亮页面：{html_path}")
        print(f"JSON 报告：{json_path}")
        print("说明：100 分仅表示本次规则检查结果，不代表审美满分或绝对零风险。")
    else:
        print(f"Open the HTML report for the highlighted slides: {html_path}")
        print(f"JSON report: {json_path}")
        print("Note: 100 is this rule-check score, not an aesthetic grade or a zero-risk guarantee.")
    failed = _threshold_failed(findings, args.fail_on)
    if args.command in {"check", "start"} and report["readiness"]["status"] == "blocked":
        failed = True
    if args.min_score is not None and int(report["scores"]["overall"]) < args.min_score:
        failed = True
    return 1 if failed else 0


def _run_compare(args: argparse.Namespace) -> int:
    try:
        before = load_audit_report(args.before.expanduser())
        after = load_audit_report(args.after.expanduser())
        report = build_comparison_report(
            before,
            after,
            threshold=args.fail_on_regression,
        )
        html_path, json_path = write_comparison_reports(args.output.expanduser(), report)
    except (ComparisonError, OSError, ValueError) as exc:
        print(f"PPTLint could not compare the reports: {exc}", file=sys.stderr)
        return 2

    overall = report["scores"]["overall"]
    print(f"PPTLint comparison {overall['before']} -> {overall['after']} ({overall['delta']:+d})")
    print(f"HTML report: {html_path}")
    print(f"JSON report: {json_path}")
    return 0 if report["gate"]["passed"] else 1


def _run_proof(args: argparse.Namespace) -> int:
    verification: dict[str, object] | None = None
    verification_path: Path | None = None
    try:
        before, _ = _build_audit_report(
            args.before,
            profile=args.profile,
            renderer=args.renderer,
            soffice_path=args.soffice_path,
            language=args.lang,
            scenario=args.scenario,
            policy_path=args.policy,
            report_mode=args.report_mode,
        )
        after, _ = _build_audit_report(
            args.after,
            profile=args.profile,
            renderer=args.renderer,
            soffice_path=args.soffice_path,
            language=args.lang,
            scenario=args.scenario,
            policy_path=args.policy,
            report_mode=args.report_mode,
        )
        output = args.output.expanduser()
        before_paths = write_reports(Path(f"{output}-before"), before)
        after_paths = write_reports(Path(f"{output}-after"), after)
        comparison = build_comparison_report(
            before,
            after,
            threshold=args.fail_on_regression,
        )
        comparison_paths = write_comparison_reports(output, comparison)
        if args.plan is not None:
            plan = load_repair_plan(args.plan.expanduser())
            verification = build_repair_verification(plan, comparison)
            verification_path = write_repair_verification(
                Path(f"{output}-verification.json"), verification
            )
    except (DeckLoadError, RenderError, ComparisonError, OSError, ValueError) as exc:
        message = f"PPTLint 无法生成对比证据：{exc}" if args.lang == "zh-CN" else f"PPTLint could not create the proof: {exc}"
        print(message, file=sys.stderr)
        return 2

    overall = comparison["scores"]["overall"]
    resolved = len(comparison["resolved"])
    remaining = len(comparison["persistent"])
    new = len(comparison["new"])
    new_high = sum(
        1
        for finding in comparison["new"]
        if finding.get("confidence") == "high"
        and SEVERITY_RANK.get(str(finding.get("severity")), 0) >= SEVERITY_RANK["high"]
    )
    if args.lang == "zh-CN":
        print(f"PPTLint 对比：{overall['before']} → {overall['after']}（{int(overall['delta']):+d}）")
        print(f"已处理 {resolved} 项 · 仍有 {remaining} 项 · 新增 {new} 项 · 新增高把握问题 {new_high} 项")
        print(f"修改前报告：{before_paths[0]}")
        print(f"修改后报告：{after_paths[0]}")
        print(f"完整对比：{comparison_paths[0]}")
        if verification_path is not None:
            print(f"修复任务验证：{verification_path}")
        print("说明：分数只用于比较同一份文件，不代表审美满分或绝对零风险。")
    else:
        print(f"PPTLint proof: {overall['before']} -> {overall['after']} ({int(overall['delta']):+d})")
        print(f"Resolved {resolved} · Remaining {remaining} · New {new} · New high-confidence {new_high}")
        print(f"Before report: {before_paths[0]}")
        print(f"After report: {after_paths[0]}")
        print(f"Complete comparison: {comparison_paths[0]}")
        if verification_path is not None:
            print(f"Repair verification: {verification_path}")
        print("Note: the score compares this deck before and after; it is not an aesthetic or zero-risk guarantee.")
    passed = bool(comparison["gate"]["passed"])
    if verification is not None:
        passed = passed and bool(verification["passed"])
    return 0 if passed else 1


def _fix_artifact_paths(output: Path) -> dict[str, Path]:
    stem = output.with_suffix("")
    return {
        "before": Path(f"{stem}.pptlint-before"),
        "after": Path(f"{stem}.pptlint-after"),
        "comparison": Path(f"{stem}.pptlint-comparison"),
        "receipt": Path(f"{stem}.pptlint-repair-receipt.json"),
    }


def _run_fix(args: argparse.Namespace) -> int:
    source = args.input.expanduser()
    output = args.output.expanduser()
    artifacts = _fix_artifact_paths(output)
    occupied = [
        path
        for key, stem in artifacts.items()
        for path in ([stem] if key == "receipt" else [Path(f"{stem}.html"), Path(f"{stem}.json")])
        if path.exists()
    ]
    if occupied:
        print(f"PPTLint could not create the cleaned copy: artifact already exists: {occupied[0].name}", file=sys.stderr)
        return 2
    try:
        before, _ = _build_audit_report(
            source,
            profile=args.profile,
            renderer=args.renderer,
            soffice_path=args.soffice_path,
            language=args.lang,
            scenario=args.scenario,
            policy_path=args.policy,
            report_mode="full",
        )
        source_sha256 = str(before["file"]["sha256"])
        cleanup = create_cleanup_copy(source, output, list(args.apply))
        if cleanup.source_sha256 != source_sha256 or sha256_path(source.resolve()) != source_sha256:
            raise CleanupError("Source file hash changed; verification stopped")
        after, _ = _build_audit_report(
            output,
            profile=args.profile,
            renderer=args.renderer,
            soffice_path=args.soffice_path,
            language=args.lang,
            scenario=args.scenario,
            policy_path=args.policy,
            report_mode="full",
        )
        before_paths = write_reports(artifacts["before"], before)
        after_paths = write_reports(artifacts["after"], after)
        comparison = build_comparison_report(before, after, threshold="high")
        comparison_paths = write_comparison_reports(artifacts["comparison"], comparison)

        operation_rules = {
            "clear-personal-metadata": {"privacy.personal-metadata"},
            "remove-comments": {"privacy.comments"},
            "remove-speaker-notes": {"privacy.speaker-notes", "policy.notes-forbidden"},
        }
        after_rules = {
            str(item.get("rule_id", ""))
            for item in after.get("findings", [])
            if isinstance(item, dict)
        }
        incomplete = [
            operation
            for operation in args.apply
            if operation_rules[operation] & after_rules
        ]
        readiness = after.get("readiness", {})
        blocked = isinstance(readiness, dict) and readiness.get("status") == "blocked"
        source_unchanged = sha256_path(source.resolve()) == source_sha256
        passed = bool(comparison["gate"]["passed"]) and not incomplete and not blocked and source_unchanged
        receipt = {
            "schemaVersion": "pptlint-repair-receipt/v1",
            "toolVersion": __version__,
            "source": {"name": source.name, "sha256": source_sha256},
            "output": {"name": output.name, "sha256": cleanup.output_sha256},
            "requestedOperations": list(args.apply),
            "operations": [
                {
                    "operation": item.operation,
                    "status": "applied",
                    "changedParts": list(item.changed_parts),
                    "changeCount": item.change_count,
                }
                for item in cleanup.operations
            ],
            "verification": {
                "passed": passed,
                "sourceHashUnchanged": source_unchanged,
                "outputOpened": True,
                "outputReadiness": str(readiness.get("status", "unknown")) if isinstance(readiness, dict) else "unknown",
                "comparisonGatePassed": bool(comparison["gate"]["passed"]),
                "incompleteOperations": incomplete,
            },
            "artifacts": {
                "beforeHtml": before_paths[0].name,
                "beforeJson": before_paths[1].name,
                "afterHtml": after_paths[0].name,
                "afterJson": after_paths[1].name,
                "comparisonHtml": comparison_paths[0].name,
                "comparisonJson": comparison_paths[1].name,
            },
        }
        artifacts["receipt"].write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    except CleanupNotApplicable as exc:
        print(f"PPTLint did not create a cleaned copy: {exc}", file=sys.stderr)
        return 1
    except (CleanupError, DeckLoadError, RenderError, ComparisonError, OSError, ValueError) as exc:
        print(f"PPTLint could not create the cleaned copy: {exc}", file=sys.stderr)
        return 2

    print(f"Cleaned copy: {output}")
    print(f"Repair receipt: {artifacts['receipt']}")
    print(f"Before/after proof: {artifacts['comparison']}.html")
    return 0 if passed else 1


def _run_plan(args: argparse.Namespace) -> int:
    try:
        report = load_audit_report(args.report.expanduser())
        output = args.output.expanduser()
        language = args.lang or str(report.get("language", "en"))
        repair_plan = build_repair_plan(report)
        if args.format == "json":
            write_repair_plan(output, repair_plan)
        else:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(
                render_repair_brief(repair_plan, adapter=args.adapter, language=language),
                encoding="utf-8",
            )
    except (ComparisonError, OSError, UnicodeError, ValueError) as exc:
        print(f"PPTLint could not create the repair brief: {exc}", file=sys.stderr)
        return 2
    print(f"{'Repair plan' if args.format == 'json' else 'Repair brief'}: {output}")
    return 0


def _run_policy(args: argparse.Namespace) -> int:
    output = args.output.expanduser()
    try:
        if output.exists():
            raise ValueError(f"Policy file already exists: {output}")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(POLICY_TEMPLATE, encoding="utf-8")
    except (OSError, ValueError) as exc:
        print(f"PPTLint could not create the policy: {exc}", file=sys.stderr)
        return 2
    print(f"Policy template: {output}")
    return 0


def _run_doctor(args: argparse.Namespace) -> int:
    soffice = shutil.which("soffice") or shutil.which("libreoffice")
    result = {
        "version": __version__,
        "python": sys.version.split()[0],
        "realRenderer": soffice or "",
        "wireframeRenderer": True,
        "supportedInput": [".pptx"],
        "localOnly": True,
        "localApp": True,
    }
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    else:
        print(f"PPTLint {result['version']}")
        print(f"Python: {result['python']}")
        print(f"Real slide renderer: {soffice or 'not found; wireframe fallback available'}")
        print("Input: .pptx · local only · source files are never modified")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "doctor":
        return _run_doctor(args)
    if args.command == "app":
        from .local_app import run_app

        return run_app(port=args.port, open_browser=not args.no_open)
    if args.command == "compare":
        return _run_compare(args)
    if args.command == "proof":
        return _run_proof(args)
    if args.command == "plan":
        return _run_plan(args)
    if args.command == "fix":
        return _run_fix(args)
    if args.command == "policy":
        return _run_policy(args)
    result = _run_audit(args)
    if args.command == "start" and result in {0, 1} and not args.no_open:
        webbrowser.open(Path(f"{args.output.expanduser()}.html").resolve().as_uri())
    return result
