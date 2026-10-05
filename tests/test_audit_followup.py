"""Health-Check, CSP und Step-up für Samba-Dienstaktionen."""

from __future__ import annotations

from app.csrf import CSRF_SESSION_KEY
from tests.test_auth_security import _login_post


def _form_token(client) -> str:
    _login_post(client)
    client.get("/status")
    with client.session_transaction() as sess:
        return sess[CSRF_SESSION_KEY]


def test_health_is_public(client):
    res = client.get("/health")
    assert res.status_code == 200
    body = res.get_json()
    assert body == {"ok": True, "priv_socket": body["priv_socket"]}
    assert isinstance(body["priv_socket"], bool)
    assert b"password" not in res.data
    assert b"secret" not in res.data


def test_csp_blocks_inline_scripts(client):
    res = client.get("/login")
    csp = res.headers["Content-Security-Policy"]
    assert csp == "default-src 'self'; style-src 'self'; script-src 'self'"
    assert b"<script>" not in res.data
    assert b'style="' not in res.data


def test_templates_have_no_inline_styles():
    from pathlib import Path

    root = Path(__file__).resolve().parents[1] / "app" / "templates"
    offenders = [path.name for path in root.glob("*.html") if 'style="' in path.read_text(encoding="utf-8")]
    assert offenders == []


def test_service_reload_requires_password(client, monkeypatch):
    called = {"n": 0}

    def _reload():
        called["n"] += 1

    monkeypatch.setattr("app.routes.service.reload_samba", _reload)
    token = _form_token(client)
    res = client.post(
        "/service/reload",
        data={"csrf_token": token},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert called["n"] == 0
    assert "Admin-Passwort erforderlich." in res.get_data(as_text=True)


def test_service_restart_requires_password(client, monkeypatch):
    called = {"n": 0}

    def _restart():
        called["n"] += 1

    monkeypatch.setattr("app.routes.service.restart_samba", _restart)
    token = _form_token(client)
    res = client.post(
        "/service/restart",
        data={"csrf_token": token, "confirm_password": ""},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert called["n"] == 0
    assert "Admin-Passwort erforderlich." in res.get_data(as_text=True)


def test_service_restart_with_password(client, monkeypatch):
    called = {"n": 0}

    def _restart():
        called["n"] += 1

    monkeypatch.setattr("app.routes.service.restart_samba", _restart)
    token = _form_token(client)
    res = client.post(
        "/service/restart",
        data={"csrf_token": token, "confirm_password": "testpass123"},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert called["n"] == 1
    assert "neu gestartet" in res.get_data(as_text=True)


def test_service_reload_with_password(client, monkeypatch):
    monkeypatch.setattr("app.routes.service.reload_samba", lambda: None)
    token = _form_token(client)
    res = client.post(
        "/service/reload",
        data={"csrf_token": token, "confirm_password": "testpass123"},
        follow_redirects=True,
    )
    assert res.status_code == 200
    assert "neu geladen" in res.get_data(as_text=True)
