from __future__ import annotations

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
from urllib.parse import parse_qs, quote, unquote, urlparse

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
:root{--ink:#0a1628;--muted:#657083;--paper:#f4f1eb;--panel:#fff;--accent:#e85d2c;--green:#0d8b63;--amber:#b66a09;--red:#c3382b}*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);font:15px/1.65 "PingFang SC","Microsoft YaHei",system-ui,sans-serif}button,input,select{font:inherit}.shell{width:min(1120px,calc(100% - 32px));margin:auto}.nav{display:flex;justify-content:space-between;align-items:center;padding:20px 0}.brand{font:900 17px/1 ui-monospace,monospace;letter-spacing:.14em}.privacy{color:var(--muted);font-size:13px}.hero{display:grid;grid-template-columns:1.2fr .8fr;gap:28px;padding:52px 0 36px}.eyebrow{font:800 12px/1 ui-monospace,monospace;letter-spacing:.13em;color:var(--accent)}h1{font-size:clamp(42px,7vw,76px);line-height:.98;letter-spacing:-.055em;margin:14px 0 22px}.lead{font-size:18px;color:var(--muted);max-width:680px}.trust{align-self:end;background:var(--ink);color:white;border-radius:24px;padding:26px;box-shadow:0 24px 70px #0a16282a}.trust strong{display:block;font-size:28px}.trust span{display:block;color:#c6cfdd;margin-top:8px}.steps{display:grid;grid-template-columns:repeat(3,1fr);gap:16px;margin:18px 0 70px}.card{background:var(--panel);border:1px solid #dfe2e7;border-radius:20px;padding:24px;box-shadow:0 14px 40px #0a16280c}.card h2{font-size:24px;margin:8px 0}.num{font:800 12px ui-monospace,monospace;color:var(--accent)}.drop{display:flex;flex-direction:column;align-items:center;justify-content:center;width:100%;min-height:136px;border:2px dashed #aeb6c2;border-radius:16px;padding:28px 18px;text-align:center;background:#fafbfc;color:var(--ink);cursor:pointer;transition:.2s}.drop.drag{border-color:var(--accent);background:#fff4ee}.drop input{display:none}.drop b{display:block;width:100%;color:var(--ink);font-size:18px}.drop span{display:block;width:100%;color:var(--muted);font-size:13px}.select{display:block;width:100%;border:1px solid #ccd2da;border-radius:10px;padding:10px 12px;margin:14px 0;background:white}.result{display:none;margin-top:22px}.result.show{display:block}.status{display:flex;gap:12px;align-items:center;padding:16px;border-radius:14px;background:#edf7f3}.status.blocked{background:#fff0ed}.status.review{background:#fff6e8}.status b{font-size:20px}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin:12px 0}.metric{background:#f4f6f8;padding:12px;border-radius:10px}.metric strong{display:block;font-size:22px}.tasks{max-height:390px;overflow:auto;border-top:1px solid #e2e5e9}.task{padding:14px 0;border-bottom:1px solid #e2e5e9}.task b{display:block}.pill{display:inline-block;border:1px solid #cdd3db;border-radius:99px;padding:2px 8px;font-size:11px;margin:5px 4px 0 0}.actions{display:flex;flex-wrap:wrap;gap:9px;margin-top:14px}.btn{border:0;border-radius:10px;padding:10px 14px;font-weight:750;cursor:pointer;background:var(--ink);color:white;text-decoration:none}.btn.alt{background:white;color:var(--ink);border:1px solid #b8c0cb}.btn:disabled{opacity:.38;cursor:not-allowed}.checks{display:grid;gap:8px;margin:12px 0}.checks label{display:flex;gap:8px;align-items:center;background:#f5f6f8;padding:9px 10px;border-radius:9px}.message{margin-top:12px;padding:12px;border-left:4px solid var(--green);background:#edf7f3;display:none}.message.show{display:block}.downloads{display:flex;flex-wrap:wrap;gap:8px;margin-top:12px}.downloads a{color:#1457a6}.footer{padding:24px 0 54px;color:var(--muted);font-size:13px}.spinner{opacity:.6;pointer-events:none}@media(max-width:820px){.hero{grid-template-columns:1fr}.steps{grid-template-columns:1fr}.trust{align-self:auto}}@media(max-width:430px){.shell{width:min(100% - 22px,1120px)}.nav{align-items:flex-start;gap:12px}.privacy{max-width:180px;text-align:right}.hero{padding-top:28px}h1{font-size:45px}.card{padding:18px}.metrics{grid-template-columns:1fr}.actions{display:grid}.btn{text-align:center;width:100%}}
</style></head><body><div class="shell"><nav class="nav"><div class="brand">PPTLINT / LOCAL</div><div class="privacy">只运行在本机 · 不上传 · 不调用模型</div></nav><header class="hero"><div><span class="eyebrow">POWERPOINT 发出前的最后一关</span><h1>先检查，再修改，<br>最后用证据交付。</h1><p class="lead">不需要看懂代码。把 PPT 拖进来，先看哪几页会翻车；能安全清理的内容由你逐项授权，复杂问题直接复制给助手。</p></div><aside class="trust"><strong>源文件永远不动</strong><span>默认只读检查。清理时只生成独立副本，并附上修改回执和复检报告。</span></aside></header><main class="steps"><section class="card" id="check-card"><span class="num">01 · 检查</span><h2>拖入要发的 PPT</h2><select class="select" id="scenario" aria-label="选择 PPT 使用场景"><option value="present">会议室汇报</option><option value="screen">电脑屏幕阅读</option><option value="document">文档型 PPT</option></select><label class="drop" id="check-drop" role="button" tabindex="0"><input type="file" accept=".pptx"><b>点击或拖入 .pptx</b><span>本地检查，文件不会离开这台电脑</span></label><div class="result" id="check-result" aria-live="polite"></div></section><section class="card"><span class="num">02 · 处理</span><h2>你决定改什么</h2><p>作者信息、批注和讲者备注可以在授权后清理副本。版式、字体、隐藏页和外链仍需你或助手判断。</p><div class="checks" id="cleanup-checks"><span style="color:var(--muted)">先完成第一步。</span></div><div class="actions"><button class="btn" id="cleanup-btn" disabled>生成清理副本</button><button class="btn alt" id="copy-btn" disabled>复制完整 Agent 任务</button></div><div class="message" id="cleanup-message" aria-live="polite"></div></section><section class="card"><span class="num">03 · 复检</span><h2>拖入修改后的 PPT</h2><p>复检会告诉你：哪些任务已完成、哪些仍存在、是否出现新问题。</p><label class="drop" id="verify-drop" role="button" tabindex="0"><input type="file" accept=".pptx"><b>点击或拖入修改后副本</b><span>只有复检通过，才会生成 PPTLint Verified 凭证</span></label><div class="result" id="verify-result" aria-live="polite"></div></section></main><footer class="footer">PPTLint __VERSION__ · 会话关闭后自动删除临时文件 · 无统计 · 无遥测</footer></div>
<script>const TOKEN=__TOKEN__;const state={deck:null};const opLabels={'clear-personal-metadata':'清除作者和最后编辑者信息','remove-comments':'移除批注','remove-speaker-notes':'移除讲者备注'};function auth(){return{'X-PPTLint-Token':TOKEN}}function esc(s){return String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]))}function downloads(items){return '<div class="downloads">'+(items||[]).map(x=>`<a href="${esc(x.url)}">${esc(x.label)}</a>`).join('')+'</div>'}function wireDrop(id,fn){const box=document.getElementById(id),input=box.querySelector('input');box.addEventListener('click',()=>input.click());box.addEventListener('keydown',e=>{if(e.key==='Enter'||e.key===' '){e.preventDefault();input.click()}});input.addEventListener('change',()=>input.files[0]&&fn(input.files[0]));['dragenter','dragover'].forEach(e=>box.addEventListener(e,x=>{x.preventDefault();box.classList.add('drag')}));['dragleave','drop'].forEach(e=>box.addEventListener(e,x=>{x.preventDefault();box.classList.remove('drag')}));box.addEventListener('drop',e=>e.dataTransfer.files[0]&&fn(e.dataTransfer.files[0]))}async function api(path,opt={}){opt.headers={...(opt.headers||{}),...auth()};const r=await fetch(path,opt);const data=await r.json();if(!r.ok)throw new Error(data.error||'运行失败');return data}async function check(file){const card=document.getElementById('check-card');card.classList.add('spinner');try{const scenario=document.getElementById('scenario').value;const data=await api(`/api/check?filename=${encodeURIComponent(file.name)}&scenario=${scenario}`,{method:'POST',headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.presentationml.presentation'},body:file});state.deck=data;renderCheck(data);renderCleanup(data)}catch(e){showError('check-result',e.message)}finally{card.classList.remove('spinner')}}function renderCheck(d){const r=d.readiness||{},cls=r.status||'review',label={ready:'可以交付',review:'发送前再看一眼',blocked:'先处理再发送'}[cls]||'需要检查';const tasks=d.tasks||[];document.getElementById('check-result').innerHTML=`<div class="status ${cls}"><div><b>${label}</b><div>${tasks.length}项完整修复任务</div></div></div><div class="metrics"><div class="metric"><span>辅助分数</span><strong>${d.score}</strong></div><div class="metric"><span>助手处理</span><strong>${d.modeCounts['agent-rebuild']||0}</strong></div><div class="metric"><span>需你判断</span><strong>${d.modeCounts['human-decision']||0}</strong></div></div><div class="tasks">${tasks.map(t=>`<div class="task"><b>${t.slideIndex?`第 ${t.slideIndex} 页 · `:''}${esc(t.consequence)}</b><span class="pill">${esc(t.repairMode)}</span><span class="pill">风险 ${esc(t.risk)}</span></div>`).join('')}</div>${downloads(d.downloads)}`;document.getElementById('check-result').classList.add('show')}function renderCleanup(d){const box=document.getElementById('cleanup-checks'),ops=d.cleanupOperations||[];box.innerHTML=ops.length?ops.map(op=>`<label><input type="checkbox" value="${op}">${opLabels[op]}</label>`).join(''):'<span style="color:var(--muted)">没有可由 PPTLint 自动清理的项目。</span>';document.getElementById('cleanup-btn').disabled=!ops.length;document.getElementById('copy-btn').disabled=false}async function cleanup(){const ops=[...document.querySelectorAll('#cleanup-checks input:checked')].map(x=>x.value);if(!ops.length){showMessage('请先勾选至少一项。',false);return}try{const data=await api('/api/fix',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({deckId:state.deck.deckId,operations:ops})});showMessage(`${data.passed?'清理并复检完成':'副本已生成，但仍有需处理的问题。'}${downloads(data.downloads)}`,true)}catch(e){showMessage(e.message,false)}}function showMessage(text,html){const el=document.getElementById('cleanup-message');el[html?'innerHTML':'textContent']=text;el.classList.add('show')}async function copyBrief(){await navigator.clipboard.writeText(state.deck.agentBrief);const b=document.getElementById('copy-btn');b.textContent='已复制完整任务'}async function verify(file){if(!state.deck){showError('verify-result','请先检查原 PPT。');return}try{const d=await api(`/api/verify?filename=${encodeURIComponent(file.name)}&deckId=${encodeURIComponent(state.deck.deckId)}`,{method:'POST',headers:{'Content-Type':'application/vnd.openxmlformats-officedocument.presentationml.presentation'},body:file});const label=d.passed?'复检通过 · PPTLint Verified':'复检未通过';document.getElementById('verify-result').innerHTML=`<div class="status ${d.passed?'':'review'}"><div><b>${label}</b><div>已完成 ${d.completed} · 仍存在 ${d.remaining} · 无法确认 ${d.unable} · 回归 ${d.regressions}</div></div></div>${downloads(d.downloads)}`;document.getElementById('verify-result').classList.add('show')}catch(e){showError('verify-result',e.message)}}function showError(id,msg){const el=document.getElementById(id);el.innerHTML=`<div class="status blocked"><b>${esc(msg)}</b></div>`;el.classList.add('show')}wireDrop('check-drop',check);wireDrop('verify-drop',verify);document.getElementById('cleanup-btn').addEventListener('click',cleanup);document.getElementById('copy-btn').addEventListener('click',copyBrief);</script></body></html>'''
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
        brief_path.write_text(render_repair_brief(plan, adapter="generic-agent", language="zh-CN"), encoding="utf-8")
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

    def _verify(self, parsed) -> None:
        query = parse_qs(parsed.query)
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
        if verification["passed"]:
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
        self._json({"passed": verification["passed"], "completed": len(verification["completedTaskIds"]), "remaining": len(verification["remainingTaskIds"]), "unable": len(verification["unableToConfirmTaskIds"]), "regressions": len(verification["regressions"]), "downloads": downloads})


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
