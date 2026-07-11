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


def test_three_identical_slides_only_create_low_confidence_layout_warning(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "repeated.pptx", slides=[slide_xml(), slide_xml(), slide_xml()])

    findings = audit_deck(load_deck(source), profile="baseline")

    repeated = next(finding for finding in findings if finding.rule_id == "consistency.repeated-layout")
    assert repeated.confidence == "low"

