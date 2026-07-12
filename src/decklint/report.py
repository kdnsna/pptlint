from __future__ import annotations

import html
import json
from pathlib import Path

from . import __version__
from .model import DeckModel
from .render import RenderResult
from .readiness import assess_readiness, classify_finding
from .schema import Finding, identified_findings
from .scoring import ScoreCard


SEVERITIES = ("critical", "high", "medium", "low")

DELIVERY_CHECKS = (
    ("file", {"integrity"}),
    ("presentation", {"readability", "accessibility", "consistency"}),
    ("editability", {"editability"}),
    ("privacy", {"privacy"}),
)

CHECK_COPY = {
    "en": {
        "file": ("Opens reliably", "No package-integrity issue was found."),
        "presentation": ("Readable in the room", "No current readability risk was found."),
        "editability": ("Can be handed over", "No flattened full-slide image was found."),
        "privacy": ("Safe to share", "No note, hidden page, comment, metadata, or external-link reminder was found."),
    },
    "zh-CN": {
        "file": ("文件能否正常打开", "没有发现文件结构问题。"),
        "presentation": ("现场是否看得清", "没有发现当前页面的可读性风险。"),
        "editability": ("别人能否继续修改", "没有发现整页图片式页面。"),
        "privacy": ("是否带出隐藏内容", "没有发现备注、隐藏页、批注、个人信息或外部链接提醒。"),
    },
}


def _delivery_checklist(findings: list[Finding], *, language: str) -> list[dict[str, object]]:
    copy = CHECK_COPY[language]
    result: list[dict[str, object]] = []
    for check_id, categories in DELIVERY_CHECKS:
        selected = [finding for finding in findings if finding.category in categories]
        classified = [classify_finding(finding, language=language) for finding in selected]
        if any(item["disposition"] == "blocker" for item in classified):
            status = "fix"
        elif selected:
            status = "review"
        else:
            status = "pass"
        label, clean_summary = copy[check_id]
        if selected:
            first = classified[0]
            summary = str(first["impact"])
        else:
            summary = clean_summary
        result.append(
            {
                "id": check_id,
                "status": status,
                "label": label,
                "summary": summary,
                "findingCount": len(selected),
            }
        )
    return result


def _issue_groups(findings: list[Finding], *, language: str) -> list[dict[str, object]]:
    grouped: dict[str, list[Finding]] = {}
    for finding in findings:
        grouped.setdefault(finding.rule_id, []).append(finding)
    result: list[dict[str, object]] = []
    for rule_id, items in grouped.items():
        detail = classify_finding(items[0], language=language)
        slides = sorted({item.slide_index for item in items if item.slide_index is not None})
        result.append(
            {
                "ruleId": rule_id,
                "category": items[0].category,
                "severity": max(
                    (item.severity for item in items),
                    key={"low": 1, "medium": 2, "high": 3, "critical": 4}.__getitem__,
                ),
                "confidence": "high" if any(item.confidence == "high" for item in items) else "low",
                "disposition": detail["disposition"],
                "impact": detail["impact"],
                "occurrenceCount": len(items),
                "affectedSlides": slides,
            }
        )
    rank = {"blocker": 3, "review": 2, "advisory": 1}
    return sorted(
        result,
        key=lambda item: (
            -rank[str(item["disposition"])],
            -int(item["occurrenceCount"]),
            str(item["ruleId"]),
        ),
    )


