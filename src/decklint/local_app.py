from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import secrets
import shutil
import threading
import webbrowser
import zipfile
from dataclasses import dataclass
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from tempfile import mkdtemp
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, unquote, urlparse
from urllib.request import Request, urlopen

from . import __version__
from .cleanup import OPERATIONS, CleanupError, create_cleanup_copy, sha256_path
from .comparison_report import build_comparison_report, write_comparison_reports
from .model import DeckLoadError, load_deck
from .render import RenderError, render_deck
from .repair_plan import build_repair_plan, render_repair_brief, write_repair_plan
from .repair_verification import build_repair_verification, write_repair_verification
from .report import build_report, write_reports
from .rules import audit_deck
from .scoring import score_findings


MAX_UPLOAD_BYTES = 200 * 1024 * 1024
ULTIMATE_BRIDGE = "http://127.0.0.1:43188"
MAX_BRIDGE_SOURCE_BYTES = 40 * 1024 * 1024
ULTIMATE_VISUAL_RULES = {
    "readability.off-canvas-text",
    "readability.text-overlap",
    "readability.text-clipping-risk",
    "readability.small-font",
    "readability.low-contrast",
    "readability.dense-text",
    "consistency.font-outlier",
    "consistency.repeated-layout",
    "editability.full-slide-image",
    "policy.font-not-allowed",
    "policy.font-size-below-minimum",
    "policy.color-not-allowed",
}

# Existing decks must be edited through a native, package-preserving PowerPoint
# path.  The current Ultimate handoff can prepare a repair plan, but its
# full-deck import/export route is not safe enough to mutate a real customer
# file without changing masters, transparency, links, or untouched objects.
ULTIMATE_NATIVE_REPAIR_AVAILABLE = False


def _safe_filename(value: str) -> str:
    name = Path(value.replace("\\", "/")).name
    name = re.sub(r"[\x00-\x1f\x7f]", "", name).strip()
    return name[:180] or "presentation.pptx"


def _audit_file(path: Path, output: Path, *, scenario: str) -> dict[str, object]:
    deck = load_deck(path)
    findings = audit_deck(deck, profile="baseline", scenario=scenario)
    report = build_report(
        deck,
        findings,
        score_findings(findings),
        render_deck(deck, source=path, renderer="wireframe"),
        profile="baseline",
        language="zh-CN",
        scenario=scenario,
        report_mode="full",
    )
    write_reports(output, report)
    return report


def _mode_counts(plan: dict[str, object]) -> dict[str, int]:
    summary = plan.get("summary", {})
    counts = summary.get("byRepairMode", {}) if isinstance(summary, dict) else {}
    return {str(key): int(value) for key, value in counts.items()} if isinstance(counts, dict) else {}


def _verification_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bridge_json(path: str, *, payload: dict[str, object] | None = None) -> dict[str, object]:
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        f"{ULTIMATE_BRIDGE}{path}",
        data=data,
        method="GET" if data is None else "POST",
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=12) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        try:
            message = str(json.loads(detail).get("message") or detail)
        except json.JSONDecodeError:
            message = detail
        raise ValueError(f"Ultimate Bridge 拒绝了请求：{message}") from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ValueError(
            "未连接 Ultimate PPT Master。请先在 Ultimate 仓库运行 `npm run bridge -- --allow-launch`。"
        ) from exc
    if not isinstance(result, dict):
        raise ValueError("Ultimate Bridge 返回了无法识别的结果。")
    return result


def _ultimate_eligible(task: dict[str, object]) -> bool:
    location = task.get("location")
    return ULTIMATE_NATIVE_REPAIR_AVAILABLE and (
        task.get("ruleId") in ULTIMATE_VISUAL_RULES
        and task.get("repairMode") in {"guided-powerpoint", "agent-rebuild"}
        and "ultimate-ppt-master" in task.get("recommendedExecutors", [])
        and isinstance(location, dict)
        and isinstance(location.get("slideIndex"), int)
    )


def _ultimate_plan_eligible(task: dict[str, object]) -> bool:
    location = task.get("location")
    return (
        task.get("ruleId") in ULTIMATE_VISUAL_RULES
        and task.get("repairMode") in {"guided-powerpoint", "agent-rebuild"}
        and "ultimate-ppt-master" in task.get("recommendedExecutors", [])
        and isinstance(location, dict)
        and isinstance(location.get("slideIndex"), int)
    )


def _ultimate_tasks(record: DeckRecord, selected_ids: set[str]) -> list[dict[str, object]]:
    tasks = record.plan.get("tasks", [])
    if not isinstance(tasks, list):
        return []
    return [
        task
        for task in tasks
        if isinstance(task, dict)
        and str(task.get("taskId", "")) in selected_ids
        and _ultimate_eligible(task)
    ]


