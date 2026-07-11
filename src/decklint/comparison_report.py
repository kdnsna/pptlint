from __future__ import annotations

import html
import json
from pathlib import Path

from . import __version__
from .comparison import ComparisonError, compare_reports


def _object(container: dict[str, object], key: str) -> dict[str, object]:
    value = container.get(key)
    if not isinstance(value, dict):
        raise ComparisonError(f"Audit report field must be an object: {key}")
    return value


def _identity(report: dict[str, object]) -> dict[str, object]:
    file_info = _object(report, "file")
    renderer = _object(report, "renderer")
    return {
        "sourceSchema": str(report.get("schemaVersion", "")),
        "profile": str(report.get("profile", "")),
        "file": {
            "name": str(file_info.get("name", "")),
            "sha256": str(file_info.get("sha256", "")),
            "slides": int(file_info.get("slides", 0)),
        },
        "renderer": {
            "requested": str(renderer.get("requested", "")),
            "used": str(renderer.get("used", "")),
            "status": str(renderer.get("status", "")),
            "detail": str(renderer.get("detail", "")),
        },
    }


def _slide_map(report: dict[str, object]) -> dict[int, dict[str, object]]:
    slides = report.get("slides")
    if not isinstance(slides, list):
        raise ComparisonError("Audit report field must be an array: slides")
    mapped: dict[int, dict[str, object]] = {}
    for item in slides:
        if not isinstance(item, dict):
            raise ComparisonError("Audit report slides must contain objects")
        index = int(item.get("index", 0))
        if index <= 0 or index in mapped:
            raise ComparisonError("Audit report slide indices must be unique positive integers")
        mapped[index] = {
            "index": index,
            "title": str(item.get("title", "")),
            "titleSource": str(item.get("titleSource", "none")),
            "preview": str(item.get("preview", "")),
        }
    return mapped


def _pair_slides(
    before: dict[str, object],
    after: dict[str, object],
) -> list[dict[str, object]]:
    before_slides = _slide_map(before)
    after_slides = _slide_map(after)
    return [
        {
            "index": index,
            "before": before_slides.get(index),
            "after": after_slides.get(index),
        }
        for index in sorted(set(before_slides) | set(after_slides))
    ]


def _agent_summary(core: dict[str, object]) -> str:
    scores = _object(core, "scores")
    overall = _object(scores, "overall")
    gate = _object(core, "gate")
    status = "通过" if gate.get("passed") else "未通过"
    return (
        f"比较门禁{status}；总分从 {overall['before']} 变为 {overall['after']}"
        f"（变化 {int(overall['delta']):+d}）；已解决 {len(core['resolved'])} 项，"
        f"持续存在 {len(core['persistent'])} 项，新增 {len(core['new'])} 项。"
    )


def build_comparison_report(
    before: dict[str, object],
    after: dict[str, object],
    *,
    threshold: str,
) -> dict[str, object]:
    core = compare_reports(before, after, threshold=threshold)
    return {
        "schemaVersion": "decklint-comparison/v1",
        "toolVersion": __version__,
        "before": _identity(before),
        "after": _identity(after),
        "scores": core["scores"],
        "severity": core["severity"],
        "resolved": core["resolved"],
        "persistent": core["persistent"],
        "new": core["new"],
        "gate": core["gate"],
        "slides": _pair_slides(before, after),
        "agentSummary": _agent_summary(core),
    }


def _escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def _finding_list(title: str, items: list[dict[str, object]], css_class: str) -> str:
    rendered = "".join(
        "<li>"
        f"<code>{_escape(item.get('rule_id', ''))}</code>"
        f"<strong>第 {_escape(item.get('slide_index') or '—')} 页</strong>"
        f"<span>{_escape(item.get('message', ''))}</span>"
        "</li>"
        for item in items
    )
    if not rendered:
        rendered = "<li class=empty>无</li>"
    return (
        f'<section class="finding-group {css_class}"><h2>{_escape(title)}</h2><ul>{rendered}</ul></section>'
    )


