from __future__ import annotations

import hashlib
import json
from pathlib import Path

import jsonschema
import pytest

from decklint.cli import build_parser, main
from decklint.model import load_deck
from decklint.repair_plan import build_repair_plan

from .pptx_factory import write_pptx


ROOT = Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_fix_applies_only_explicit_operations_and_preserves_source(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "内部版.pptx",
        creator="Alice Example",
        include_comments=True,
        notes_text="internal talking point",
    )
    output = tmp_path / "交付版.pptx"
    source_hash = _sha256(source)

    exit_code = main(
        [
            "fix",
            str(source),
            "--output",
            str(output),
            "--apply",
            "clear-personal-metadata",
            "--apply",
            "remove-comments",
            "--apply",
            "remove-speaker-notes",
            "--lang",
            "zh-CN",
        ]
    )

    assert exit_code == 0
    assert _sha256(source) == source_hash
    cleaned = load_deck(output)
    assert cleaned.metadata == {}
    assert cleaned.comments_count == 0
    assert all(not slide.notes_text for slide in cleaned.slides)

    receipt_path = tmp_path / "交付版.pptlint-repair-receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    jsonschema.validate(
        receipt,
        json.loads(
            (ROOT / "schema/pptlint-repair-receipt-v1.schema.json").read_text(encoding="utf-8")
        ),
    )
    assert receipt["verification"]["passed"] is True
    assert receipt["source"]["sha256"] == source_hash
    assert receipt["output"]["sha256"] == _sha256(output)
    assert {item["operation"] for item in receipt["operations"]} == {
        "clear-personal-metadata",
        "remove-comments",
        "remove-speaker-notes",
    }


def test_fix_does_not_touch_unselected_private_content(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "source.pptx",
        creator="Alice",
        include_comments=True,
        notes_text="keep until explicitly selected",
    )
    output = tmp_path / "metadata-only.pptx"

    assert main(
        [
            "fix",
            str(source),
            "--output",
            str(output),
            "--apply",
            "clear-personal-metadata",
        ]
    ) == 1

    cleaned = load_deck(output)
    assert cleaned.metadata == {}
    assert cleaned.comments_count == 1
    assert cleaned.slides[0].notes_text == "keep until explicitly selected"


def test_fix_refuses_missing_duplicate_same_or_existing_outputs(tmp_path: Path) -> None:
    clean = write_pptx(tmp_path / "clean.pptx")
    original_hash = _sha256(clean)

    with pytest.raises(SystemExit):
        build_parser().parse_args(["fix", str(clean), "--output", str(tmp_path / "out.pptx")])
    assert main(
        [
            "fix", str(clean), "--output", str(tmp_path / "unused.pptx"),
            "--apply", "remove-comments",
        ]
    ) == 1
    assert not (tmp_path / "unused.pptx").exists()
    assert main(
        ["fix", str(clean), "--output", str(clean), "--apply", "remove-comments"]
    ) == 2
    assert main(
        ["fix", str(clean), "--output", str(tmp_path / "not-a-ppt.txt"),
         "--apply", "remove-comments"]
    ) == 2
    existing = write_pptx(tmp_path / "existing.pptx", include_comments=True)
    assert main(
        ["fix", str(existing), "--output", str(clean), "--apply", "remove-comments"]
    ) == 2
    assert _sha256(clean) == original_hash


def test_proof_can_verify_a_subset_repair_plan(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "before.pptx", notes_text="remove me")
    report_stem = tmp_path / "report"
    assert main(
        ["check", str(source), "--renderer", "wireframe", "--output", str(report_stem)]
    ) in {0, 1}
    report = json.loads(report_stem.with_suffix(".json").read_text(encoding="utf-8"))
    plan = build_repair_plan(report)
    plan["tasks"] = [
        task for task in plan["tasks"] if task["ruleId"] == "privacy.speaker-notes"
    ]
    plan["summary"]["taskCount"] = len(plan["tasks"])
    plan_path = tmp_path / "repair-plan.json"
    plan_path.write_text(json.dumps(plan), encoding="utf-8")

    output = tmp_path / "after.pptx"
    assert main(
        [
            "fix", str(source), "--output", str(output),
            "--apply", "remove-speaker-notes",
        ]
    ) == 0
    proof_stem = tmp_path / "proof"
    assert main(
        [
            "proof", str(source), str(output), "--renderer", "wireframe",
            "--plan", str(plan_path), "--output", str(proof_stem),
        ]
    ) == 0

    verification = json.loads(
        Path(f"{proof_stem}-verification.json").read_text(encoding="utf-8")
    )
    jsonschema.validate(
        verification,
        json.loads(
            (ROOT / "schema/pptlint-repair-verification-v1.schema.json").read_text(
                encoding="utf-8"
            )
        ),
    )
    assert verification["passed"] is True
    assert verification["completedTaskIds"] == [plan["tasks"][0]["taskId"]]
    assert verification["remainingTaskIds"] == []
    assert verification["regressions"] == []
