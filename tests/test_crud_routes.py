"""Routen-Tests für Freigaben, Benutzer und Datei-API."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from app.csrf import CSRF_SESSION_KEY
from app.samba import Share
from tests.test_auth_security import _login_post


def _token(client) -> str:
    with client.session_transaction() as sess:
        return sess[CSRF_SESSION_KEY]


def test_share_create_persists(client, app_config, monkeypatch):
    _config_path, data = app_config
    base = Path(data["shares_base_path"])
    base.mkdir(parents=True, exist_ok=True)
    saved: dict = {}

    monkeypatch.setattr("app.routes.shares.read_shares", lambda *_a, **_k: [])
    monkeypatch.setattr("app.routes.shares.get_share_by_name", lambda *_a, **_k: None)
    monkeypatch.setattr(
        "app.routes.shares.write_shares",
        lambda shares, *_a, **_k: saved.update(shares=list(shares)),
    )
    monkeypatch.setattr("app.routes.shares.load_samba_users_for_form", lambda: ["alice"])

    _login_post(client)
    client.get("/shares/new")
    res = client.post(
        "/shares/new",
        data={
            "csrf_token": _token(client),
            "name": "media",
            "path": str(base / "media"),
            "comment": "Filme",
            "valid_users": ["alice"],
            "browseable": "on",
            "enabled": "on",
        },
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert res.headers["Location"].endswith("/shares")
    assert saved["shares"][0].name == "media"


def test_user_create_and_delete(client, monkeypatch):
    created: dict = {}
    deleted: list[str] = []
    monkeypatch.setattr(
        "app.routes.users.add_samba_user",
        lambda username, password: created.update(user=username, password=password),
    )
    monkeypatch.setattr("app.routes.users.delete_samba_user", lambda username: deleted.append(username))
    monkeypatch.setattr("app.routes.users.list_samba_users", lambda: ["alice"])

    _login_post(client)
    client.get("/users/new")
    res = client.post(
        "/users/new",
        data={
            "csrf_token": _token(client),
            "username": "alice",
            "password": "secretpass",
        },
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert created["user"] == "alice"

    res = client.post(
        "/users/alice/delete",
        data={"csrf_token": _token(client)},
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert deleted == []

    res = client.post(
        "/users/alice/delete",
        data={"csrf_token": _token(client), "confirm_password": "testpass123"},
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert deleted == ["alice"]


def test_files_mkdir_and_delete(client, monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(
        "app.routes.files_routes.create_directory",
        lambda share, path, name: calls.append(("mkdir", share, path, name)),
    )
    monkeypatch.setattr(
        "app.routes.files_routes.delete_path",
        lambda share, path: calls.append(("delete", share, path)),
    )

    _login_post(client)
    client.get("/dateien")
    headers = {"X-CSRF-Token": _token(client)}
    res = client.post(
        "/api/files/mkdir",
        headers=headers,
        json={"share": "media", "path": "", "name": "docs"},
    )
    assert res.status_code == 200
    assert res.get_json()["ok"] is True

    res = client.post(
        "/api/files/delete",
        headers=headers,
        json={"share": "media", "path": "docs"},
    )
    assert res.status_code == 403
    assert calls == [("mkdir", "media", "", "docs")]

    res = client.post(
        "/api/files/delete",
        headers=headers,
        json={"share": "media", "path": "docs", "password": "testpass123"},
    )
    assert res.status_code == 200
    assert calls == [
        ("mkdir", "media", "", "docs"),
        ("delete", "media", "docs"),
    ]


def test_files_upload_commits(client, monkeypatch, tmp_path):
    committed: dict = {}
    monkeypatch.setattr("app.routes.files_routes.FILE_STAGING_DIR", str(tmp_path))
    monkeypatch.setattr(
        "app.routes.files_routes.commit_upload",
        lambda share, path, staging, filename: committed.update(
            share=share, path=path, filename=filename
        ),
    )

    _login_post(client)
    client.get("/dateien")
    res = client.post(
        "/api/files/upload",
        data={
            "csrf_token": _token(client),
            "share": "media",
            "path": "",
            "file": (BytesIO(b"hello"), "readme.txt"),
        },
        content_type="multipart/form-data",
    )
    assert res.status_code == 200
    assert res.get_json()["ok"] is True
    assert committed["filename"] == "readme.txt"
    assert committed["share"] == "media"


def test_share_create_requires_login(client):
    res = client.post("/shares/new", data={"name": "x"})
    assert res.status_code in (302, 403)


def test_share_delete_files_requires_admin_password(client, monkeypatch):
    share = Share(name="media", path="/srv/shares/media")
    written: dict = {}
    deleted_dirs: list[str] = []
    monkeypatch.setattr("app.routes.shares.read_shares", lambda *_a, **_k: [share])
    monkeypatch.setattr("app.routes.shares.get_share_by_name", lambda *_a, **_k: share)
    monkeypatch.setattr(
        "app.routes.shares.write_shares",
        lambda shares, *_a, **_k: written.update(shares=list(shares)),
    )
    monkeypatch.setattr(
        "app.routes.shares.delete_share_directory",
        lambda path, *_a, **_k: deleted_dirs.append(path),
    )

    _login_post(client)
    client.get("/shares/media/delete")
    res = client.post(
        "/shares/media/delete",
        data={"csrf_token": _token(client), "delete_files": "on"},
        follow_redirects=False,
    )
    assert res.status_code == 200
    assert b"checked" in res.data
    assert "shares" not in written
    assert deleted_dirs == []

    res = client.post(
        "/shares/media/delete",
        data={
            "csrf_token": _token(client),
            "delete_files": "on",
            "confirm_password": "testpass123",
        },
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert written["shares"] == []
    assert deleted_dirs == ["/srv/shares/media"]


def test_share_toggle_requires_admin_password(client, monkeypatch):
    share = Share(name="media", path="/srv/shares/media", enabled=True)
    written: dict = {}
    monkeypatch.setattr("app.routes.shares.read_shares", lambda *_a, **_k: [share])
    monkeypatch.setattr("app.routes.shares.get_share_by_name", lambda *_a, **_k: share)
    monkeypatch.setattr(
        "app.routes.shares.write_shares",
        lambda shares, *_a, **_k: written.update(enabled=shares[0].enabled),
    )

    _login_post(client)
    client.get("/shares")
    res = client.post(
        "/shares/media/toggle",
        data={"csrf_token": _token(client)},
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert "enabled" not in written
    assert share.enabled is True

    res = client.post(
        "/shares/media/toggle",
        data={"csrf_token": _token(client), "confirm_password": "testpass123"},
        follow_redirects=False,
    )
    assert res.status_code == 302
    assert written["enabled"] is False
    assert share.enabled is False
