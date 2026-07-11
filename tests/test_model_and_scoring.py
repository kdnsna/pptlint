from __future__ import annotations

from pathlib import Path

from decklint.model import load_deck
from decklint.schema import BBox, Finding
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
