from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .model import DeckLoadError, load_deck
from .render import render_deck
from .report import build_report, write_reports
from .rules import audit_deck
from .scoring import score_findings


SEVERITY_RANK = {"low": 1, "medium": 2, "high": 3, "critical": 4}


def _score_value(value: str) -> int:
    score = int(value)
    if not 0 <= score <= 100:
        raise argparse.ArgumentTypeError("score must be between 0 and 100")
    return score


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="decklint", description="Lighthouse for PowerPoint.")
    subcommands = parser.add_subparsers(dest="command", required=True)
    audit = subcommands.add_parser("audit", help="Audit a PPTX and write offline HTML and JSON reports.")
    audit.add_argument("input", type=Path, help="PPTX file to audit")
    audit.add_argument("--output", type=Path, default=Path("decklint-report"), help="Report filename prefix")
    audit.add_argument("--profile", choices=("baseline", "ai-generated"), default="baseline")
    audit.add_argument("--renderer", choices=("auto", "wireframe", "libreoffice"), default="auto")
    audit.add_argument("--fail-on", choices=("none", "low", "medium", "high", "critical"), default="high")
    audit.add_argument("--min-score", type=_score_value, default=None)
    return parser


def _threshold_failed(findings, threshold: str) -> bool:
    if threshold == "none":
        return False
    threshold_rank = SEVERITY_RANK[threshold]
    return any(
        finding.confidence == "high" and SEVERITY_RANK[finding.severity] >= threshold_rank
        for finding in findings
    )


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        deck = load_deck(args.input.expanduser())
        findings = audit_deck(deck, profile=args.profile)
        scores = score_findings(findings)
        rendering = render_deck(deck, source=args.input.expanduser(), renderer=args.renderer)
        report = build_report(deck, findings, scores, rendering, profile=args.profile)
        html_path, json_path = write_reports(args.output.expanduser(), report)
    except (DeckLoadError, OSError, ValueError) as exc:
        print(f"DeckLint could not audit the file: {exc}", file=sys.stderr)
        return 2

    counts = report["summary"]
    print(
        f"DeckLint score {scores.overall}/100 · "
        f"{counts['critical']} critical, {counts['high']} high, {counts['medium']} medium, {counts['low']} low"
    )
    print(f"HTML report: {html_path}")
    print(f"JSON report: {json_path}")
    failed = _threshold_failed(findings, args.fail_on)
    if args.min_score is not None and scores.overall < args.min_score:
        failed = True
    return 1 if failed else 0

