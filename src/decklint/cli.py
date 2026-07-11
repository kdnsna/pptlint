from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .comparison import ComparisonError, load_audit_report
from .comparison_report import build_comparison_report, write_comparison_reports
from .model import DeckLoadError, load_deck
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
    command.add_argument("--renderer", choices=("auto", "wireframe", "libreoffice"), default="auto")
    command.add_argument("--soffice-path", help="Optional path to the LibreOffice soffice executable")
    command.add_argument("--fail-on", choices=("none", "low", "medium", "high", "critical"), default=fail_on)
    command.add_argument("--min-score", type=_score_value, default=None)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="pptlint", description="Preflight checks for AI-generated PowerPoint files.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    check = subcommands.add_parser("check", help="Check whether a PPTX is ready to deliver.")
    _add_check_arguments(check, output="pptlint-report", fail_on="none")
    audit = subcommands.add_parser("audit", help="Audit a PPTX and write offline HTML and JSON reports.")
    _add_check_arguments(audit, output="decklint-report", fail_on="high")
    compare = subcommands.add_parser("compare", help="Compare two DeckLint audit reports.")
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
    return parser


def _threshold_failed(findings, threshold: str) -> bool:
    if threshold == "none":
        return False
    threshold_rank = SEVERITY_RANK[threshold]
    return any(
        finding.confidence == "high" and SEVERITY_RANK[finding.severity] >= threshold_rank
        for finding in findings
    )


def _run_audit(args: argparse.Namespace) -> int:
    try:
        deck = load_deck(args.input.expanduser())
        findings = audit_deck(deck, profile=args.profile)
        scores = score_findings(findings)
        rendering = render_deck(
            deck,
            source=args.input.expanduser(),
            renderer=args.renderer,
            soffice_path=args.soffice_path,
        )
        report = build_report(deck, findings, scores, rendering, profile=args.profile)
        html_path, json_path = write_reports(args.output.expanduser(), report)
    except (DeckLoadError, RenderError, OSError, ValueError) as exc:
        print(f"PPTLint could not check the file: {exc}", file=sys.stderr)
        return 2

    counts = report["summary"]
    print(
        f"PPTLint readiness {report['readiness']['status']} · score {scores.overall}/100 · "
        f"{counts['critical']} critical, {counts['high']} high, {counts['medium']} medium, {counts['low']} low"
    )
    print(f"HTML report: {html_path}")
    print(f"JSON report: {json_path}")
    failed = _threshold_failed(findings, args.fail_on)
    if args.command == "check" and report["readiness"]["status"] == "blocked":
        failed = True
    if args.min_score is not None and scores.overall < args.min_score:
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
        print(f"DeckLint could not compare the reports: {exc}", file=sys.stderr)
        return 2

    overall = report["scores"]["overall"]
    print(
        f"DeckLint comparison {overall['before']} -> {overall['after']} "
        f"({overall['delta']:+d})"
    )
    print(f"HTML report: {html_path}")
    print(f"JSON report: {json_path}")
    return 0 if report["gate"]["passed"] else 1


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "compare":
        return _run_compare(args)
    return _run_audit(args)
