from __future__ import annotations

import http.client
import json
import threading
from pathlib import Path
from urllib.parse import urlparse

import jsonschema

import decklint.local_app as local_app
from decklint.local_app import create_app_server
from decklint.model import load_deck

from .pptx_factory import slide_xml, write_pptx


ROOT = Path(__file__).resolve().parents[1]

class LocalClient:
    def __init__(self, url: str, token: str) -> None:
        parsed = urlparse(url)
        self.host = parsed.hostname or "127.0.0.1"
        self.port = parsed.port or 80
        self.root_path = parsed.path + "?" + (parsed.query or "")
        self.token = token

    def request(
        self,
        method: str,
        path: str,
        body: bytes | None = None,
        *,
        authorized: bool = True,
        content_type: str = "application/octet-stream",
    ) -> tuple[int, bytes, dict[str, str]]:
        connection = http.client.HTTPConnection(self.host, self.port, timeout=10)
        headers = {"Content-Type": content_type}
        if authorized:
            headers["X-PPTLint-Token"] = self.token
        connection.request(method, path, body=body, headers=headers)
        response = connection.getresponse()
        data = response.read()
        result_headers = {key.lower(): value for key, value in response.getheaders()}
        connection.close()
        return response.status, data, result_headers


def _start():
    server, session, url = create_app_server()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, session, url, thread


def _stop(server, session, thread) -> None:
    server.shutdown()
    thread.join(timeout=5)
    server.server_close()
    session.close()


def test_app_binds_only_loopback_and_serves_a_self_contained_chinese_ui() -> None:
    server, session, url, thread = _start()
    root = session.root
    client = LocalClient(url, session.token)
    try:
        assert server.server_address[0] == "127.0.0.1"
        unauthorized, _, _ = client.request("GET", "/", authorized=False)
        assert unauthorized == 403

        status, body, headers = client.request("GET", client.root_path)
        markup = body.decode("utf-8")
        assert status == 200
        assert "找到难改的页面" in markup
        assert "优先按命中页处理" in markup
        assert "自动改文件暂不可用" not in markup
        assert "不会把整份真实 PPT 重导出来" in markup
        assert "待处理页面" in markup
        assert "可安全清理" in markup
        assert "需要判断" in markup
        assert "groupTasks" in markup and "pageGroupMarkup" in markup
        assert "mergePageTasks" in markup and "occurrenceCount" in markup
        assert "已合并重复" in markup
        assert "完整报告保留每一处证据" in markup
        assert "风险 high" not in markup
        assert "没有可由 PPTLint 自动清理的项目。" in markup
        assert "等待检查结果。" in markup
        assert 'target="_blank" rel="noopener"' in markup
        assert "sessionStorage" in markup
        assert "restoreSession" in markup
        assert "/api/session?deckId=" in markup
        assert "这里只记住会话编号" in markup
        assert "解析文件 → 检查风险 → 生成调整步骤" in markup
        assert "MAX_UPLOAD_BYTES=209715200" in markup
        assert "WPS 的入口名称和位置可能不同" in markup
        assert "PPTLint Verified" in markup
        assert "不上传" in markup
        assert markup.count('role="button" tabindex="0"') == 2
        assert 'aria-live="polite"' in markup
        assert "https://" not in markup and "@import" not in markup
        assert "default-src 'self'" in headers["content-security-policy"]
    finally:
        _stop(server, session, thread)
    assert not root.exists()


def test_app_restores_a_checked_deck_from_the_current_server_session(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "return-safe.pptx", slides=[slide_xml(body_size=1000)])
    server, session, url, thread = _start()
    client = LocalClient(url, session.token)
    try:
        status, body, _ = client.request(
            "POST", "/api/check?filename=return-safe.pptx&scenario=present", source.read_bytes()
        )
        assert status == 200
        checked = json.loads(body)

        status, body, _ = client.request("GET", f"/api/session?deckId={checked['deckId']}")
        assert status == 200
        restored = json.loads(body)
        assert restored["deckId"] == checked["deckId"]
        assert restored["file"]["name"] == "return-safe.pptx"
        assert restored["tasks"] == checked["tasks"]
        assert restored["agentBrief"] == checked["agentBrief"]
        assert len(restored["downloads"]) == 4

        missing, _, _ = client.request("GET", "/api/session?deckId=missing")
        assert missing == 404
    finally:
        _stop(server, session, thread)


def test_app_blocks_full_deck_reexport_handoff_until_native_repair_exists(tmp_path: Path, monkeypatch) -> None:
    source = write_pptx(tmp_path / "needs-polish.pptx", slides=[slide_xml(body_size=1000)])
    bridge_calls: list[tuple[str, dict[str, object] | None]] = []

    def fake_bridge(path: str, *, payload: dict[str, object] | None = None) -> dict[str, object]:
        bridge_calls.append((path, payload))
        if path == "/health":
            return {"ok": True, "version": "6.1.0", "allowLaunch": True}
        if path == "/handoff":
            assert payload is not None
            source_note = str(payload["sourceMarkdown"])
            assert "原文、数字、数据、结论、页数、页面顺序和未命中页面全部锁定" in source_note
            attachments = payload["attachments"]
            assert isinstance(attachments, list)
            assert {item["name"] for item in attachments} == {
                "needs-polish.pptx",
                "pptlint-repair-plan.json",
            }
            return {"ok": True, "projectPath": "/tmp/ultimate-repair"}
        assert path == "/agent/launch"
        return {"ok": True, "launched": True, "command": "codex repair"}

    monkeypatch.setattr(local_app, "_bridge_json", fake_bridge)
    server, session, url, thread = _start()
    client = LocalClient(url, session.token)
    try:
        status, body, _ = client.request(
            "POST", "/api/check?filename=needs-polish.pptx&scenario=present", source.read_bytes()
        )
        assert status == 200
        checked = json.loads(body)
        planned = [task for task in checked["tasks"] if task["ultimatePlanEligible"]]
        assert planned
        assert all(task["ultimateEligible"] is False for task in checked["tasks"])
        payload = json.dumps(
            {"deckId": checked["deckId"], "taskIds": [planned[0]["taskId"]]}
        ).encode("utf-8")
        status, body, _ = client.request(
            "POST", "/api/ultimate-handoff", payload, content_type="application/json"
        )
        result = json.loads(body)
        assert status == 400
        assert "已暂停自动修改真实 PPT" in result["error"]
        assert bridge_calls == []
    finally:
        _stop(server, session, thread)