def _ultimate_handoff_payload(record: DeckRecord, tasks: list[dict[str, object]]) -> dict[str, object]:
    source_bytes = record.source.read_bytes()
    if len(source_bytes) > MAX_BRIDGE_SOURCE_BYTES:
        raise ValueError("文件超过 40 MB，无法安全直连 Bridge；请在 Ultimate 工作台中手动导入。")
    slide_indexes = sorted(
        {
            int(location["slideIndex"])
            for task in tasks
            if isinstance((location := task.get("location")), dict)
            and isinstance(location.get("slideIndex"), int)
        }
    )
    task_lines = []
    for task in tasks:
        location = task.get("location", {})
        slide = location.get("slideIndex") if isinstance(location, dict) else None
        steps = task.get("steps", [])
        task_lines.extend(
            [
                f"## 第 {slide} 页 · {task.get('consequence', '')}",
                f"- 目标：{task.get('target', '')}",
                *[f"- 步骤：{step}" for step in steps if isinstance(step, str)],
            ]
        )
    source_markdown = "\n".join(
        [
            f"# 优化 {record.source.name}",
            "",
            "这是 PPTLint 点名页面的局部优化任务，不是重新制作整套 PPT。",
            f"只处理页面：{', '.join(str(value) for value in slide_indexes)}。",
            "原文、数字、数据、结论、页数、页面顺序和未命中页面全部锁定。",
            "如果不改变内容或页数就无法安全改善，请保留原页并在交付说明中写明原因。",
            "",
            *task_lines,
        ]
    )
    selected_counts = {
        mode: sum(1 for task in tasks if task.get("repairMode") == mode)
        for mode in ("cleanup-copy", "guided-powerpoint", "agent-rebuild", "human-decision")
    }
    repair_plan_text = json.dumps(
        {
            **record.plan,
            "tasks": tasks,
            "summary": {"taskCount": len(tasks), "byRepairMode": selected_counts},
        },
        ensure_ascii=False,
        indent=2,
    )
    constraints = (
        "Only repair the PPTLint-selected slides. Preserve every character, number, datum, conclusion, "
        "slide count, slide order, and all unselected slides. Keep native editable PowerPoint objects. "
        "Write a new copy, run PPTLint proof, and stop rather than forcing a change that violates these locks."
    )
    return {
        "form": {
            "title": f"局部优化-{record.source.stem}",
            "audience": "原演示文稿受众",
            "coreMessage": "保留原文，只改善 PPTLint 命中页的可读性、层级、对齐与视觉完成度",
            "sourceNotes": source_markdown,
            "constraints": constraints,
            "slideCount": str(record.plan.get("source", {}).get("slides", "")),
            "outputMode": "pptx",
            "stylePreset": "reference-style-only",
            "language": "zh",
        },
        "sourceMarkdown": source_markdown,
        "agentPrompt": (
            "Use Ultimate PPT Master to repair an existing PPTX, not to create a new deck. "
            + constraints
            + " Read attachments/pptlint-repair-plan.json and use the source PPTX as style-only reference."
        ),
        "projectBrief": {
            "schemaVersion": "v5.2-brief-v1",
            "title": f"局部优化-{record.source.stem}",
            "outputMode": "pptx",
            "briefMode": "source-first",
            "expectationFit": {
                "riskLevel": "yellow",
                "score": 90,
                "readyForProduction": True,
                "missingSignals": [],
                "assumptions": [
                    "exact visible text is locked",
                    "slide count and order are locked",
                    "only PPTLint-selected slides may change",
                ],
            },
            "qualityGate": {
                "level": "formal-business",
                "acceptanceCriteria": [
                    "exact text and numbers preserved",
                    "only selected slides changed",
                    "native editable objects preserved",
                    "no new high-confidence PPTLint finding",
                    "rendered before-after review completed",
                ],
                "reviewCommands": [
                    "python3 scripts/audit_formal_delivery.py <project_path>",
                    "python3 scripts/audit_design_completion.py <project_path>",
                    "uvx pptlint proof <before.pptx> <after.pptx> --scenario present",
                ],
            },
        },
        "attachments": [
            {
                "id": "source-pptx",
                "name": record.source.name,
                "type": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
                "size": len(source_bytes),
                "dataBase64": base64.b64encode(source_bytes).decode("ascii"),
            },
            {
                "id": "pptlint-repair-plan",
                "name": "pptlint-repair-plan.json",
                "type": "application/json",
                "size": len(repair_plan_text.encode("utf-8")),
                "text": repair_plan_text,
            },
        ],
    }


@dataclass
class DeckRecord:
    source: Path
    scenario: str
    report: dict[str, object]
    report_stem: Path
    plan: dict[str, object]
    plan_path: Path
    brief_path: Path


class AppSession:
    def __init__(self) -> None:
        self.root = Path(mkdtemp(prefix="pptlint-app-")).resolve()
        os.chmod(self.root, 0o700)
        self.uploads = self.root / "uploads"
        self.artifacts = self.root / "artifacts"
        self.uploads.mkdir(mode=0o700)
        self.artifacts.mkdir(mode=0o700)
        self.token = secrets.token_urlsafe(32)
        self.decks: dict[str, DeckRecord] = {}
        self.downloads: dict[str, Path] = {}
        self.closed = False

    def register(self, path: Path) -> str:
        key = secrets.token_urlsafe(12)
        self.downloads[key] = path.resolve()
        return key

    def download_url(self, path: Path) -> str:
        key = self.register(path)
        return f"/download/{key}/{quote(path.name)}?token={quote(self.token)}"

    def close(self) -> None:
        if not self.closed:
            shutil.rmtree(self.root, ignore_errors=True)
            self.closed = True


def _download_item(session: AppSession, path: Path, label: str) -> dict[str, str]:
    return {"label": label, "name": path.name, "url": session.download_url(path)}


