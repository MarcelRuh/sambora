"""Tests für Host-Redirect, Passwortzwang, Audit-Rotation und Re-Auth."""

from __future__ import annotations

from app.auth import verify_password
from app.csrf import CSRF_SESSION_KEY
from app.http import parse_host_header, safe_redirect_hostname
from tests.test_auth_security import _login_post


def test_parse_host_header_strips_port_and_rejects_injection():
    assert parse_host_header("nas.lan:8080") == "nas.lan"
    assert parse_host_header("[::1]:8443") == "::1"
    assert parse_host_header("evil.example\r\nX-Injected: 1") is None
    assert parse_host_header("evil.example/phishing") is None


def test_safe_redirect_hostname_rejects_public_attacker_host():
    assert (
        safe_redirect_hostname("evil.example", bind_host="0.0.0.0")
        == "127.0.0.1"
    )
    assert (
        safe_redirect_hostname("evil.example", bind_host="192.0.2.10")
        == "192.0.2.10"
    )


def test_safe_redirect_hostname_allows_private_and_local():
    assert safe_redirect_hostname("192.168.1.20:8080", bind_host="0.0.0.0") == "192.168.1.20"
    assert safe_redirect_hostname("nas.local", bind_host="0.0.0.0") == "nas.local"
    assert (
        safe_redirect_hostname(
            "nas.example.test",
            bind_host="0.0.0.0",
            public_hostname="nas.example.test",
        )
        == "nas.example.test"
    )


def test_hash_admin_password_script_handles_quotes():
    import importlib.util
    from pathlib import Path

    path = Path(__file__).resolve().parents[1] / "scripts" / "hash-admin-password.py"
    spec = importlib.util.spec_from_file_location("hash_admin_password", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    hashed = module.hash_admin_password(b"O'Brien\"pass")
    assert verify_password("O'Brien\"pass", hashed)


def _csrf_token(client) -> str:
    with client.session_transaction() as sess:
        return sess[CSRF_SESSION_KEY]


def test_login_forces_password_change(client, monkeypatch, tmp_path):
    pw_file = tmp_path / "initial-password.txt"
    pw_file.write_text("testpass123\n", encoding="utf-8")
    monkeypatch.setattr("app.auth.INITIAL_PASSWORD_FILE", str(pw_file))

    res = _login_post(client)
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/change-password")

    blocked = client.get("/shares", follow_redirects=False)
    assert blocked.status_code == 302
    assert blocked.headers["Location"].endswith("/change-password")


def test_password_change_deletes_initial_file(client, monkeypatch, tmp_path):
    pw_file = tmp_path / "initial-password.txt"
    pw_file.write_text("testpass123\n", encoding="utf-8")
    monkeypatch.setattr("app.auth.INITIAL_PASSWORD_FILE", str(pw_file))

    _login_post(client)
    client.get("/change-password")
    token = _csrf_token(client)
    res = client.post(
        "/change-password",
        data={
            "csrf_token": token,
            "current_password": "testpass123",
            "new_password": "newpass1234",
            "confirm_password": "newpass1234",
        },
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/")
    assert not pw_file.exists() or not pw_file.read_text(encoding="utf-8").strip()


def test_audit_log_tails_newest_first(tmp_path, monkeypatch):
    from app import audit

    log_path = tmp_path / "audit.log"
    monkeypatch.setattr("app.audit.AUDIT_LOG_PATH", log_path)
    monkeypatch.setattr("app.audit.MAX_LOG_BYTES", 10_000_000)

    for i in range(8):
        audit.audit_log("share.create", f"item-{i}", user="admin")

    entries = audit.read_audit_log(limit=3)
    assert [e["detail"] for e in entries] == ["item-7", "item-6", "item-5"]


def test_audit_log_rotates_when_too_large(tmp_path, monkeypatch):
    from app import audit

    log_path = tmp_path / "audit.log"
    monkeypatch.setattr("app.audit.AUDIT_LOG_PATH", log_path)
    monkeypatch.setattr("app.audit.MAX_LOG_BYTES", 120)

    for i in range(12):
        audit.audit_log("share.create", f"item-{i}", user="admin")

    assert log_path.is_file()
    assert (tmp_path / "audit.log.1").is_file()
    assert audit.read_audit_log(limit=20)


def test_app_update_start_requires_password(client, monkeypatch):
    monkeypatch.setattr("app.routes.system.app_update_start", lambda: None)
    _login_post(client)
    client.get("/")
    token = _csrf_token(client)
    res = client.post(
        "/system/updates/app/start",
        headers={"X-CSRF-Token": token},
        json={},
    )
    assert res.status_code == 403