def test_app_keeps_accessibility_and_deck_level_tasks_out_of_one_click(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "manual-only.pptx",
        slides=[slide_xml(title=None, include_picture=True, picture_alt="")],
    )
    server, session, url, thread = _start()
    client = LocalClient(url, session.token)
    try:
        status, body, _ = client.request(
            "POST", "/api/check?filename=manual-only.pptx&scenario=present", source.read_bytes()
        )
        assert status == 200
        tasks = json.loads(body)["tasks"]
        accessibility = [task for task in tasks if task["ruleId"].startswith("accessibility.")]
        deck_level = [task for task in tasks if task["slideIndex"] is None]

        assert accessibility
        assert all(task["ultimateEligible"] is False for task in accessibility)
        assert all(task["ultimateEligible"] is False for task in deck_level)
    finally:
        _stop(server, session, thread)


def test_app_checks_cleans_and_downloads_a_separate_copy(tmp_path: Path) -> None:
    source = write_pptx(
        tmp_path / "客户汇报.pptx",
        creator="Alice",
        include_comments=True,
        notes_text="internal only",
    )
    server, session, url, thread = _start()
    client = LocalClient(url, session.token)
    try:
        status, body, _ = client.request(
            "POST",
            "/api/check?filename=%E5%AE%A2%E6%88%B7%E6%B1%87%E6%8A%A5.pptx&scenario=present",
            source.read_bytes(),
        )
        assert status == 200
        checked = json.loads(body)
        assert checked["file"]["name"] == "客户汇报.pptx"
        assert set(checked["cleanupOperations"]) == {
            "clear-personal-metadata",
            "remove-comments",
            "remove-speaker-notes",
        }

        status, body, _ = client.request(
            "POST",
            f"/api/verify?filename=still-private.pptx&deckId={checked['deckId']}",
            source.read_bytes(),
        )
        unverified = json.loads(body)
        assert status == 200
        assert unverified["passed"] is False
        assert not any("pptlint-verified" in item["name"] for item in unverified["downloads"])

        payload = json.dumps(
            {"deckId": checked["deckId"], "operations": checked["cleanupOperations"]}
        ).encode("utf-8")
        status, body, _ = client.request(
            "POST", "/api/fix", payload, content_type="application/json"
        )
        assert status == 200
        cleaned = json.loads(body)
        pptx_download = next(item for item in cleaned["downloads"] if item["name"].endswith(".pptx"))
        parsed = urlparse(pptx_download["url"])
        status, data, _ = client.request("GET", parsed.path + "?" + parsed.query)
        assert status == 200
        downloaded = tmp_path / "downloaded.pptx"
        downloaded.write_bytes(data)
        deck = load_deck(downloaded)
        assert deck.metadata == {}
        assert deck.comments_count == 0
        assert all(not slide.notes_text for slide in deck.slides)
    finally:
        _stop(server, session, thread)


def test_app_generates_verified_credential_only_after_a_passing_recheck(tmp_path: Path) -> None:
    source = write_pptx(tmp_path / "ready.pptx")
    server, session, url, thread = _start()
    client = LocalClient(url, session.token)
    try:
        status, body, _ = client.request(
            "POST", "/api/check?filename=ready.pptx&scenario=present", source.read_bytes()
        )
        assert status == 200
        checked = json.loads(body)
        assert checked["tasks"] == []

        status, body, _ = client.request(
            "POST",
            f"/api/verify?filename=ready-after.pptx&deckId={checked['deckId']}",
            source.read_bytes(),
        )
        assert status == 200
        unconfirmed = json.loads(body)
        assert unconfirmed["automatedPassed"] is True
        assert unconfirmed["passed"] is False
        assert unconfirmed["visualReviewRequired"] is True
        assert not any("pptlint-verified" in item["name"] for item in unconfirmed["downloads"])

        status, body, _ = client.request(
            "POST",
            f"/api/verify?filename=ready-after.pptx&deckId={checked['deckId']}&visualConfirmed=true",
            source.read_bytes(),
        )
        assert status == 200
        verified = json.loads(body)
        assert verified["passed"] is True
        assert verified["visualReviewRequired"] is False
        names = {item["name"] for item in verified["downloads"]}
        assert any(name.endswith("pptlint-verified.json") for name in names)
        assert any(name.endswith("pptlint-verified.svg") for name in names)
        assert any(name.endswith("proof-pack.zip") for name in names)
        credential_item = next(
            item for item in verified["downloads"] if item["name"].endswith("pptlint-verified.json")
        )
        parsed = urlparse(credential_item["url"])
        status, data, _ = client.request("GET", parsed.path + "?" + parsed.query)
        assert status == 200
        jsonschema.validate(
            json.loads(data),
            json.loads(
                (ROOT / "schema/pptlint-verified-v1.schema.json").read_text(encoding="utf-8")
            ),
        )
    finally:
        _stop(server, session, thread)
