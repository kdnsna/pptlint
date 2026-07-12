from __future__ import annotations

import json
from pathlib import Path

import pytest

from decklint.model import load_deck
from decklint.report import build_report, write_reports
from decklint.render import RenderError, render_deck
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
    assert first["schemaVersion"] == "pptlint-report/v2"
    assert first["file"]["name"] == "private-location.pptx"
    assert str(tmp_path) not in json.dumps(first)


def test_report_publishes_semantic_title_source(tmp_path: Path) -> None:
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
    rendering = render_deck(deck, source=source, renderer="wireframe")

    report = build_report(
        deck,
        findings,
        score_findings(findings),
        rendering,
        profile="ai-generated",
    )

    assert report["slides"][0]["titleSource"] == "inferred"


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
    assert 'data-slide="1"' in html
    assert "How the secondary score is calculated" in html
    assert "points" in html
    assert payload == report


def test_html_leads_with_delivery_readiness_and_priority_actions(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "broken.pptx", broken_relationship=True)
    deck = load_deck(source)
    findings = audit_deck(deck, profile="ai-generated")
    rendering = render_deck(deck, source=source, renderer="wireframe")
    report = build_report(deck, findings, score_findings(findings), rendering, profile="ai-generated")

    html_path, _ = write_reports(tmp_path / "pptlint-report", report)
    html = html_path.read_text(encoding="utf-8")

    assert "Delivery readiness" in html
    assert "Fix before sending" in html
    assert "Priority actions" in html
    assert "PowerPoint may repair the file" in html
    assert "Run PPTLint again" in html
    assert html.index("Delivery readiness") < html.index("Secondary score")
    assert "Checked locally" in html
    assert "Fix before sending" in html
    assert "Technical details" in html
    assert '<details class="technical-details">' in html
    assert "ai-generated profile" not in html.split("</section>", 1)[0]


def test_chinese_html_is_localized_and_actionable(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "broken.pptx", broken_relationship=True)
    deck = load_deck(source)
    findings = audit_deck(deck, profile="ai-generated")
    rendering = render_deck(deck, source=source, renderer="wireframe")
    report = build_report(
        deck,
        findings,
        score_findings(findings),
        rendering,
        profile="ai-generated",
        language="zh-CN",
    )

    html_path, _ = write_reports(tmp_path / "report", report)
    markup = html_path.read_text(encoding="utf-8")
    assert '<html lang="zh-CN">' in markup
    assert "PPTX 中有关系指向缺失的文件对象" in markup
    assert "影响整个文件的问题" in markup
    assert "技术证据" in markup
    assert "报告可能包含幻灯片预览" in markup
    assert 'data-filter="blocker"' in markup
    assert "Impact:" not in markup


def test_shareable_report_redacts_sensitive_content(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "confidential-client-name.pptx", broken_relationship=True)
    deck = load_deck(source)
    findings = audit_deck(deck, profile="ai-generated")
    rendering = render_deck(deck, source=source, renderer="wireframe")
    report = build_report(
        deck,
        findings,
        score_findings(findings),
        rendering,
        profile="ai-generated",
        language="zh-CN",
        report_mode="shareable",
    )

    html_path, json_path = write_reports(tmp_path / "shareable", report)
    markup = html_path.read_text(encoding="utf-8")
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    assert payload["reportMode"] == "shareable"
    assert payload["file"]["name"] == "presentation.pptx"
    assert all(slide["preview"] == "" and slide["title"] == "" for slide in payload["slides"])
    assert all(finding["evidence"].startswith("[redacted") for finding in payload["findings"])
    assert "data:image/png;base64," not in markup
    assert "confidential-client-name" not in markup
    assert "安全分享报告" in markup


def test_v2_report_exposes_editability_metrics(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "mixed.pptx",
        include_picture=True,
        slides=[slide_xml(include_picture=True, picture_alt="Background")],
    )
    deck = load_deck(source)
    findings = audit_deck(deck, profile="ai-generated")
    report = build_report(
        deck,
        findings,
        score_findings(findings),
        render_deck(deck, source=source, renderer="wireframe"),
        profile="ai-generated",
    )

    assert report["metrics"]["editability"]["nativeTextShapes"] == 2
    assert report["metrics"]["editability"]["pictures"] == 1
    assert 0 <= report["metrics"]["editability"]["nativeObjectRatio"] <= 1


def test_auto_renderer_degrades_to_wireframe_when_soffice_is_unavailable(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "deck.pptx")
    deck = load_deck(source)

    result = render_deck(deck, source=source, renderer="auto", soffice_path="/missing/soffice")

    assert result.used == "wireframe"
    assert result.status == "degraded"
    assert "LibreOffice" in result.detail


def test_output_prefix_with_dots_is_not_truncated(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "deck.pptx")
    deck = load_deck(source)
    findings = audit_deck(deck, profile="baseline")
    rendering = render_deck(deck, source=source, renderer="wireframe")
    report = build_report(deck, findings, score_findings(findings), rendering, profile="baseline")

    html_path, json_path = write_reports(tmp_path / "release.v0.1-report", report)

    assert html_path.name == "release.v0.1-report.html"
    assert json_path.name == "release.v0.1-report.json"


def test_explicit_libreoffice_mode_fails_when_executable_is_missing(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "deck.pptx")
    deck = load_deck(source)

    with pytest.raises(RenderError, match="LibreOffice"):
        render_deck(deck, source=source, renderer="libreoffice", soffice_path="/missing/soffice")