def build_report(
    deck: DeckModel,
    findings: list[Finding],
    scores: ScoreCard,
    rendering: RenderResult,
    *,
    profile: str,
    language: str = "en",
    scenario: str = "present",
) -> dict[str, object]:
    if language not in CHECK_COPY:
        raise ValueError(f"Unsupported report language: {language}")
    summary = {
        severity: sum(1 for finding in findings if finding.severity == severity) for severity in SEVERITIES
    }
    readiness = assess_readiness(findings, renderer_status=rendering.status, language=language)
    all_shapes = [shape for slide in deck.slides for shape in slide.shapes]
    native_text_shapes = sum(1 for shape in all_shapes if shape.text.strip())
    pictures = sum(1 for shape in all_shapes if shape.kind == "picture")
    graphic_frames = sum(1 for shape in all_shapes if shape.kind == "graphic-frame")
    content_objects = native_text_shapes + pictures + graphic_frames
    native_objects = native_text_shapes + graphic_frames
    flattened_slides = sum(
        1
        for slide in deck.slides
        if any(
            shape.kind == "picture"
            and (shape.bbox.w * shape.bbox.h) / max(1, deck.width * deck.height) >= 0.9
            for shape in slide.shapes
        )
        and sum(1 for shape in slide.shapes if shape.text.strip()) <= 2
    )
    return {
        "schemaVersion": "pptlint-report/v2",
        "toolVersion": __version__,
        "language": language,
        "profile": profile,
        "scenario": scenario,
        "file": {"name": deck.filename, "sha256": deck.sha256, "slides": len(deck.slides)},
        "renderer": rendering.metadata(),
        "scores": scores.to_dict(),
        "summary": summary,
        "readiness": {"status": readiness.status, "reasons": readiness.reasons},
        "priorityActions": readiness.priority_actions,
        "issueGroups": _issue_groups(findings, language=language),
        "deliveryChecklist": _delivery_checklist(findings, language=language),
        "metrics": {
            "editability": {
                "nativeTextShapes": native_text_shapes,
                "pictures": pictures,
                "graphicFrames": graphic_frames,
                "nativeObjectRatio": round(native_objects / max(1, content_objects), 4),
                "flattenedSlides": flattened_slides,
            }
        },
        "findings": [
            {
                **finding.to_dict(
                    finding_id=finding_id,
                    deck_width=deck.width,
                    deck_height=deck.height,
                ),
                **classify_finding(finding, language=language),
            }
            for finding_id, finding in identified_findings(findings)
        ],
        "slides": [
            {
                "index": slide.index,
                "title": slide.title,
                "titleSource": slide.title_source,
                "preview": rendering.previews[slide.index - 1]
                if slide.index <= len(rendering.previews)
                else "",
            }
            for slide in deck.slides
        ],
    }


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _action_location(action: dict[str, object], *, zh: bool) -> str:
    slides = action.get("affectedSlides")
    if isinstance(slides, list) and slides:
        shown = [str(value) for value in slides[:5]]
        suffix = "等" if zh and len(slides) > 5 else ("…" if len(slides) > 5 else "")
        return f"第 {'、'.join(shown)} 页{suffix}" if zh else f"Slides {', '.join(shown)}{suffix}"
    slide = action.get("slideIndex")
    if slide:
        return f"第 {slide} 页" if zh else f"Slide {slide}"
    return "整个文件" if zh else "Whole file"


def _render_groups(items: list[dict[str, object]]) -> list[list[dict[str, object]]]:
    grouped: dict[str, list[dict[str, object]]] = {}
    for item in items:
        grouped.setdefault(str(item["rule_id"]), []).append(item)
    return list(grouped.values())


