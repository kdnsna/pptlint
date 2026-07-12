from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .comparison import ComparisonError, load_audit_report
from .comparison_report import build_comparison_report, write_comparison_reports
from .model import DeckLoadError, load_deck
from .policy import POLICY_TEMPLATE, apply_policy, load_policy
from .render import RenderError, render_deck
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
        prog="pptlint", description="Preflight checks for AI-generated PowerPoint files."
    )
    subcommands = parser.add_subparsers(dest="command", required=True)
    check = subcommands.add_parser("check", help="Check whether a PPTX is ready to deliver.")
    _add_check_arguments(check, output="pptlint-report", fail_on="none")
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
    policy = subcommands.add_parser("policy", help="Create a delivery policy template.")
    policy.add_argument("action", choices=("init",))
    policy.add_argument("output", type=Path, nargs="?", default=Path("pptlint-policy.yml"))
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
    if policy is not None:
        findings.extend(apply_policy(deck, policy))
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
    if args.command == "check" and report["readiness"]["status"] == "blocked":
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
        print("说明：分数只用于比较同一份文件，不代表审美满分或绝对零风险。")
    else:
        print(f"PPTLint proof: {overall['before']} -> {overall['after']} ({int(overall['delta']):+d})")
        print(f"Resolved {resolved} · Remaining {remaining} · New {new} · New high-confidence {new_high}")
        print(f"Before report: {before_paths[0]}")
        print(f"After report: {after_paths[0]}")
        print(f"Complete comparison: {comparison_paths[0]}")
        print("Note: the score compares this deck before and after; it is not an aesthetic or zero-risk guarantee.")
    return 0 if comparison["gate"]["passed"] else 1


def _run_plan(args: argparse.Namespace) -> int:
    try:
        report = load_audit_report(args.report.expanduser())
        output = args.output.expanduser()
        language = args.lang or str(report.get("language", "en"))
        actions = report.get("priorityActions", [])
        if not isinstance(actions, list):
            raise ValueError("Report priorityActions must be an array")
        file_info = report.get("file", {})
        readiness = report.get("readiness", {})
        if not isinstance(file_info, dict) or not isinstance(readiness, dict):
            raise ValueError("Report file and readiness fields must be objects")
        zh = language == "zh-CN"
        lines = [
            "# PPTLint 修复简报" if zh else "# PPTLint repair brief",
            "",
            (f"- 文件：`{file_info.get('name', '')}`" if zh else f"- File: `{file_info.get('name', '')}`"),
            (f"- 交付结论：`{readiness.get('status', 'unknown')}`" if zh else f"- Readiness: `{readiness.get('status', 'unknown')}`"),
            (f"- 使用场景：`{report.get('scenario', 'present')}`" if zh else f"- Scenario: `{report.get('scenario', 'present')}`"),
            "- 原则：保留原文件，只修改独立副本；不要为了分数破坏已有设计。" if zh else "- Rule: preserve the source, edit a copy, and do not damage the design merely to increase a score.",
            "",
            "## 优先处理" if zh else "## Priority actions",
            "",
        ]
        if not actions:
            lines.append("当前没有优先修复动作。" if zh else "No priority repair action is required.")
        for index, action in enumerate(actions, 1):
            if not isinstance(action, dict):
                continue
            lines.extend(
                [
                    f"### {index}. {action.get('impact', '')}",
                    "",
                    (f"- 位置：{_action_location(action, zh=True)}" if zh else f"- Location: {_action_location(action, zh=False)}"),
                    (f"- 规则：`{action.get('ruleId', '')}`" if zh else f"- Rule: `{action.get('ruleId', '')}`"),
                ]
            )
            steps = action.get("fixSteps", [])
            if isinstance(steps, list):
                lines.extend(f"  {number}. {step}" for number, step in enumerate(steps, 1))
            lines.append("")
        source_name = str(file_info.get("name", "deck.pptx"))
        lines.extend(
            [
                "## 复检" if zh else "## Recheck",
                "",
                "```bash",
                f"pptlint check {source_name} --scenario {report.get('scenario', 'present')} --output pptlint-report",
                "```",
                "",
                "100 分只代表规则检查结果，不代表审美满分或绝对零风险。" if zh else "A score of 100 is a rule-check result, not an aesthetic grade or a zero-risk guarantee.",
            ]
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except (ComparisonError, OSError, UnicodeError, ValueError) as exc:
        print(f"PPTLint could not create the repair brief: {exc}", file=sys.stderr)
        return 2
    print(f"Repair brief: {output}")
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


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "compare":
        return _run_compare(args)
    if args.command == "proof":
        return _run_proof(args)
    if args.command == "plan":
        return _run_plan(args)
    if args.command == "policy":
        return _run_policy(args)
    return _run_audit(args)
