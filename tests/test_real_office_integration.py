from __future__ import annotations

import shutil
from pathlib import Path

import pytest
from pptx import Presentation

from decklint.model import load_deck
from decklint.render import render_deck


def create_real_pptx(path: Path) -> Path:
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[1])
    slide.shapes.title.text = "Real Office Fixture"
    slide.placeholders[1].text = "Native text rendered by LibreOffice"
    presentation.save(path)
    return path


def test_parser_reads_real_python_pptx_package(tmp_path: Path) -> None:
    source = create_real_pptx(tmp_path / "real.pptx")

    deck = load_deck(source)

    assert len(deck.slides) == 1
    assert deck.slides[0].title == "Real Office Fixture"
    assert sum(1 for shape in deck.slides[0].shapes if shape.text) == 2
    assert not deck.broken_relationships


@pytest.mark.skipif(not shutil.which("soffice"), reason="LibreOffice is not installed")
def test_libreoffice_renderer_produces_matching_real_preview(tmp_path: Path) -> None:
    source = create_real_pptx(tmp_path / "real.pptx")
    deck = load_deck(source)

    result = render_deck(deck, source=source, renderer="libreoffice")

    assert result.status == "ok", result.detail
    assert result.used == "libreoffice"
    assert len(result.previews) == len(deck.slides)