def _render_html(report: dict[str, object]) -> str:
    file_info = report["file"]
    scores = report["scores"]
    findings = report["findings"]
    slides = report["slides"]
    renderer = report["renderer"]
    readiness = report["readiness"]
    priority_actions = report["priorityActions"]
    delivery_checklist = report["deliveryChecklist"]
    language = str(report.get("language", "en"))
    assert isinstance(file_info, dict) and isinstance(scores, dict) and isinstance(findings, list)
    assert isinstance(slides, list) and isinstance(renderer, dict)
    assert isinstance(readiness, dict) and isinstance(priority_actions, list)
    assert isinstance(delivery_checklist, list)
    zh = language == "zh-CN"
    categories = scores["categories"]
    assert isinstance(categories, dict)
    score_cards = "".join(
        f'<div class="score-card"><span>{_escape(name.title())}</span><strong>{_escape(value)}</strong></div>'
        for name, value in categories.items()
    )
    deductions = scores.get("deductions", [])
    deduction_map = {
        deduction["findingId"]: deduction for deduction in deductions if isinstance(deduction, dict)
    }
    policy = scores["policy"]
    weights = scores["weights"]
    assert isinstance(policy, dict) and isinstance(weights, dict)
    severity_deductions = policy["severityDeductions"]
    assert isinstance(severity_deductions, dict)
    scoring_policy = (
        '<details class="scoring-policy"><summary>How the secondary score is calculated</summary>'
        f"<p>Starts at {policy['startingScore']} per category. High-confidence deductions: "
        f"critical {severity_deductions['critical']}, high {severity_deductions['high']}, "
        f"medium {severity_deductions['medium']}, low {severity_deductions['low']} points; "
        f"per-rule cap {policy['perRuleCap']}. Weights: "
        + ", ".join(f"{name} {float(weight):.0%}" for name, weight in weights.items())
        + ". Suggestions that require human judgment and privacy reminders deduct 0 points.</p></details>"
    )
    status = str(readiness["status"])
    status_label = (
        {"ready": "可以发送", "review": "发送前再看一眼", "blocked": "先处理再发送"}
        if zh
        else {"ready": "Ready to send", "review": "Check before sending", "blocked": "Fix before sending"}
    )[status]
    disposition_labels = (
        {"blocker": "必须处理", "review": "需要确认", "advisory": "建议查看"}
        if zh
        else {"blocker": "Must fix", "review": "Check", "advisory": "Suggestion"}
    )
    action_items = "".join(
        "<li>"
        f"<span>{_escape(disposition_labels[str(action['disposition'])])} · "
        f"{_escape(_action_location(action, zh=zh))}</span>"
        f"<strong>{_escape(action['impact'])}</strong>"
        + "<ol>"
        + "".join(f"<li>{_escape(step)}</li>" for step in action["fixSteps"])
        + "</ol></li>"
        for action in priority_actions
        if isinstance(action, dict)
    )
    readiness_panel = (
        f'<section class="readiness readiness-{_escape(status)}">'
        f'<div><span class="eyebrow">{"发送前结论" if zh else "Delivery readiness"}</span>'
        f"<h2>{_escape(status_label)}</h2>"
        f'<p>{"先处理下面这些事。分数只用于比较同一份文件修改前后的变化。" if zh else "Start with these actions. Use the score only to compare this file before and after changes."}</p></div>'
        f'<div class="priority"><h3>{"先做这几件事" if zh else "Priority actions"}</h3><ul>{action_items or ("<li>当前没有必须处理的交付问题。</li>" if zh else "<li>No delivery action is required.</li>")}</ul></div>'
        "</section>"
    )
    checklist_labels = {"pass": "通过", "review": "确认", "fix": "处理"} if zh else {"pass": "Pass", "review": "Review", "fix": "Fix"}
    checklist_cards = "".join(
        f'<article class="check check-{_escape(item["status"])}"><span>{_escape(checklist_labels[str(item["status"])])}</span>'
        f'<h3>{_escape(item["label"])}</h3><p>{_escape(item["summary"])}</p><small>{_escape(item["findingCount"])} {"项提醒" if zh else "finding(s)"}</small></article>'
        for item in delivery_checklist
        if isinstance(item, dict)
    )
    checklist_panel = f'<section class="checklist"><header><span class="eyebrow">{"四项交付体检" if zh else "Four delivery checks"}</span><h2>{"发出去之前，先回答这四个问题" if zh else "What happens when someone else opens it?"}</h2></header><div>{checklist_cards}</div></section>'
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
            bbox = finding.get("bbox")
            if isinstance(bbox, dict) and float(bbox.get("w", 0)) > 0 and float(bbox.get("h", 0)) > 0:
                overlays += (
                    f'<i class="overlay severity-{_escape(finding["severity"])}" '
                    f'style="left:{float(bbox["x"]) * 100:.3f}%;top:{float(bbox["y"]) * 100:.3f}%;'
                    f'width:{float(bbox["w"]) * 100:.3f}%;height:{float(bbox["h"]) * 100:.3f}%"></i>'
                )
        rendered_groups = _render_groups(slide_findings)
        for group in rendered_groups:
            finding = group[0]
            deductions_for_group = [
                deduction_map.get(item["id"], {"applied": 0, "reason": "unscored"})
                for item in group
            ]
            applied = sum(int(item.get("applied", 0)) for item in deductions_for_group)
            deduction = deductions_for_group[0]
            points = (
                f"-{applied} points"
                if applied
                else f"0 points · {deduction['reason']}"
            )
            count_label = (
                f" · 本页 {len(group)} 处" if zh and len(group) > 1 else (f" · {len(group)} occurrences" if len(group) > 1 else "")
            )
            evidence = " | ".join(str(item["evidence"]) for item in group[:5])
            if len(group) > 5:
                evidence += f" | +{len(group) - 5} more"
            finding_items += (
                f'<li class="finding severity-{_escape(finding["severity"])}" '
                f'data-severity="{_escape(finding["severity"])}" data-category="{_escape(finding["category"])}">'
                f"<strong>{_escape(finding['message'])}{_escape(count_label)}</strong>"
                f'<p class="impact">Impact: {_escape(finding["impact"])}</p>'
                '<ol class="fix-steps">'
                + "".join(f"<li>{_escape(step)}</li>" for step in finding["fixSteps"])
                + '</ol><details class="technical-details"><summary>Technical details</summary>'
                f"<code>{_escape(finding['rule_id'])}</code><em>{_escape(points)}</em>"
                f"<p>{_escape(evidence)}</p></details></li>"
            )
        slide_cards.append(
            f'<article class="slide-card" data-slide="{index}"><header><span>Slide {index:02d}</span>'
            f"<h2>{_escape(slide.get('title') or 'Untitled slide')}</h2><b>{len(rendered_groups)} groups · {len(slide_findings)} occurrences</b></header>"
            f'<div class="slide-preview"><img alt="Slide {index} preview" src="{_escape(slide.get("preview", ""))}">{overlays}</div>'
            f"<ul>{finding_items or '<li class=clean>No item to check on this slide.</li>'}</ul></article>"
        )
    deck_findings = finding_groups.get(0, [])
    deck_items = ""
    for group in _render_groups(deck_findings):
        finding = group[0]
        deductions_for_group = [
            deduction_map.get(item["id"], {"applied": 0, "reason": "unscored"}) for item in group
        ]
        applied = sum(int(item.get("applied", 0)) for item in deductions_for_group)
        deduction = deductions_for_group[0]
        points = (
            f"-{applied} points" if applied else f"0 points · {deduction['reason']}"
        )
        count_label = (
            f" · {len(group)} 处" if zh and len(group) > 1 else (f" · {len(group)} occurrences" if len(group) > 1 else "")
        )
        deck_items += (
            f'<li class="finding severity-{_escape(finding["severity"])}">'
            f"<strong>{_escape(finding['message'])}{_escape(count_label)}</strong>"
            f'<p class="impact">Impact: {_escape(finding["impact"])}</p>'
            '<ol class="fix-steps">'
            + "".join(f"<li>{_escape(step)}</li>" for step in finding["fixSteps"])
            + '</ol><details class="technical-details"><summary>Technical details</summary>'
            f"<code>{_escape(finding['rule_id'])}</code><em>{_escape(points)}</em>"
            f"<p>{_escape(' | '.join(str(item['evidence']) for item in group[:5]))}</p></details></li>"
        )
    raw_json = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    safe_json = raw_json.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PPTLint report · {_escape(file_info["name"])}</title>