def _report_response(session: AppSession, deck_id: str, record: DeckRecord) -> dict[str, object]:
    report = record.report
    readiness = report.get("readiness", {})
    file_info = report.get("file", {})
    tasks = record.plan.get("tasks", [])
    safe_tasks = []
    cleanup_operations: set[str] = set()
    operation_by_rule = {
        "privacy.personal-metadata": "clear-personal-metadata",
        "privacy.comments": "remove-comments",
        "privacy.speaker-notes": "remove-speaker-notes",
        "policy.notes-forbidden": "remove-speaker-notes",
    }
    if isinstance(tasks, list):
        for task in tasks:
            if not isinstance(task, dict):
                continue
            location = task.get("location", {})
            safe_tasks.append(
                {
                    "taskId": task.get("taskId"),
                    "ruleId": task.get("ruleId"),
                    "slideIndex": location.get("slideIndex") if isinstance(location, dict) else None,
                    "consequence": task.get("consequence"),
                    "target": task.get("target"),
                    "repairMode": task.get("repairMode"),
                    "risk": task.get("risk"),
                    "steps": task.get("steps", []),
                    "ultimateEligible": _ultimate_eligible(task),
                    "ultimatePlanEligible": _ultimate_plan_eligible(task),
                }
            )
            operation = operation_by_rule.get(str(task.get("ruleId", "")))
            if task.get("repairMode") == "cleanup-copy" and operation:
                cleanup_operations.add(operation)
    brief = record.brief_path.read_text(encoding="utf-8")
    return {
        "deckId": deck_id,
        "file": file_info,
        "readiness": readiness,
        "score": report.get("scores", {}).get("overall") if isinstance(report.get("scores"), dict) else None,
        "summary": report.get("summary", {}),
        "modeCounts": _mode_counts(record.plan),
        "tasks": safe_tasks,
        "cleanupOperations": [operation for operation in OPERATIONS if operation in cleanup_operations],
        "agentBrief": brief,
        "downloads": [
            _download_item(session, Path(f"{record.report_stem}.html"), "中文检查报告"),
            _download_item(session, Path(f"{record.report_stem}.json"), "机器可读报告"),
            _download_item(session, record.plan_path, "完整修复计划"),
            _download_item(session, record.brief_path, "Agent 修复简报"),
        ],
    }


def _html(token: str) -> str:
    template = r'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PPTLint 本地交付台</title>
