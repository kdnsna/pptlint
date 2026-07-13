from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from decklint.cli import build_parser


ROOT = Path(__file__).resolve().parents[1]


def test_case_lab_has_twelve_complete_honest_cases() -> None:
    lab = ROOT / "site" / "lab"
    data = json.loads((lab / "cases.json").read_text(encoding="utf-8"))
    cases = data["cases"]
    assert len(cases) == 12
    assert len({case["slug"] for case in cases}) == 12
    for case in cases:
        assert case["kind"] == "controlled"
        assert case["scoreBefore"] < case["scoreAfter"] <= 100
        assert case["before"] and case["after"] and case["rule"]
        page = lab / "cases" / f'{case["slug"]}.html'
        assert page.exists()
        markup = page.read_text(encoding="utf-8")
        assert case["title"] in markup
        assert "可控演示" in markup
        assert "并非客户证言" in markup
        assert "--rule" not in markup
        assert markup.count("</body>") == 1
        assert markup.count("</html>") == 1


def test_case_lab_recheck_command_matches_cli_contract() -> None:
    args = build_parser().parse_args(
        ["check", "deck.pptx", "--scenario", "present", "--lang", "zh-CN"]
    )
    assert args.command == "check"
    assert args.scenario == "present"
    assert args.lang == "zh-CN"


def test_case_lab_has_attributed_market_audits() -> None:
    data = json.loads((ROOT / "site" / "lab" / "cases.json").read_text(encoding="utf-8"))
    audits = data["featuredSamples"]
    assert len(audits) >= 4
    assert all(len(audit["sha256"]) == 64 for audit in audits)
    validation = json.loads(
        (ROOT / "validation" / "public-sample-validation.json").read_text(encoding="utf-8")
    )
    known = {item["sha256"] for item in validation["results"]}
    assert {audit["sha256"] for audit in audits} <= known


def test_generated_case_lab_is_current() -> None:
    result = subprocess.run(
        [sys.executable, "tools/build_case_lab.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_case_lab_index_is_well_formed_enough_for_static_hosting() -> None:
    markup = (ROOT / "site" / "lab" / "index.html").read_text(encoding="utf-8")
    assert markup.count("</body>") == 1
    assert markup.count("</html>") == 1
    assert markup.index("document.querySelectorAll('.filter')") < markup.index("</body>")
