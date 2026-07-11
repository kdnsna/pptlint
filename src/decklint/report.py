from __future__ import annotations

import html
import json
from pathlib import Path

from . import __version__
from .model import DeckModel
from .render import RenderResult
from .schema import Finding, identified_findings
from .scoring import ScoreCard


SEVERITIES = ("critical", "high", "medium", "low")


def build_report(
    deck: DeckModel,
    findings: list[Finding],
    scores: ScoreCard,
    rendering: RenderResult,
    *,
    profile: str,
) -> dict[str, object]:
    summary = {severity: sum(1 for finding in findings if finding.severity == severity) for severity in SEVERITIES}
    return {
        "schemaVersion": "decklint-report/v1",
        "toolVersion": __version__,
        "profile": profile,
        "file": {"name": deck.filename, "sha256": deck.sha256, "slides": len(deck.slides)},
        "renderer": rendering.metadata(),
        "scores": scores.to_dict(),
        "summary": summary,
        "findings": [
            finding.to_dict(
                finding_id=finding_id,
                deck_width=deck.width,
                deck_height=deck.height,
            )
            for finding_id, finding in identified_findings(findings)
        ],
        "slides": [
            {
                "index": slide.index,
                "title": slide.title,
                "titleSource": slide.title_source,
                "preview": rendering.previews[slide.index - 1] if slide.index <= len(rendering.previews) else "",
            }
            for slide in deck.slides
        ],
    }


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _render_html(report: dict[str, object]) -> str:
    file_info = report["file"]
    scores = report["scores"]
    findings = report["findings"]
    slides = report["slides"]
    renderer = report["renderer"]
    assert isinstance(file_info, dict) and isinstance(scores, dict) and isinstance(findings, list)
    assert isinstance(slides, list) and isinstance(renderer, dict)
    categories = scores["categories"]
    assert isinstance(categories, dict)
    score_cards = "".join(
        f'<div class="score-card"><span>{_escape(name.title())}</span><strong>{_escape(value)}</strong></div>'
        for name, value in categories.items()
    )
    deductions = scores.get("deductions", [])
    deduction_map = {
        deduction["findingId"]: deduction
        for deduction in deductions
        if isinstance(deduction, dict)
    }
    policy = scores["policy"]
    weights = scores["weights"]
    assert isinstance(policy, dict) and isinstance(weights, dict)
    severity_deductions = policy["severityDeductions"]
    assert isinstance(severity_deductions, dict)
    scoring_policy = (
        '<section class="scoring-policy"><h2>Scoring policy</h2>'
        f'<p>Starts at {policy["startingScore"]} per category. High-confidence deductions: '
        f'critical {severity_deductions["critical"]}, high {severity_deductions["high"]}, '
        f'medium {severity_deductions["medium"]}, low {severity_deductions["low"]} points; '
        f'per-rule cap {policy["perRuleCap"]}. Weights: '
        + ", ".join(f"{name} {float(weight):.0%}" for name, weight in weights.items())
        + ". Low-confidence and privacy findings deduct 0 points.</p></section>"
    )
    finding_groups: dict[int, list[dict[str, object]]] = {}
    for finding in findings:
        assert isinstance(finding, dict)
        finding_groups.setdefault(int(finding.get("slide_index") or 0), []).append(finding)
    slide_cards: list[str] = []
    for slide in slides:
        assert isinstance(slide, dict)
        index = int(slide["index"])
        slide_findings = finding_groups.get(index, [])
        overlays = ""
        finding_items = ""
        for finding in slide_findings:
            deduction = deduction_map.get(finding["id"], {"applied": 0, "reason": "unscored"})
            points = (
                f'-{deduction["applied"]} points'
                if deduction["applied"]
                else f'0 points · {deduction["reason"]}'
            )
            bbox = finding.get("bbox")
            if isinstance(bbox, dict) and float(bbox.get("w", 0)) > 0 and float(bbox.get("h", 0)) > 0:
                overlays += (
                    f'<i class="overlay severity-{_escape(finding["severity"])}" '
                    f'style="left:{float(bbox["x"])*100:.3f}%;top:{float(bbox["y"])*100:.3f}%;'
                    f'width:{float(bbox["w"])*100:.3f}%;height:{float(bbox["h"])*100:.3f}%"></i>'
                )
            finding_items += (
                f'<li class="finding severity-{_escape(finding["severity"])}" '
                f'data-severity="{_escape(finding["severity"])}" data-category="{_escape(finding["category"])}">'
                f'<code>{_escape(finding["rule_id"])}</code><em>{_escape(points)}</em>'
                f'<strong>{_escape(finding["message"])}</strong>'
                f'<p>{_escape(finding["evidence"])}</p><small>{_escape(finding["remediation"])}</small></li>'
            )
        slide_cards.append(
            f'<article class="slide-card" data-slide="{index}"><header><span>Slide {index:02d}</span>'
            f'<h2>{_escape(slide.get("title") or "Untitled slide")}</h2><b>{len(slide_findings)} findings</b></header>'
            f'<div class="slide-preview"><img alt="Slide {index} preview" src="{_escape(slide.get("preview", ""))}">{overlays}</div>'
            f'<ul>{finding_items or "<li class=clean>No slide-level findings.</li>"}</ul></article>'
        )
    deck_findings = finding_groups.get(0, [])
    deck_items = ""
    for finding in deck_findings:
        deduction = deduction_map.get(finding["id"], {"applied": 0, "reason": "unscored"})
        points = (
            f'-{deduction["applied"]} points'
            if deduction["applied"]
            else f'0 points · {deduction["reason"]}'
        )
        deck_items += (
            f'<li class="finding severity-{_escape(finding["severity"])}"><code>{_escape(finding["rule_id"])}</code>'
            f'<em>{_escape(points)}</em><strong>{_escape(finding["message"])}</strong>'
            f'<p>{_escape(finding["evidence"])}</p><small>{_escape(finding["remediation"])}</small></li>'
        )
    raw_json = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    safe_json = raw_json.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DeckLint report · {_escape(file_info["name"])}</title>
