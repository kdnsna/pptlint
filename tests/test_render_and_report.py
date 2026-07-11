from __future__ import annotations

import json
from pathlib import Path

from decklint.model import load_deck
from decklint.report import build_report, write_reports
from decklint.render import render_deck
from decklint.rules import audit_deck
from decklint.scoring import score_findings

from .pptx_factory import slide_xml, write_pptx


def test_wireframe_renderer_returns_embedded_png(tmp_path: Path) -> None:
    deck = load_deck(write_pptx(tmp_path / "deck.pptx"))

    result = render_deck(deck, source=tmp_path / "deck.pptx", renderer="wireframe")

    assert result.used == "wireframe"
    assert result.status == "ok"
    assert len(result.previews) == 1
    assert result.previews[0].startswith("data:image/png;base64,")


def test_report_is_deterministic_and_redacts_absolute_path(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "private-location.pptx", slides=[slide_xml(body_size=900)])
    deck = load_deck(source)
    findings = audit_deck(deck, profile="baseline")
    rendering = render_deck(deck, source=source, renderer="wireframe")

    first = build_report(deck, findings, score_findings(findings), rendering, profile="baseline")
    second = build_report(deck, findings, score_findings(findings), rendering, profile="baseline")

    assert first == second
    assert first["schemaVersion"] == "decklint-report/v1"
    assert first["file"]["name"] == "private-location.pptx"
    assert str(tmp_path) not in json.dumps(first)


def test_html_report_is_self_contained_and_locates_findings(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "deck.pptx",
        include_picture=True,
        slides=[slide_xml(title=None, include_picture=True)],
    )
    deck = load_deck(source)
    findings = audit_deck(deck, profile="ai-generated")
    rendering = render_deck(deck, source=source, renderer="wireframe")
    report = build_report(deck, findings, score_findings(findings), rendering, profile="ai-generated")

    html_path, json_path = write_reports(tmp_path / "decklint-report", report)

    html = html_path.read_text(encoding="utf-8")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert "https://" not in html and "http://" not in html
    assert "data:image/png;base64," in html
    assert "accessibility.missing-alt-text" in html
    assert "data-slide=\"1\"" in html
    assert payload == report


def test_auto_renderer_degrades_to_wireframe_when_soffice_is_unavailable(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "deck.pptx")
    deck = load_deck(source)

    result = render_deck(deck, source=source, renderer="auto", soffice_path="/missing/soffice")

    assert result.used == "wireframe"
    assert result.status == "degraded"
    assert "LibreOffice" in result.detail

