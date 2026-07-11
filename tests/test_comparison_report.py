from __future__ import annotations

import json
from pathlib import Path

import jsonschema

from decklint.comparison_report import build_comparison_report, write_comparison_reports

from .report_factory import make_report


ROOT = Path(__file__).resolve().parents[1]


def test_comparison_report_is_chinese_offline_and_deterministic(tmp_path: Path) -> None:
    comparison = build_comparison_report(
        make_report(name="before.pptx", score=80),
        make_report(name="after.pptx", score=95),
        threshold="high",
    )

    first = write_comparison_reports(tmp_path / "proof", comparison)
    second = write_comparison_reports(tmp_path / "proof-2", comparison)

    assert first[0].read_bytes() == second[0].read_bytes()
    assert first[1].read_bytes() == second[1].read_bytes()
    text = first[0].read_text(encoding="utf-8")
    assert '<html lang="zh-CN">' in text
    assert "已解决" in text and "新增问题" in text
    assert "http://" not in text and "https://" not in text
    assert str(tmp_path) not in text


def test_comparison_matches_public_schema() -> None:
    payload = build_comparison_report(
        make_report(name="before.pptx", score=80),
        make_report(name="after.pptx", score=95),
        threshold="high",
    )
    schema = json.loads(
        (ROOT / "schema/decklint-comparison-v1.schema.json").read_text(encoding="utf-8")
    )

    jsonschema.validate(payload, schema)