<style>
:root{--ink:#0a1628;--muted:#657083;--paper:#f4f1eb;--panel:#fff;--accent:#e85d2c;--green:#0d8b63;--amber:#b66a09;--red:#c3382b;--line:#dfe2e7}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.65 "PingFang SC","Microsoft YaHei",system-ui,sans-serif}button,input,select{font:inherit}.shell{width:min(1240px,calc(100% - 32px));margin:auto}.nav{display:flex;justify-content:space-between;align-items:center;padding:20px 0}.brand{font:900 17px/1 ui-monospace,monospace;letter-spacing:.14em}.privacy{color:var(--muted);font-size:13px}.hero{display:grid;grid-template-columns:1.2fr .8fr;gap:28px;padding:52px 0 36px}.eyebrow{font:800 12px/1 ui-monospace,monospace;letter-spacing:.13em;color:var(--accent)}h1{font-size:clamp(42px,6.2vw,72px);line-height:.98;letter-spacing:-.055em;margin:14px 0 22px}.lead{font-size:18px;color:var(--muted);max-width:720px}.trust{align-self:end;background:var(--ink);color:white;border-radius:24px;padding:26px;box-shadow:0 24px 70px #0a16282a}.trust strong{display:block;font-size:28px}.trust span{display:block;color:#c6cfdd;margin-top:8px}.steps{display:grid;grid-template-columns:minmax(280px,.9fr) minmax(390px,1.35fr) minmax(280px,.9fr);gap:16px;margin:18px 0 70px;align-items:start}.card{min-width:0;background:var(--panel);border:1px solid var(--line);border-radius:20px;padding:24px;box-shadow:0 14px 40px #0a16280c}.card h2{font-size:24px;margin:8px 0}.card>p{color:var(--muted)}.num{font:800 12px ui-monospace,monospace;color:var(--accent)}.drop{display:flex;flex-direction:column;align-items:center;justify-content:center;width:100%;min-height:136px;border:2px dashed #aeb6c2;border-radius:16px;padding:28px 18px;text-align:center;background:#fafbfc;color:var(--ink);cursor:pointer;transition:.2s}.drop.drag{border-color:var(--accent);background:#fff4ee}.drop input{display:none}.drop b{display:block;width:100%;color:var(--ink);font-size:18px}.drop span{display:block;width:100%;color:var(--muted);font-size:13px}.select{display:block;width:100%;border:1px solid #ccd2da;border-radius:10px;padding:10px 12px;margin:14px 0;background:white}.result{display:none;margin-top:22px}.result.show{display:block}.status{display:flex;gap:12px;align-items:center;padding:16px;border-radius:14px;background:#edf7f3}.status.blocked{background:#fff0ed}.status.review{background:#fff6e8}.status b{font-size:20px}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0}.metric{background:#f4f6f8;padding:12px;border-radius:10px}.metric strong{display:block;font-size:22px}.tasks{max-height:580px;overflow:auto;border-top:1px solid #e2e5e9}.task{border-bottom:1px solid #e2e5e9}.task summary{display:grid;grid-template-columns:auto 1fr;gap:10px;padding:14px 2px;cursor:pointer;list-style:none}.task summary::-webkit-details-marker{display:none}.task summary:before{content:"+";display:grid;place-items:center;width:22px;height:22px;border-radius:50%;background:#eef1f5;font-weight:900}.task[open] summary:before{content:"−"}.task-title b{display:block}.task-title small{color:var(--muted)}.task-body{padding:0 2px 16px 32px}.task-body p{margin:4px 0 8px}.task-body ol{margin:6px 0;padding-left:20px;color:var(--muted)}.task-route{display:flex;align-items:flex-start;gap:8px;background:#f5f6f8;border-radius:10px;padding:9px 10px;margin-top:10px}.task-route input{margin-top:5px}.pill{display:inline-block;border:1px solid #cdd3db;border-radius:99px;padding:2px 8px;font-size:11px;margin:5px 4px 0 0}.choice{border:1px solid var(--line);border-radius:14px;padding:14px;margin:12px 0}.choice strong{display:block;font-size:17px}.choice p{margin:4px 0;color:var(--muted)}.choice.recommended{border-color:#9fb7ff;background:#f5f7ff}.choice-tag{font:800 10px ui-monospace,monospace;color:#3557c8}.actions{display:flex;flex-wrap:wrap;gap:9px;margin-top:12px}.btn{border:0;border-radius:10px;padding:11px 14px;font-weight:750;cursor:pointer;background:var(--ink);color:white;text-decoration:none}.btn.accent{background:var(--accent)}.btn.alt{background:white;color:var(--ink);border:1px solid #b8c0cb}.btn:disabled{opacity:.38;cursor:not-allowed}.checks{display:grid;gap:8px;margin:10px 0}.checks label{display:flex;gap:8px;align-items:center;background:#f5f6f8;padding:9px 10px;border-radius:9px}.subhead{margin:20px 0 6px;font-size:13px}.message{margin-top:12px;padding:12px;border-left:4px solid var(--green);background:#edf7f3;display:none;overflow-wrap:anywhere}.message.show{display:block}.message.error{border-color:var(--red);background:#fff0ed}.message code{display:block;margin-top:8px;padding:8px;background:white;white-space:pre-wrap}.downloads{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.downloads a{color:#1457a6}.platform-note{font-size:12px;color:var(--muted);margin-top:10px}.footer{padding:24px 0 54px;color:var(--muted);font-size:13px}.spinner{opacity:.6;pointer-events:none}@media(max-width:1000px){.steps{grid-template-columns:1fr 1fr}.steps .card:nth-child(2){grid-column:span 1}.steps .card:nth-child(3){grid-column:1/-1}}@media(max-width:760px){.hero,.steps{grid-template-columns:1fr}.steps .card:nth-child(3){grid-column:auto}.trust{align-self:auto}}@media(max-width:430px){.shell{width:min(100% - 22px,1240px)}.nav{align-items:flex-start;gap:10px}.brand{font-size:14px;white-space:nowrap}.privacy{max-width:160px;text-align:right}.hero{padding-top:28px}h1{font-size:40px}.card{padding:18px}.metrics{grid-template-columns:1fr}.actions{display:grid}.btn{text-align:center;width:100%}}
</style></head><body><div class="shell">
<nav class="nav"><div class="brand">PPTLINT / LOCAL</div><div class="privacy">只运行在本机 · 不上传 · 不调用模型</div></nav>
<header class="hero"><div><span class="eyebrow">POWERPOINT 发出前的最后一关</span><h1>把难改的页点出来，<br>再把它稳妥改好。</h1><p class="lead">先看哪里影响阅读和交付，再按页面给出的 PowerPoint 步骤处理。现阶段不再用整份重导出的方式自动改真实 PPT，避免母版、透明背景、组合对象和链接被破坏。</p></div><aside class="trust"><strong>不破坏，比自动更重要</strong><span>源文件永远不动。PPTLint 只自动执行不会重排画面的安全清理；视觉修改先给出明确人工步骤。</span></aside></header>
<main class="steps">
<section class="card" id="check-card"><span class="num">01 · 找到难改的页</span><h2>拖入要发的 PPT</h2><select class="select" id="scenario" aria-label="选择 PPT 使用场景"><option value="present">会议室汇报</option><option value="screen">电脑屏幕阅读</option><option value="document">文档型 PPT</option></select><label class="drop" id="check-drop" role="button" tabindex="0"><input type="file" accept=".pptx"><b>点击或拖入 .pptx</b><span>本地检查，文件不会离开这台电脑</span></label><div class="result" id="check-result" aria-live="polite"></div></section>
<section class="card"><span class="num">02 · 选择怎么改</span><h2>优先在 PowerPoint 里改</h2><div class="choice recommended"><span class="choice-tag">推荐 · 最稳妥</span><strong>A · 按命中页人工调整</strong><p>展开左侧每项问题，按页码、目标和具体菜单步骤处理，不重建整份文件。</p><div class="platform-note">步骤以 PowerPoint 桌面版为主；WPS 中可在“开始 / 设计 / 图片工具”的同名命令中完成。</div></div><div class="choice"><strong>B · 复制给助手分析</strong><p>可复制完整任务，让助手进一步给建议；在原生保真编辑链路完成前，不再承诺一键生成修改版。</p><div class="actions"><button class="btn accent" id="ultimate-btn" disabled>自动改文件暂不可用</button><button class="btn alt" id="copy-btn" disabled>复制完整任务</button></div></div><h3 class="subhead">可安全清理的隐私内容</h3><div class="checks" id="cleanup-checks"><span style="color:var(--muted)">先完成第一步。</span></div><button class="btn alt" id="cleanup-btn" disabled>生成清理副本</button><div class="message" id="action-message" aria-live="polite"></div></section>
<section class="card"><span class="num">03 · 规则复检 + 画面确认</span><h2>先目检，再拖入副本</h2><p>先在 PowerPoint/WPS 中查看每个修改页；PPTLint 复检只负责规则变化，不能代替画面验收。</p><div class="checks"><label><input type="checkbox" id="visual-confirm">我已确认修改页没有黑底、缺字、丢链接、错位或异常换行</label></div><label class="drop" id="verify-drop" role="button" tabindex="0"><input type="file" accept=".pptx"><b>点击或拖入修改后副本</b><span>规则复检与人工画面确认都完成后，才生成 Verified 凭证</span></label><div class="result" id="verify-result" aria-live="polite"></div></section>
</main><footer class="footer">PPTLint __VERSION__ · 会话关闭后自动删除临时文件 · 无统计 · 无遥测</footer></div>
<script>
const TOKEN=__TOKEN__;const state={deck:null};
const opLabels={'clear-personal-metadata':'清除作者和最后编辑者信息','remove-comments':'移除批注','remove-speaker-notes':'移除讲者备注'};
const modeLabels={'cleanup-copy':'PPTLint 可清理副本','guided-powerpoint':'适合自己调整','agent-rebuild':'建议先人工调整','human-decision':'需要你先确认'};
function auth(){return{'X-PPTLint-Token':TOKEN}}
function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}
function downloads(items){return '<div class="downloads">'+(items||[]).map(x=>`<a href="${esc(x.url)}">${esc(x.label)}</a>`).join('')+'</div>'}
function wireDrop(id,fn){const box=document.getElementById(id),input=box.querySelector('input');box.addEventListener('click',()=>input.click());box.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();input.click()}});input.addEventListener('change',()=>input.files[0]&&fn(input.files[0]));['dragenter','dragover'].forEach(e=>box.addEventListener(e,x=>{x.preventDefault();box.classList.add('drag')}));['dragleave','drop'].forEach(e=>box.addEventListener(e,x=>{x.preventDefault();box.classList.remove('drag')}));box.addEventListener('drop',e=>e.dataTransfer.files[0]&&fn(e.dataTransfer.files[0]))}
async function api(path,opt={}){opt.headers={...(opt.headers||{}),...auth()};const r=await fetch(path,opt);const data=await r.json();if(!r.ok)throw new Error(data.error||'运行失败');return data}
async function check(file){const card=document.getElementById('check-card');card.classList.add('spinner');try{const scenario=document.getElementById('scenario').value;const data=await api(`/api/check?filename=${encodeURIComponent(file.name)}&scenario=${scenario}`,{method:'POST',headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.presentationml.presentation'},body:file});state.deck=data;renderCheck(data);renderActions(data)}catch(e){showError('check-result',e.message)}finally{card.classList.remove('spinner')}}
function taskMarkup(t){const loc=t.slideIndex?`第 ${t.slideIndex} 页`:'整个文件',plan=t.ultimatePlanEligible;return `<details class="task"><summary><span></span><span class="task-title"><b>${loc} · ${esc(t.consequence)}</b><small>${esc(modeLabels[t.repairMode]||t.repairMode)} · 风险 ${esc(t.risk)}</small></span></summary><div class="task-body"><b>希望改成什么样</b><p>${esc(t.target)}</p><b>自己在 PowerPoint 里这样改</b><ol>${(t.steps||[]).map(step=>`<li>${esc(step)}</li>`).join('')}</ol><div class="task-route"><span><b>${plan?'可复制给助手继续分析':'这一项需要人工确认或由 PPTLint 清理'}</b><small>${plan?'助手只能给定向建议；当前不会自动重导出整份 PPT。':'不会被自动处理。'}</small></span></div></div></details>`}
function renderCheck(d){const r=d.readiness||{},cls=r.status||'review',label={ready:'可以交付',review:'发送前再看一眼',blocked:'先处理再发送'}[cls]||'需要检查',tasks=d.tasks||[],guidedPages=new Set(tasks.filter(t=>t.ultimatePlanEligible).map(t=>t.slideIndex)).size;document.getElementById('check-result').innerHTML=`<div class="status ${cls}"><div><b>${label}</b><div>${tasks.length} 项处理任务，逐项展开即可照着改</div></div></div><div class="metrics"><div class="metric"><span>辅助分数</span><strong>${d.score}</strong></div><div class="metric"><span>有人工步骤的页</span><strong>${guidedPages}</strong></div><div class="metric"><span>需你判断</span><strong>${d.modeCounts['human-decision']||0}</strong></div></div><div class="tasks">${tasks.map(taskMarkup).join('')}</div>${downloads(d.downloads)}`;document.getElementById('check-result').classList.add('show');updateUltimateCount()}
function renderActions(d){const box=document.getElementById('cleanup-checks'),ops=d.cleanupOperations||[];box.innerHTML=ops.length?ops.map(op=>`<label><input type="checkbox" value="${op}">${opLabels[op]}</label>`).join(''):'<span style="color:var(--muted)">没有可由 PPTLint 自动清理的项目。</span>';document.getElementById('cleanup-btn').disabled=!ops.length;document.getElementById('copy-btn').disabled=false;updateUltimateCount()}
function selectedUltimateTasks(){return [...document.querySelectorAll('.ultimate-task:checked')].map(item=>item.value)}
function updateUltimateCount(){const button=document.getElementById('ultimate-btn');button.disabled=true;button.textContent='自动改文件暂不可用'}
function showMessage(text,html=false,error=false){const el=document.getElementById('action-message');el[html?'innerHTML':'textContent']=text;el.classList.toggle('error',error);el.classList.add('show')}
async function cleanup(){const ops=[...document.querySelectorAll('#cleanup-checks input:checked')].map(x=>x.value);if(!ops.length){showMessage('请先勾选至少一项。',false,true);return}try{const data=await api('/api/fix',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({deckId:state.deck.deckId,operations:ops})});showMessage(`${data.passed?'清理并复检完成':'副本已生成，但仍有需处理的问题。'}${downloads(data.downloads)}`,true)}catch(e){showMessage(e.message,false,true)}}
async function copyBrief(){await navigator.clipboard.writeText(state.deck.agentBrief);document.getElementById('copy-btn').textContent='已复制完整任务'}
async function optimize(){const button=document.getElementById('ultimate-btn'),taskIds=selectedUltimateTasks();if(!taskIds.length)return;button.disabled=true;button.textContent='正在准备本地优化…';try{const data=await api('/api/ultimate-handoff',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({deckId:state.deck.deckId,taskIds})});if(!data.launched&&data.command){try{await navigator.clipboard.writeText(data.command)}catch{}}showMessage(data.launched?`已启动 Codex，只处理 ${data.taskCount} 项命中页。项目保存在：<code>${esc(data.projectPath)}</code>`:`Ultimate 项目已准备好，启动命令已复制。<code>${esc(data.command||'')}</code>`,true)}catch(e){showMessage(e.message,false,true)}finally{updateUltimateCount()}}
async function verify(file){if(!state.deck){showError('verify-result','请先检查原 PPT。');return}const confirmed=document.getElementById('visual-confirm').checked;if(!confirmed){showError('verify-result','请先在 PowerPoint/WPS 中目检修改页，并勾选画面确认。');return}try{const d=await api(`/api/verify?filename=${encodeURIComponent(file.name)}&deckId=${encodeURIComponent(state.deck.deckId)}&visualConfirmed=true`,{method:'POST',headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.presentationml.presentation'},body:file});const label=d.passed?'复检通过 · PPTLint Verified':d.automatedPassed?'规则已通过，仍缺画面确认':'复检未通过';document.getElementById('verify-result').innerHTML=`<div class="status ${d.passed?'':'review'}"><div><b>${label}</b><div>已完成 ${d.completed} · 仍存在 ${d.remaining} · 无法确认 ${d.unable} · 回归 ${d.regressions}</div></div></div>${downloads(d.downloads)}`;document.getElementById('verify-result').classList.add('show')}catch(e){showError('verify-result',e.message)}}
function showError(id,msg){const el=document.getElementById(id);el.innerHTML=`<div class="status blocked"><b>${esc(msg)}</b></div>`;el.classList.add('show')}
wireDrop('check-drop',check);wireDrop('verify-drop',verify);document.getElementById('cleanup-btn').addEventListener('click',cleanup);document.getElementById('copy-btn').addEventListener('click',copyBrief);document.getElementById('ultimate-btn').addEventListener('click',optimize);
</script></body></html>'''
    return template.replace("__TOKEN__", json.dumps(token)).replace("__VERSION__", __version__)


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, address: tuple[str, int], session: AppSession):
        self.session = session
        super().__init__(address, _Handler)


class _Handler(BaseHTTPRequestHandler):
    server: _Server

    def log_message(self, format: str, *args: object) -> None:
        return

    def _headers(self, status: int, content_type: str, length: int) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(length))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", "default-src 'self'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; font-src 'none'; frame-ancestors 'none'")
        self.end_headers()

    def _json(self, payload: dict[str, object], status: int = 200) -> None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(data))
        self.wfile.write(data)

    def _authorized(self, *, query_allowed: bool = False) -> bool:
        parsed = urlparse(self.path)
        query_token = parse_qs(parsed.query).get("token", [""])[0] if query_allowed else ""
        header_token = self.headers.get("X-PPTLint-Token", "")
        token = query_token or header_token
        if not secrets.compare_digest(token, self.server.session.token):
            self._json({"error": "会话令牌无效。"}, HTTPStatus.FORBIDDEN)
            return False
        origin = self.headers.get("Origin")
        if origin:
            port = self.server.server_address[1]
            if origin not in {f"http://127.0.0.1:{port}", f"http://localhost:{port}"}:
                self._json({"error": "不允许的请求来源。"}, HTTPStatus.FORBIDDEN)
                return False
        return True

    def _body(self) -> bytes:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise ValueError("无效的文件大小。") from exc
        if not 0 < length <= MAX_UPLOAD_BYTES:
            raise ValueError("文件为空或超过 200 MB 限制。")
        data = self.rfile.read(length)
        if len(data) != length:
            raise ValueError("文件上传不完整。")
        return data

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        if parsed.path == "/favicon.ico":
            self._headers(HTTPStatus.NO_CONTENT, "image/x-icon", 0)
            return
        if parsed.path == "/":
            if not self._authorized(query_allowed=True):
                return
            data = _html(self.server.session.token).encode("utf-8")
            self._headers(HTTPStatus.OK, "text/html; charset=utf-8", len(data))
            self.wfile.write(data)
            return
        if parsed.path.startswith("/download/"):
            if not self._authorized(query_allowed=True):
                return
            parts = parsed.path.split("/", 3)
            key = parts[2] if len(parts) > 2 else ""
            path = self.server.session.downloads.get(key)
            if path is None or not path.is_file() or not path.resolve().is_relative_to(self.server.session.root):
                self._json({"error": "下载文件不存在。"}, HTTPStatus.NOT_FOUND)
                return
            data = path.read_bytes()
            content_type = "application/octet-stream"
            if path.suffix == ".html":
                content_type = "text/html; charset=utf-8"
            elif path.suffix == ".json":
                content_type = "application/json; charset=utf-8"
            elif path.suffix == ".svg":
                content_type = "image/svg+xml; charset=utf-8"
            self._headers(HTTPStatus.OK, content_type, len(data))
            self.wfile.write(data)
            return
        self._json({"error": "页面不存在。"}, HTTPStatus.NOT_FOUND)

    def do_POST(self) -> None:
        if not self._authorized():
            return
        parsed = urlparse(self.path)
        try:
            if parsed.path == "/api/check":
                self._check(parsed)
            elif parsed.path == "/api/fix":
                self._fix()
            elif parsed.path == "/api/ultimate-handoff":
                self._ultimate_handoff()
            elif parsed.path == "/api/verify":
                self._verify(parsed)
            elif parsed.path == "/api/shutdown":
                self._json({"ok": True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
            else:
                self._json({"error": "接口不存在。"}, HTTPStatus.NOT_FOUND)
        except (ValueError, DeckLoadError, RenderError, CleanupError, OSError, zipfile.BadZipFile) as exc:
            self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)

    def _check(self, parsed) -> None:
        query = parse_qs(parsed.query)
        filename = _safe_filename(unquote(query.get("filename", ["presentation.pptx"])[0]))
        scenario = query.get("scenario", ["present"])[0]
        if scenario not in {"present", "screen", "document"}:
            raise ValueError("不支持的使用场景。")
        if not filename.lower().endswith(".pptx"):
            raise ValueError("只支持 .pptx 文件。")
        deck_id = secrets.token_urlsafe(10)
        deck_directory = self.server.session.uploads / deck_id
        deck_directory.mkdir(mode=0o700)
        source = deck_directory / filename
        source.write_bytes(self._body())
        os.chmod(source, 0o600)
        report_stem = self.server.session.artifacts / f"{deck_id}-pptlint-report"
        report = _audit_file(source, report_stem, scenario=scenario)
        plan = build_repair_plan(report)
        plan_path = self.server.session.artifacts / f"{deck_id}-repair-plan.json"
        brief_path = self.server.session.artifacts / f"{deck_id}-agent-brief.md"
        write_repair_plan(plan_path, plan)
        brief_path.write_text(
            render_repair_brief(plan, adapter="powerpoint-manual", language="zh-CN"),
            encoding="utf-8",
        )
        record = DeckRecord(source, scenario, report, report_stem, plan, plan_path, brief_path)
        self.server.session.decks[deck_id] = record
        self._json(_report_response(self.server.session, deck_id, record))

    def _fix(self) -> None:
        body = json.loads(self._body())
        if not isinstance(body, dict):
            raise ValueError("清理请求必须是 JSON 对象。")
        deck_id = str(body.get("deckId", ""))
        record = self.server.session.decks.get(deck_id)
        if record is None:
            raise ValueError("原 PPT 会话不存在。")
        operations = body.get("operations")
        if not isinstance(operations, list) or not operations or not all(isinstance(item, str) for item in operations):
            raise ValueError("请至少选择一项清理操作。")
        if not set(operations) <= set(OPERATIONS):
            raise ValueError("清理操作不在允许范围内。")
        run_id = secrets.token_urlsafe(6)
        output = self.server.session.artifacts / f"{deck_id}-{run_id}-delivery.pptx"
        cleanup = create_cleanup_copy(record.source, output, list(operations))
        after_stem = self.server.session.artifacts / f"{deck_id}-{run_id}-after"
        after = _audit_file(output, after_stem, scenario=record.scenario)
        comparison = build_comparison_report(record.report, after, threshold="high")
        comparison_stem = self.server.session.artifacts / f"{deck_id}-{run_id}-comparison"
        comparison_paths = write_comparison_reports(comparison_stem, comparison)
        after_rules = {str(item.get("rule_id", "")) for item in after.get("findings", []) if isinstance(item, dict)}
        rule_map = {
            "clear-personal-metadata": {"privacy.personal-metadata"},
            "remove-comments": {"privacy.comments"},
            "remove-speaker-notes": {"privacy.speaker-notes", "policy.notes-forbidden"},
        }
        incomplete = [operation for operation in operations if rule_map[operation] & after_rules]
        readiness = after.get("readiness", {})
        blocked = isinstance(readiness, dict) and readiness.get("status") == "blocked"
        passed = bool(comparison["gate"]["passed"]) and not incomplete and not blocked
        receipt_path = self.server.session.artifacts / f"{deck_id}-{run_id}-repair-receipt.json"
        receipt = {
            "schemaVersion": "pptlint-repair-receipt/v1", "toolVersion": __version__,
            "source": {"name": record.source.name, "sha256": cleanup.source_sha256},
            "output": {"name": output.name, "sha256": cleanup.output_sha256},
            "requestedOperations": operations,
            "operations": [{"operation": item.operation, "status": "applied", "changedParts": list(item.changed_parts), "changeCount": item.change_count} for item in cleanup.operations],
            "verification": {"passed": passed, "sourceHashUnchanged": sha256_path(record.source) == cleanup.source_sha256, "outputOpened": True, "outputReadiness": str(readiness.get("status", "unknown")) if isinstance(readiness, dict) else "unknown", "comparisonGatePassed": bool(comparison["gate"]["passed"]), "incompleteOperations": incomplete},
            "artifacts": {"beforeHtml": Path(f"{record.report_stem}.html").name, "beforeJson": Path(f"{record.report_stem}.json").name, "afterHtml": Path(f"{after_stem}.html").name, "afterJson": Path(f"{after_stem}.json").name, "comparisonHtml": comparison_paths[0].name, "comparisonJson": comparison_paths[1].name},
        }
        receipt_path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
        self._json({"passed": passed, "downloads": [_download_item(self.server.session, output, "清理后 PPTX"), _download_item(self.server.session, receipt_path, "清理回执"), _download_item(self.server.session, comparison_paths[0], "清理前后对比") ]})

    def _ultimate_handoff(self) -> None:
        if not ULTIMATE_NATIVE_REPAIR_AVAILABLE:
            raise ValueError(
                "已暂停自动修改真实 PPT：当前整份重导出链路可能破坏母版、透明背景、组合对象和链接。"
                "请使用报告中的 PowerPoint 步骤，或复制完整任务让助手给出定向建议。"
            )
        body = json.loads(self._body())
        if not isinstance(body, dict):
            raise ValueError("优化请求必须是 JSON 对象。")
        deck_id = str(body.get("deckId", ""))
        record = self.server.session.decks.get(deck_id)
        if record is None:
            raise ValueError("请先检查原 PPT。")
        task_ids = body.get("taskIds")
        if (
            not isinstance(task_ids, list)
            or not task_ids
            or not all(isinstance(item, str) for item in task_ids)
        ):
            raise ValueError("请至少选择一项可由 Ultimate 优化的任务。")
        selected_ids = set(task_ids)
        tasks = _ultimate_tasks(record, selected_ids)
        if len(tasks) != len(selected_ids):
            raise ValueError("所选任务中包含不适合一键优化的高风险项目。")
        health = _bridge_json("/health")
        handoff = _bridge_json("/handoff", payload=_ultimate_handoff_payload(record, tasks))
        project_path = str(handoff.get("projectPath", ""))
        if not project_path:
            raise ValueError("Ultimate Bridge 未返回本地项目路径。")
        launch = _bridge_json(
            "/agent/launch", payload={"projectPath": project_path, "agent": "codex"}
        )
        self._json(
            {
                "ok": True,
                "taskCount": len(tasks),
                "projectPath": project_path,
                "launched": bool(launch.get("launched")),
                "command": str(launch.get("command", "")),
                "bridgeVersion": str(health.get("version", "")),
            }
        )

    def _verify(self, parsed) -> None:
        query = parse_qs(parsed.query)
        visual_confirmed = query.get("visualConfirmed", [""])[0].lower() == "true"
        deck_id = query.get("deckId", [""])[0]
        record = self.server.session.decks.get(deck_id)
        if record is None:
            raise ValueError("请先检查原 PPT。")
        filename = _safe_filename(unquote(query.get("filename", ["repaired.pptx"])[0]))
        if not filename.lower().endswith(".pptx"):
            raise ValueError("只支持 .pptx 文件。")
        run_id = secrets.token_urlsafe(6)
        repaired_directory = self.server.session.uploads / deck_id / run_id
        repaired_directory.mkdir(mode=0o700)
        repaired = repaired_directory / filename
        repaired.write_bytes(self._body())
        os.chmod(repaired, 0o600)
        after_stem = self.server.session.artifacts / f"{deck_id}-{run_id}-verified-after"
        after = _audit_file(repaired, after_stem, scenario=record.scenario)
        comparison = build_comparison_report(record.report, after, threshold="high")
        comparison_stem = self.server.session.artifacts / f"{deck_id}-{run_id}-proof"
        comparison_paths = write_comparison_reports(comparison_stem, comparison)
        verification = build_repair_verification(record.plan, comparison)
        verification_path = write_repair_verification(self.server.session.artifacts / f"{deck_id}-{run_id}-verification.json", verification)
        files = [Path(f"{record.report_stem}.html"), Path(f"{record.report_stem}.json"), record.plan_path, record.brief_path, Path(f"{after_stem}.html"), Path(f"{after_stem}.json"), *comparison_paths, verification_path]
        downloads = [_download_item(self.server.session, comparison_paths[0], "完整前后对比"), _download_item(self.server.session, verification_path, "修复任务验证")]
        passed = bool(verification["passed"]) and visual_confirmed
        if passed:
            credential_path = self.server.session.artifacts / f"{deck_id}-{run_id}-pptlint-verified.json"
            credential = {"schemaVersion": "pptlint-verified/v1", "toolVersion": __version__, "status": "verified", "sourceSha256": record.plan["source"]["sha256"], "outputSha256": after["file"]["sha256"], "verificationSha256": _verification_hash(verification_path), "proof": {"comparison": comparison_paths[1].name, "verification": verification_path.name}}
            credential_path.write_text(json.dumps(credential, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
            svg_path = self.server.session.artifacts / f"{deck_id}-{run_id}-pptlint-verified.svg"
            svg_path.write_text(f'''<svg xmlns="http://www.w3.org/2000/svg" width="320" height="72" role="img" aria-label="PPTLint Verified"><a href="{verification_path.name}"><rect width="320" height="72" rx="14" fill="#0a1628"/><circle cx="38" cy="36" r="18" fill="#0d8b63"/><path d="M29 36l6 6 12-14" fill="none" stroke="white" stroke-width="4"/><text x="68" y="31" fill="white" font-family="system-ui" font-size="13" font-weight="700">PPTLINT</text><text x="68" y="51" fill="#9ee4cc" font-family="system-ui" font-size="20" font-weight="800">VERIFIED</text></a></svg>''', encoding="utf-8")
            files.extend([credential_path, svg_path])
            downloads.extend([_download_item(self.server.session, credential_path, "PPTLint Verified 凭证"), _download_item(self.server.session, svg_path, "PPTLint Verified 徽章")])
        pack = self.server.session.artifacts / f"{deck_id}-{run_id}-proof-pack.zip"
        with zipfile.ZipFile(pack, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for path in files:
                archive.write(path, arcname=path.name)
        downloads.append(_download_item(self.server.session, pack, "完整 Proof Pack"))
        self._json({"passed": passed, "automatedPassed": bool(verification["passed"]), "visualReviewRequired": not visual_confirmed, "completed": len(verification["completedTaskIds"]), "remaining": len(verification["remainingTaskIds"]), "unable": len(verification["unableToConfirmTaskIds"]), "regressions": len(verification["regressions"]), "downloads": downloads})


def create_app_server(port: int = 0) -> tuple[_Server, AppSession, str]:
    if not 0 <= port <= 65535:
        raise ValueError("Port must be between 0 and 65535")
    session = AppSession()
    try:
        server = _Server(("127.0.0.1", port), session)
    except Exception:
        session.close()
        raise
    actual_port = int(server.server_address[1])
    url = f"http://127.0.0.1:{actual_port}/?token={quote(session.token)}"
    return server, session, url


def run_app(*, port: int = 0, open_browser: bool = True) -> int:
    server, session, url = create_app_server(port)
    print(f"PPTLint local app: {url}")
    print("只绑定 127.0.0.1；关闭后临时文件会被删除。")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever(poll_interval=0.2)
    except KeyboardInterrupt:
        print("\nPPTLint local app stopped.")
    finally:
        server.server_close()
        session.close()
    return 0
