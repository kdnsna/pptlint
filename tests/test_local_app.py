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
        assert "把难改的页点出来" in markup
        assert "自己在 PowerPoint 里改" in markup
        assert "交给 Ultimate 优化" in markup
        assert "PPTLint Verified" in markup
        assert "不上传" in markup
        assert markup.count('role="button" tabindex="0"') == 2
        assert 'aria-live="polite"' in markup
        assert "https://" not in markup and "@import" not in markup
        assert "default-src 'self'" in headers["content-security-policy"]
    finally:
        _stop(server, session, thread)
    assert not root.exists()


def test_app_hands_only_selected_eligible_tasks_to_ultimate(tmp_path: Path, monkeypatch) -> None:
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
        eligible = [task for task in checked["tasks"] if task["ultimateEligible"]]
        assert eligible
        payload = json.dumps(
            {"deckId": checked["deckId"], "taskIds": [eligible[0]["taskId"]]}
        ).encode("utf-8")
        status, body, _ = client.request(
            "POST", "/api/ultimate-handoff", payload, content_type="application/json"
        )
        result = json.loads(body)
        assert status == 200
        assert result["launched"] is True
        assert result["taskCount"] == 1
        assert [path for path, _ in bridge_calls] == [
            "/health",
            "/handoff",
            "/agent/launch",
        ]
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
        verified = json.loads(body)
        assert verified["passed"] is True
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