def _render_comparison_html(report: dict[str, object]) -> str:
    before = _object(report, "before")
    after = _object(report, "after")
    before_file = _object(before, "file")
    after_file = _object(after, "file")
    scores = _object(report, "scores")
    overall = _object(scores, "overall")
    categories = _object(scores, "categories")
    gate = _object(report, "gate")
    category_names = {
        "integrity": "完整性",
        "readability": "可读性",
        "editability": "可编辑性",
        "consistency": "一致性",
        "accessibility": "无障碍",
    }
    score_cards = "".join(
        f"<article><span>{_escape(category_names.get(name, name))}</span>"
        f"<b>{_escape(change['before'])} → {_escape(change['after'])}</b>"
        f"<em>{int(change['delta']):+d}</em></article>"
        for name, change in categories.items()
        if isinstance(change, dict)
    )
    slide_cards = ""
    slides = report.get("slides")
    assert isinstance(slides, list)
    for pair in slides:
        assert isinstance(pair, dict)
        index = int(pair["index"])
        left = pair.get("before") if isinstance(pair.get("before"), dict) else {}
        right = pair.get("after") if isinstance(pair.get("after"), dict) else {}
        slide_cards += (
            f'<article class="slide-pair"><header><span>第 {index:02d} 页</span>'
            f"<h2>{_escape(right.get('title') or left.get('title') or '未命名页面')}</h2></header>"
            '<div class="preview"><figure><figcaption>改造前</figcaption>'
            f'<img alt="第 {index} 页改造前预览" src="{_escape(left.get("preview", ""))}"></figure>'
            "<figure><figcaption>改造后</figcaption>"
            f'<img alt="第 {index} 页改造后预览" src="{_escape(right.get("preview", ""))}"></figure></div></article>'
        )
    resolved = report.get("resolved")
    new = report.get("new")
    persistent = report.get("persistent")
    assert isinstance(resolved, list) and isinstance(new, list) and isinstance(persistent, list)
    persistent_after = [
        item["after"] for item in persistent if isinstance(item, dict) and isinstance(item.get("after"), dict)
    ]
    findings = (
        _finding_list("已解决", resolved, "resolved")
        + _finding_list("持续存在", persistent_after, "persistent")
        + _finding_list("新增问题", new, "new")
    )
    new_high_confidence = sum(
        1
        for item in new
        if item.get("confidence") == "high" and item.get("severity") in {"high", "critical"}
    )
    outcome_cards = (
        f"<article><span>已处理</span><b>{len(resolved)}</b><em>修改后不再报告</em></article>"
        f"<article><span>仍存在</span><b>{len(persistent)}</b><em>继续人工确认</em></article>"
        f"<article><span>新增提醒</span><b>{len(new)}</b><em>修改后首次报告</em></article>"
        f"<article><span>新增高把握问题</span><b>{new_high_confidence}</b><em>高或严重级别</em></article>"
    )
    raw_json = json.dumps(report, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    safe_json = raw_json.replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e")
    gate_label = "通过" if gate.get("passed") else "未通过"
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PPTLint 比较报告 · {_escape(after_file["name"])}</title>
<style>
:root{{--ink:#10233f;--paper:#f2f0eb;--panel:#fff;--muted:#667085;--good:#18794e;--warn:#b54708;--bad:#b42318}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--paper);color:var(--ink);font:15px/1.65 "PingFang SC","Microsoft YaHei",system-ui,sans-serif}}
main{{max-width:1180px;margin:auto;padding:52px 24px 88px}}header.hero{{border-bottom:3px solid var(--ink);padding-bottom:28px}}
.kicker{{font-size:12px;font-weight:700;letter-spacing:.14em;color:#8a3d22}}h1{{font-size:clamp(38px,7vw,76px);line-height:1.05;margin:10px 0}}.hero p{{color:var(--muted);margin:0}}
.overall{{display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:22px;background:var(--panel);padding:28px;margin:28px 0}}.overall strong{{font-size:54px}}.overall i{{font-size:34px;color:var(--good)}}.overall .after{{text-align:right}}.gate{{font-weight:700;color:{"var(--good)" if gate.get("passed") else "var(--bad)"}}}
.outcomes,.scores{{display:grid;grid-template-columns:repeat(4,1fr);gap:12px}}.outcomes{{margin:18px 0 30px}}.outcomes article,.scores article{{background:var(--panel);padding:16px;border-top:3px solid var(--ink)}}.outcomes span,.outcomes b,.outcomes em,.scores span,.scores b,.scores em{{display:block}}.outcomes b{{font-size:34px}}.outcomes em,.scores em{{color:var(--good);font-style:normal}}.boundary{{color:var(--muted);font-size:13px}}
.groups{{display:grid;grid-template-columns:repeat(3,1fr);gap:18px;margin:42px 0}}.finding-group{{background:var(--panel);padding:20px;border-top:5px solid var(--muted)}}.resolved{{border-color:var(--good)}}.new{{border-color:var(--bad)}}ul{{list-style:none;margin:0;padding:0}}li{{padding:9px 0;border-top:1px solid #e4e7ec}}li code,li strong,li span{{display:block}}li code{{font-size:11px;color:var(--muted)}}
.slide-grid{{display:grid;gap:24px}}.slide-pair{{background:var(--panel);padding:20px}}.slide-pair header{{display:flex;gap:18px;align-items:baseline}}.slide-pair h2{{margin:0 0 12px}}.preview{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}figure{{margin:0}}figcaption{{font-weight:700;margin-bottom:6px}}img{{display:block;width:100%;background:#e4e7ec;min-height:32px}}
@media(max-width:820px){{.outcomes,.scores,.groups{{grid-template-columns:1fr 1fr}}.preview{{grid-template-columns:1fr}}}}@media(max-width:560px){{.outcomes,.scores,.groups{{grid-template-columns:1fr}}}}
</style></head><body><main>
<header class="hero"><span class="kicker">PPTLINT · POWERPOINT 修改前后检查</span><h1>改造前后比较报告</h1><p>{_escape(before_file["name"])} → {_escape(after_file["name"])}</p></header>
<section class="overall"><div><span>改造前</span><strong>{_escape(overall["before"])}</strong></div><i>{int(overall["delta"]):+d}</i><div class="after"><span>改造后</span><strong>{_escape(overall["after"])}</strong></div></section>
<p class="gate">回归检查：{gate_label}</p><section class="outcomes">{outcome_cards}</section><section class="scores">{score_cards}</section>
<p class="boundary">分数只用于比较同一份 PPT 修改前后的规则检查结果，不代表审美满分，也不代表绝对没有风险。“已处理”表示对应提醒在修改后报告中不再出现。</p>
<section class="groups">{findings}</section><section class="slide-grid">{slide_cards}</section>
<script id="decklint-comparison-data" type="application/json">{safe_json}</script>
</main></body></html>"""


def write_comparison_reports(
    output_stem: Path,
    report: dict[str, object],
) -> tuple[Path, Path]:
    output_stem = Path(output_stem)
    output_stem.parent.mkdir(parents=True, exist_ok=True)
    html_path = Path(f"{output_stem}.html")
    json_path = Path(f"{output_stem}.json")
    html_path.write_text(_render_comparison_html(report), encoding="utf-8")
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return html_path, json_path
