from __future__ import annotations

from pathlib import Path

from decklint.cli import _build_audit_report
from decklint.comparison_report import build_comparison_report, write_comparison_reports
from decklint.report import write_reports


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples" / "proof-loop"
PROOF = ROOT / "site" / "proof-loop"


def main() -> int:
    reports = []
    for name in ("before", "after"):
        report, _ = _build_audit_report(
            EXAMPLES / f"{name}.pptx",
            profile="ai-generated",
            renderer="wireframe",
            soffice_path=None,
            language="zh-CN",
            scenario="present",
            policy_path=None,
            report_mode="full",
        )
        write_reports(PROOF / name, report)
        reports.append(report)
    comparison = build_comparison_report(reports[0], reports[1], threshold="high")
    write_comparison_reports(PROOF / "comparison", comparison)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