<style>
:root{{--ink:#172033;--paper:#f4f0e7;--panel:#fffdf8;--muted:#667085;--critical:#b42318;--high:#d92d20;--medium:#dc6803;--low:#175cd3}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.5 ui-sans-serif,system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1240px;margin:auto;padding:48px 24px 80px}}.hero{{display:grid;grid-template-columns:1fr auto;gap:28px;align-items:end;border-bottom:2px solid var(--ink);padding-bottom:28px}}
.eyebrow{{font:700 12px/1.2 ui-monospace,monospace;letter-spacing:.12em;text-transform:uppercase;color:#8a3d22}}h1{{font-size:clamp(34px,6vw,72px);line-height:.95;margin:10px 0 12px;max-width:13ch}}.hero p{{color:var(--muted);margin:0}}
.scores{{display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin:16px 0}}.score-card{{background:var(--panel);border:1px solid #d6d0c4;padding:16px}}.score-card span{{display:block;color:var(--muted);font-size:12px}}.score-card strong{{font-size:28px}}.secondary-score{{background:#ebe6dc;padding:14px 18px;margin:0 0 36px}}.secondary-score>summary{{font-weight:700;cursor:pointer}}.secondary-score>p{{color:var(--muted)}}
.readiness{{display:grid;grid-template-columns:minmax(260px,.7fr) minmax(360px,1.3fr);gap:28px;margin:28px 0;background:var(--panel);border-left:8px solid #175cd3;padding:24px}}.readiness-blocked{{border-color:var(--critical)}}.readiness-review{{border-color:var(--medium)}}.readiness-ready{{border-color:#18794e}}.readiness h2{{font-size:44px;margin:4px 0}}.readiness p{{color:var(--muted)}}.priority h3{{margin-top:0}}.priority>ul>li{{padding:10px 0;border-top:1px solid #ded8cd}}.priority span{{font:700 11px ui-monospace,monospace;text-transform:uppercase;color:var(--muted)}}.priority strong{{display:block}}.priority ol,.fix-steps{{margin:6px 0 0;padding-left:20px;color:var(--muted)}}.impact{{font-weight:700;color:var(--ink)!important}}
.checklist{{margin:28px 0}}.checklist>header h2{{font-size:clamp(26px,4vw,42px);margin:5px 0 18px}}.checklist>div{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.check{{background:var(--panel);border-top:5px solid #18794e;padding:18px}}.check-review{{border-color:var(--medium)}}.check-fix{{border-color:var(--critical)}}.check span{{font-weight:800;font-size:12px}}.check h3{{margin:7px 0}}.check p{{color:var(--muted);min-height:68px}}.check small{{color:var(--muted)}}
.notice{{padding:12px 16px;background:#fff3d6;border-left:4px solid var(--medium);margin-bottom:24px}}.slide-grid{{display:grid;gap:28px}}.slide-card{{display:grid;grid-template-columns:minmax(360px,1.1fr) minmax(300px,.9fr);gap:24px;background:var(--panel);border:1px solid #d6d0c4;padding:20px}}
.slide-card header{{grid-column:1/-1;display:flex;align-items:baseline;gap:14px;border-bottom:1px solid #ded8cd}}.slide-card header h2{{margin:0 0 10px;flex:1}}.slide-card header span,.slide-card header b{{font:700 11px ui-monospace,monospace;color:var(--muted)}}
.slide-preview{{position:relative;align-self:start;background:#ddd;box-shadow:0 12px 28px #17203320}}.slide-preview img{{width:100%;display:block}}.overlay{{position:absolute;border:3px solid var(--high);background:#d92d2015}}.overlay.severity-critical{{border-color:var(--critical)}}.overlay.severity-medium{{border-color:var(--medium)}}
ul{{list-style:none;margin:0;padding:0;display:grid;gap:10px}}.finding{{border-left:4px solid var(--low);padding:12px;background:#f7f8fa}}.finding.severity-critical{{border-color:var(--critical)}}.finding.severity-high{{border-color:var(--high)}}.finding.severity-medium{{border-color:var(--medium)}}.finding code{{display:inline-block;color:var(--muted);font-size:11px}}.finding em{{float:right;color:var(--muted);font:700 11px ui-monospace,monospace}}.finding strong{{display:block;margin:0 0 3px}}.finding p,.finding small{{margin:0;color:var(--muted)}}.technical-details{{margin-top:10px;color:var(--muted)}}.technical-details summary{{cursor:pointer;font-size:12px}}.technical-details p{{clear:both}}.deck-findings{{margin:0 0 32px}}.scoring-policy{{border-left:4px solid #8a3d22;padding:10px 14px;margin:12px 0 0}}.scoring-policy p{{margin:6px 0 0;color:var(--muted)}}
@media(max-width:800px){{.hero,.readiness{{grid-template-columns:1fr}}.checklist>div{{grid-template-columns:1fr 1fr}}.overall{{width:110px;height:110px}}.scores{{grid-template-columns:repeat(2,1fr)}}.slide-card{{grid-template-columns:1fr}}}}@media(max-width:480px){{.checklist>div{{grid-template-columns:1fr}}main{{padding-left:16px;padding-right:16px}}}}
</style></head><body><main>
<section class="hero"><div><span class="eyebrow">PPTLint · {"PPT 发送前体检" if zh else "PowerPoint delivery check"}</span><h1>{_escape(file_info["name"])}</h1><p>{("本地检查 · " + str(file_info["slides"]) + " 页 · 原文件未改动") if zh else ("Checked locally · " + str(file_info["slides"]) + (" slide" if int(file_info["slides"]) == 1 else " slides") + " · source file unchanged")}</p></div></section>
{readiness_panel}
{checklist_panel}
<details class="secondary-score"><summary>Secondary score: {_escape(scores["overall"])}/100</summary><p>Use this only to compare the same presentation before and after changes.</p><section class="scores">{score_cards}</section>{scoring_policy}<details class="technical-details"><summary>Run details</summary><p>{_escape(report["profile"])} profile · {_escape(renderer["used"])} renderer</p></details></details>
{f'<div class="notice">{_escape(renderer["detail"])}</div>' if renderer.get("detail") else ""}
{f'<section class="deck-findings"><h2>Items that affect the whole file</h2><ul>{deck_items}</ul></section>' if deck_items else ""}
<section class="slide-grid">{"".join(slide_cards)}</section>
<script id="decklint-data" type="application/json">{safe_json}</script>
</main></body></html>"""


def write_reports(output_stem: Path, report: dict[str, object]) -> tuple[Path, Path]:
    output_stem = Path(output_stem)
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    html_path = Path(f"{output_stem}.html")
    json_path = Path(f"{output_stem}.json")
    html_path.write_text(_render_html(report), encoding="utf-8")
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return html_path, json_path
