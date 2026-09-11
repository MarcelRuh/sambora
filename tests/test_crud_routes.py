"""Routen-Tests für Freigaben, Benutzer und Datei-API."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path

from app.csrf import CSRF_SESSION_KEY
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
