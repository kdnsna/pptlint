from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


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
        assert "不是客户证言" in markup


def test_case_lab_has_attributed_market_audits() -> None:
    data = json.loads((ROOT / "site" / "lab" / "cases.json").read_text(encoding="utf-8"))
    audits = data["marketAudits"]
    assert len(audits) >= 4
    assert all(str(audit["source"]).startswith("https://github.com/") for audit in audits)
    assert all(str(audit["sourceFile"]).endswith(".pptx") for audit in audits)
    assert all(len(audit["sha256"]) == 64 for audit in audits)


def test_generated_case_lab_is_current() -> None:
    result = subprocess.run(
        [sys.executable, "tools/build_case_lab.py", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
