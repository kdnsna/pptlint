from __future__ import annotations

from pathlib import Path

import pytest

from decklint.model import load_deck
from decklint.rules import audit_deck

from .pptx_factory import slide_xml, write_pptx


def rule_ids(path: Path, profile: str) -> set[str]:
    return {
        finding.rule_id
        for finding in audit_deck(load_deck(path), profile=profile)
    }


def test_ai_profile_accepts_large_top_native_text_as_title(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "semantic-title.pptx",
        slides=[
            slide_xml(
                title=None,
                body_size=3200,
                body_y=200_000,
                body_w=6_000_000,
            )
        ],
    )
    deck = load_deck(source)

    findings = audit_deck(deck, profile="ai-generated")

    assert "accessibility.missing-title" not in {
        finding.rule_id for finding in findings
    }
    assert deck.slides[0].title_source == "inferred"


@pytest.mark.parametrize(
    ("body_size", "body_y", "body_w"),
    [
        (1800, 200_000, 6_000_000),
        (3200, 3_000_000, 6_000_000),
        (3200, 200_000, 1_000_000),
    ],
)
def test_ai_profile_rejects_small_low_or_narrow_text(
    tmp_path: Path,
    body_size: int,
    body_y: int,
    body_w: int,
) -> None:
    source = write_pptx(
        tmp_path / "not-title.pptx",
        slides=[
            slide_xml(
                title=None,
                body_size=body_size,
                body_y=body_y,
                body_w=body_w,
            )
        ],
    )

    assert "accessibility.missing-title" in rule_ids(source, "ai-generated")


def test_baseline_still_requires_title_placeholder(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "baseline.pptx",
        slides=[
            slide_xml(
                title=None,
                body_size=3200,
                body_y=200_000,
                body_w=6_000_000,
            )
        ],
    )

    assert "accessibility.missing-title" in rule_ids(source, "baseline")


def test_ai_profile_rejects_raster_only_slide(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "raster-only.pptx",
        include_picture=True,
        slides=[slide_xml(title=None, body_text=None, include_picture=True)],
    )

    assert "accessibility.missing-title" in rule_ids(source, "ai-generated")