<style>
:root{{--ink:#172033;--paper:#f4f0e7;--panel:#fffdf8;--muted:#667085;--critical:#b42318;--high:#d92d20;--medium:#dc6803;--low:#175cd3}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1240px;margin:auto;padding:48px 24px 80px}}.hero{{display:grid;grid-template-columns:1fr auto;gap:28px;align-items:end;border-bottom:2px solid var(--ink);padding-bottom:28px}}
.eyebrow{{font:700 12px/1.2 ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:#8a3d22}}h1{{font-size:clamp(34px,6vw,72px);line-height:.95;margin:10px 0 12px;max-width:13ch}}.hero p{{color:var(--muted);margin:0}}
.overall{{width:150px;height:150px;border:12px solid #d8e6db;border-radius:50%;display:grid;place-items:center;background:var(--panel)}}.overall strong{{font-size:52px}}.overall span{{font-size:11px;text-transform:uppercase;color:var(--muted)}}
.scores{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:24px 0 48px}}.score-card{{background:var(--panel);border:1px solid #d6d0c4;padding:16px}}.score-card span{{display:block;color:var(--muted);font-size:12px}}.score-card strong{{font-size:28px}}
.notice{{padding:12px 16px;background:#fff3d6;border-left:4px solid var(--medium);margin-bottom:24px}}.slide-grid{{display:grid;gap:28px}}.slide-card{{display:grid;grid-template-columns:minmax(360px,1.1fr) minmax(300px,.9fr);gap:24px;background:var(--panel);border:1px solid #d6d0c4;padding:20px}}
.slide-card header{{grid-column:1/-1;display:flex;align-items:baseline;gap:14px;border-bottom:1px solid #ded8cd}}.slide-card header h2{{margin:0 0 10px;flex:1}}.slide-card header span,.slide-card header b{{font:700 11px ui-monospace,monospace;color:var(--muted)}}
.slide-preview{{position:relative;align-self:start;background:#ddd;box-shadow:0 12px 28px #17203320}}.slide-preview img{{width:100%;display:block}}.overlay{{position:absolute;border:3px solid var(--high);background:#d92d2015}}.overlay.severity-critical{{border-color:var(--critical)}}.overlay.severity-medium{{border-color:var(--medium)}}
ul{{list-style:none;margin:0;padding:0;display:grid;gap:10px}}.finding{{border-left:4px solid var(--low);padding:8px 12px;background:#f7f8fa}}.finding.severity-critical{{border-color:var(--critical)}}.finding.severity-high{{border-color:var(--high)}}.finding.severity-medium{{border-color:var(--medium)}}.finding code{{display:inline-block;color:var(--muted);font-size:11px}}.finding em{{float:right;color:var(--muted);font:700 11px ui-monospace,monospace}}.finding strong{{display:block;clear:both;margin:3px 0}}.finding p,.finding small{{margin:0;color:var(--muted)}}.deck-findings{{margin:0 0 32px}}.scoring-policy{{background:#ebe6dc;border-left:4px solid #8a3d22;padding:12px 18px;margin:-28px 0 36px}}.scoring-policy h2{{font-size:14px;margin:0 0 3px}}.scoring-policy p{{margin:0;color:var(--muted)}}
@media(max-width:800px){{.hero{{grid-template-columns:1fr}}.overall{{width:110px;height:110px}}.scores{{grid-template-columns:repeat(2,1fr)}}.slide-card{{grid-template-columns:1fr}}}}
</style></head><body><main>
<section class="hero"><div><span class="eyebrow">DeckLint · Lighthouse for PowerPoint</span><h1>{_escape(file_info["name"])}</h1><p>{_escape(file_info["slides"])} slides · {_escape(report["profile"])} profile · {_escape(renderer["used"])} renderer</p></div><div class="overall"><div><strong>{_escape(scores["overall"])}</strong><span>overall</span></div></div></section>
<section class="scores">{score_cards}</section>
{scoring_policy}
{f'<div class="notice">{_escape(renderer["detail"])}</div>' if renderer.get("detail") else ''}
{f'<section class="deck-findings"><h2>Deck-level findings</h2><ul>{deck_items}</ul></section>' if deck_items else ''}
<section class="slide-grid">{"".join(slide_cards)}</section>
<script id="decklint-data" type="application/json">{safe_json}</script>
</main></body></html>"""


def write_reports(output_stem: Path, report: dict[str, object]) -> tuple[Path, Path]:
    output_stem = Path(output_stem)
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    html_path = Path(f"{output_stem}.html")
    json_path = Path(f"{output_stem}.json")
    html_path.write_text(_render_html(report), encoding="utf-8")
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return html_path, json_path
