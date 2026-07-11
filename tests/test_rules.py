from __future__ import annotations

from pathlib import Path

from decklint.model import load_deck
from decklint.rules import audit_deck

from .pptx_factory import slide_xml, write_pptx


def rule_ids(path: Path, profile: str = "baseline") -> set[str]:
    return {finding.rule_id for finding in audit_deck(load_deck(path), profile=profile)}


def test_integrity_rule_reports_missing_relationship_target(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "broken.pptx", broken_relationship=True)

    findings = audit_deck(load_deck(source), profile="baseline")

    broken = next(finding for finding in findings if finding.rule_id == "integrity.broken-relationship")
    assert broken.severity == "critical"
    assert broken.confidence == "high"


def test_readability_rules_find_small_and_off_canvas_text(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "unreadable.pptx",
        slides=[slide_xml(body_size=900, body_x=11_500_000, body_w=2_000_000)],
    )

    ids = rule_ids(source)

    assert "readability.small-font" in ids
    assert "readability.off-canvas-text" in ids


def test_explicit_low_contrast_is_high_confidence(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "contrast.pptx",
        slides=[slide_xml(body_fill="FFFFFF", body_text_color="F8F8F8")],
    )

    findings = audit_deck(load_deck(source), profile="baseline")

    contrast = next(finding for finding in findings if finding.rule_id == "readability.low-contrast")
    assert contrast.confidence == "high"


def test_ai_profile_upgrades_flattened_slide_severity(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "flattened.pptx",
        include_picture=True,
        slides=[slide_xml(title=None, include_picture=True, picture_alt="visual")],
    )

    baseline = audit_deck(load_deck(source), profile="baseline")
    ai_generated = audit_deck(load_deck(source), profile="ai-generated")

    assert next(f for f in baseline if f.rule_id == "editability.full-slide-image").severity == "medium"
    assert next(f for f in ai_generated if f.rule_id == "editability.full-slide-image").severity == "high"


def test_accessibility_rules_find_missing_title_and_alt_text(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "inaccessible.pptx",
        include_picture=True,
        slides=[slide_xml(title=None, include_picture=True, picture_alt="")],
    )

    ids = rule_ids(source)

    assert "accessibility.missing-title" in ids
    assert "accessibility.missing-alt-text" in ids


def test_privacy_findings_do_not_depend_on_scoring_categories(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "private.pptx",
        creator="Private User",
        include_comments=True,
        slides=[slide_xml(hidden=True)],
    )

    ids = rule_ids(source)

    assert {"privacy.personal-metadata", "privacy.comments", "privacy.hidden-slide"} <= ids


def test_privacy_rules_find_notes_and_external_relationships(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "external.pptx",
        notes_text="Internal only",
        external_url="https://intranet.example.test/file",
    )

    ids = rule_ids(source)

    assert {"privacy.speaker-notes", "privacy.external-relationship"} <= ids


def test_empty_comments_container_does_not_claim_comments_exist(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "empty-comments.pptx", include_comments=True, empty_comments=True)

    assert "privacy.comments" not in rule_ids(source)


def test_three_identical_slides_only_create_low_confidence_layout_warning(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "repeated.pptx", slides=[slide_xml(), slide_xml(), slide_xml()])

    findings = audit_deck(load_deck(source), profile="baseline")

    repeated = next(finding for finding in findings if finding.rule_id == "consistency.repeated-layout")
    assert repeated.confidence == "low"


def test_missing_content_type_is_an_integrity_blocker(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "missing-content-type.pptx",
        include_picture=True,
        omit_picture_content_type=True,
    )

    finding = next(
        item
        for item in audit_deck(load_deck(source), profile="baseline")
        if item.rule_id == "integrity.missing-content-type"
    )

    assert finding.severity == "critical"
    assert finding.confidence == "high"


def test_blank_slide_requires_human_review(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "blank.pptx",
        slides=[slide_xml(title=None, body_text=None)],
    )

    assert "readability.blank-slide" in rule_ids(source)


def test_substantial_text_box_overlap_remains_advisory_until_visually_confirmed(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "overlap.pptx",
        slides=[slide_xml(second_body=True)],
    )

    finding = next(
        item
        for item in audit_deck(load_deck(source), profile="baseline")
        if item.rule_id == "readability.text-overlap"
    )

    assert finding.confidence == "low"
    assert finding.slide_index == 1
    assert finding.bbox is not None


def test_intentional_text_overlays_in_public_deck_do_not_block_delivery() -> None:
    source = Path(__file__).parents[1] / "examples" / "proof-loop" / "after.pptx"
    overlaps = [
        item
        for item in audit_deck(load_deck(source), profile="ai-generated")
        if item.rule_id == "readability.text-overlap"
    ]

    assert overlaps
    assert all(item.confidence == "low" for item in overlaps)


def test_explicit_clipping_and_portability_fonts_are_advisory(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "portable.pptx",
        slides=[
            slide_xml(
                body_font="Private Brand Sans",
                body_overflow="clip",
                body_text="A" * 700,
                body_w=1_000_000,
                body_h=300_000,
            )
        ],
    )

    findings = audit_deck(load_deck(source), profile="baseline")
    selected = {
        item.rule_id: item
        for item in findings
        if item.rule_id in {"readability.text-clipping-risk", "readability.font-portability-risk"}
    }

    assert selected.keys() == {"readability.text-clipping-risk", "readability.font-portability-risk"}
    assert all(item.confidence == "low" for item in selected.values())


def test_unusual_slide_aspect_ratio_is_advisory(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "wide.pptx", slide_width="20000000", slide_height="6858000")

    finding = next(
        item
        for item in audit_deck(load_deck(source), profile="baseline")
        if item.rule_id == "readability.unusual-aspect-ratio"
    )

    assert finding.confidence == "low"
