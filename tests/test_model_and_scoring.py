from __future__ import annotations

from pathlib import Path

from decklint.model import load_deck
from decklint.rules import audit_deck
from decklint.schema import BBox, Finding, identified_findings
from decklint.scoring import score_findings

from .pptx_factory import slide_xml, write_pptx


def test_load_deck_builds_normalized_model(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "quarterly-review.pptx")

    deck = load_deck(source)

    assert deck.filename == "quarterly-review.pptx"
    assert len(deck.sha256) == 64
    assert deck.width == 12_192_000
    assert deck.height == 6_858_000
    assert len(deck.slides) == 1
    assert deck.slides[0].title == "Quarterly Review"
    assert deck.slides[0].shapes[1].bbox.normalized(deck.width, deck.height).w == 0.85


def test_scoring_ignores_low_confidence_and_caps_integrity_critical() -> None:
    findings = [
        Finding(
            rule_id="integrity.broken-relationship",
            category="integrity",
            severity="critical",
            confidence="high",
            message="Broken relationship",
            evidence="ppt/media/missing.png",
            remediation="Restore the missing media.",
            slide_index=1,
            shape_id=None,
            bbox=BBox(0, 0, 0, 0),
        ),
        Finding(
            rule_id="readability.repeated-layout",
            category="consistency",
            severity="high",
            confidence="low",
            message="Possible repeated layout",
            evidence="three similar slides",
            remediation="Review the slide rhythm.",
            slide_index=1,
            shape_id=None,
            bbox=None,
        ),
    ]

    scores = score_findings(findings)

    assert scores.categories["integrity"] == 70
    assert scores.categories["consistency"] == 100
    assert scores.overall == 49
    payload = scores.to_dict()
    assert payload["weights"]["integrity"] == 0.30
    assert payload["policy"]["perRuleCap"] == 30
    assert payload["deductions"][0]["applied"] == 30
    assert payload["deductions"][1]["applied"] == 0
    assert payload["deductions"][1]["reason"] == "low-confidence"


def test_load_deck_uses_presentation_order_not_slide_filename_order(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "reordered.pptx",
        slides=[slide_xml(title="First file"), slide_xml(title="Second file")],
        slide_order=[2, 1],
    )

    deck = load_deck(source)

    assert [slide.title for slide in deck.slides] == ["Second file", "First file"]


def test_load_deck_attaches_speaker_notes_to_slide(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "notes.pptx", notes_text="Confidential speaker note")

    deck = load_deck(source)

    assert deck.slides[0].notes_text == "Confidential speaker note"


def test_orphan_slide_part_is_not_treated_as_active_content(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "orphan.pptx", slide_order=[])

    deck = load_deck(source)

    assert deck.slides == []
    assert deck.orphan_slide_parts == ["ppt/slides/slide1.xml"]
    ids = {finding.rule_id for finding in audit_deck(deck)}
    assert {"integrity.empty-deck", "integrity.orphan-slide-part"} <= ids


def test_group_transform_maps_child_coordinate_space_to_slide(tmp_path: Path) -> None:
    grouped_slide = '''<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>
<p:grpSp><p:nvGrpSpPr><p:cNvPr id="2" name="Group"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm><a:off x="100" y="200"/><a:ext cx="2000" cy="1000"/><a:chOff x="10" y="20"/><a:chExt cx="1000" cy="500"/></a:xfrm></p:grpSpPr>
<p:sp><p:nvSpPr><p:cNvPr id="3" name="Child"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="110" y="70"/><a:ext cx="100" cy="50"/></a:xfrm></p:spPr><p:txBody><a:p><a:r><a:t>Child</a:t></a:r></a:p></p:txBody></p:sp>
</p:grpSp></p:spTree></p:cSld></p:sld>'''
    source = write_pptx(tmp_path / "scaled-group.pptx", slides=[grouped_slide])

    shape = load_deck(source).slides[0].shapes[0]

    assert shape.shape_id == "2/3"
    assert shape.bbox == BBox(300, 300, 200, 100)


def test_group_transform_applies_rotation_and_horizontal_flip(tmp_path: Path) -> None:
    grouped_slide = '''<?xml version="1.0" encoding="UTF-8"?>
<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><p:cSld><p:spTree>
<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr><p:grpSpPr/>
<p:grpSp><p:nvGrpSpPr><p:cNvPr id="2" name="Group"/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>
<p:grpSpPr><a:xfrm rot="5400000" flipH="1"><a:off x="100" y="100"/><a:ext cx="200" cy="200"/><a:chOff x="0" y="0"/><a:chExt cx="200" cy="200"/></a:xfrm></p:grpSpPr>
<p:sp><p:nvSpPr><p:cNvPr id="3" name="Child"/><p:cNvSpPr/><p:nvPr/></p:nvSpPr><p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="50" cy="100"/></a:xfrm></p:spPr><p:txBody><a:p><a:r><a:t>Child</a:t></a:r></a:p></p:txBody></p:sp>
</p:grpSp></p:spTree></p:cSld></p:sld>'''
    source = write_pptx(tmp_path / "rotated-flipped-group.pptx", slides=[grouped_slide])

    shape = load_deck(source).slides[0].shapes[0]

    assert shape.bbox == BBox(200, 250, 100, 50)


def test_missing_presentation_slide_relationship_is_critical(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "missing-slide-rel.pptx",
        slides=[slide_xml(title="Valid")],
        slide_order=[1, 2],
    )

    deck = load_deck(source)
    findings = audit_deck(deck)

    assert len(deck.slides) == 1
    broken = [finding for finding in findings if finding.rule_id == "integrity.broken-relationship"]
    assert any(finding.severity == "critical" and "rId2" in finding.evidence for finding in broken)


def test_lookalike_slide_relationship_type_is_rejected(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "lookalike-slide-rel.pptx",
        presentation_relationship_type="https://attacker.invalid/custom/slide",
    )

    deck = load_deck(source)
    findings = audit_deck(deck)

    assert deck.slides == []
    assert "integrity.broken-relationship" in {finding.rule_id for finding in findings}


def test_slide_relationship_cannot_target_a_non_slide_part(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "slide-targets-core-properties.pptx",
        creator="Alice",
        presentation_relationship_target="../docProps/core.xml",
    )

    deck = load_deck(source)
    findings = audit_deck(deck)

    assert deck.slides == []
    assert any(
        finding.rule_id == "integrity.broken-relationship" and "rId1" in finding.evidence
        for finding in findings
    )


def test_repeated_deck_level_rule_ids_remain_unique() -> None:
    findings = [
        Finding(
            rule_id="privacy.external-relationship",
            category="privacy",
            severity="high",
            confidence="high",
            message="External relationship",
            evidence=target,
            remediation="Review it.",
        )
        for target in ("https://one.example", "https://two.example")
    ]

    ids = [finding_id for finding_id, _ in identified_findings(findings)]

    assert len(ids) == len(set(ids)) == 2


def test_reported_deductions_never_exceed_actual_category_score_drop() -> None:
    findings = [
        Finding(
            rule_id=f"integrity.rule-{index}",
            category="integrity",
            severity="critical",
            confidence="high",
            message="Critical integrity problem",
            evidence=str(index),
            remediation="Repair it.",
        )
        for index in range(5)
    ]

    scores = score_findings(findings)

    assert scores.categories["integrity"] == 0
    assert [item["applied"] for item in scores.deductions] == [30, 30, 30, 10, 0]
    assert [item["reason"] for item in scores.deductions][-2:] == ["category-floor", "category-floor"]
