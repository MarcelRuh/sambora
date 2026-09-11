#!/usr/bin/env python3
"""Erzeugt README-Screenshots mit Dummy-Daten (keine echten Hostnamen/Pfade)."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import bcrypt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT_DIR = ROOT / "docs" / "screenshots"
HOST = "127.0.0.1"
PORT = 8765
BASE = f"http://{HOST}:{PORT}"
MTIME = int(datetime(2026, 3, 15, 10, 30, tzinfo=timezone.utc).timestamp())


def dummy_shares():
    from app.samba import Share

    return [
        Share(
            name="media",
            path="/srv/shares/media",
            comment="Filme, Serien und Musik",
            valid_users=["alice", "bob"],
            enabled=True,
        ),
        Share(
            name="backup",
            path="/srv/shares/backup",
            comment="Tägliche Sicherungen",
            valid_users=["alice"],
            enabled=True,
        ),
        Share(
            name="docs",
            path="/srv/shares/docs",
            comment="Dokumente und Vorlagen",
            valid_users=["alice", "bob", "charlie"],
            enabled=True,
        ),
    ]


def dummy_overview():
    from app.system import SystemOverview

    return SystemOverview(
        disk_path="/srv/shares",
        disk_total=8 * 1024**4,
        disk_used=int(3.4 * 1024**4),
        disk_free=int(4.6 * 1024**4),
        disk_percent=42.0,
        disk_error="",
        reboot_required=False,
        reboot_reason="",
        uptime_seconds=12 * 86400 + 4 * 3600,
        upgradable_count=0,
        cpu_count=8,
        cpu_percent=11.0,
        load_1=0.42,
        load_5=0.38,
        load_15=0.31,
        mem_total=32 * 1024**3,
        mem_used=int(11.2 * 1024**3),
        mem_percent=35.0,
        mem_error="",
    )


def dummy_smb_status():
    from app.smbstatus_parser import SmbConnection, SmbStatusSummary

    return SmbStatusSummary(
        connections=[
            SmbConnection("alice", "192.0.2.20", "media", "2026-03-15T10:12:00"),
            SmbConnection("bob", "192.0.2.21", "backup", "2026-03-15T09:48:00"),
        ],
        session_count=2,
        open_files_count=3,
        version="4.22.0",
    )


def dummy_app_update():
    from app import __version__
    from app.app_updates import AppUpdateInfo

    return AppUpdateInfo(
        current_version=__version__,
        latest_version=__version__,
        update_available=False,
        github_repo="example/sambora",
        github_branch="main",
        repo_url="https://github.com/example/sambora",
        bootstrap_command="wget -qO- https://example.test/bootstrap.sh | bash",
        manual_command="git clone https://github.com/example/sambora.git",
        check_error=None,
        checked_at=time.time(),
        from_cache=True,
    )


def dummy_list_directory(share_name: str, rel_path: str = "") -> dict:
    return {
        "path": f"/srv/shares/{share_name}",
        "entries": [
            {"name": "Movies", "type": "dir", "size": 0, "mtime": MTIME},
            {"name": "Photos", "type": "dir", "size": 0, "mtime": MTIME},
            {"name": "Music", "type": "dir", "size": 0, "mtime": MTIME},
            {"name": "README.txt", "type": "file", "size": 2048, "mtime": MTIME},
            {"name": "sample-clip.mp4", "type": "file", "size": 256 * 1024 * 1024, "mtime": MTIME},
        ],
        "rel_path": rel_path or "",
        "parent_rel": "",
        "share": share_name,
        "read_only": False,
        "share_path": f"/srv/shares/{share_name}",
    }


def write_config(tmp: Path) -> Path:
    shares_file = tmp / "smb-shares.conf"
    shares_file.write_text("# dummy\n", encoding="utf-8")
    password_hash = bcrypt.hashpw(b"demo-pass-123", bcrypt.gensalt(rounds=4)).decode()
    config_path = tmp / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "bind_host": "nas.example.test",
                "bind_port": 8443,
                "http_port": 8080,
                "shares_base_path": "/srv/shares",
                "samba_shares_file": str(shares_file),
                "admin_username": "admin",
                "admin_password_hash": password_hash,
                "session_secret": "b" * 64,
                "session_lifetime_hours": 8,
                "github_repo": "example/sambora",
                "github_branch": "main",
                "update_check_enabled": False,
                "tls_enabled": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return config_path


def apply_patches() -> None:
    import app.app as app_mod
    import app.routes.dashboard as dashboard
    import app.routes.files_routes as files_routes
    import app.routes.service as service
    import app.routes.shares as shares
    import app.routes.system as system
    import app.routes.users as users

    shares_fn = lambda *_a, **_k: dummy_shares()
    status_fn = lambda: {
        "active": "active",
        "is_running": True,
        "output": (
            "● smbd.service - Samba SMB Daemon\n"
            "     Loaded: loaded (/lib/systemd/system/smbd.service; enabled)\n"
            "     Active: active (running) since Sun 2026-03-15 08:00:00 UTC\n"
            "   Main PID: 1234 (smbd)"
        ),
        "returncode": 0,
    }
    testparm_fn = lambda: {
        "success": True,
        "output": "Load smb config files from /etc/samba/smb.conf\nLoaded services file OK.",
        "returncode": "0",
    }
    users_fn = lambda: ["alice", "bob", "charlie"]
    overview_fn = lambda: (dummy_overview(), None)
    smb_fn = lambda: (dummy_smb_status(), None)
    update_fn = lambda *_a, **_k: dummy_app_update()

    dashboard.read_shares = shares_fn
    dashboard.list_samba_users = users_fn
    dashboard.service_status = status_fn
    dashboard.run_testparm = testparm_fn
    dashboard.get_overview_safe = overview_fn
    dashboard.get_smb_status_safe = smb_fn
    dashboard.INITIAL_PASSWORD_FILE = "/tmp/sambora-demo-no-initial-password.txt"

    shares.read_shares = shares_fn
    users.list_samba_users = users_fn
    files_routes.read_shares = shares_fn
    files_routes.list_directory = dummy_list_directory
    service.service_status = status_fn
    service.run_testparm = testparm_fn
    system.check_upgradable_safe = lambda **_k: ([], None)
    system.get_overview_safe = overview_fn
    system.apt_job_status = lambda: {"status": "idle"}
    system.app_update_job_status = lambda: {"status": "idle"}
    system.get_app_update_info = update_fn
    app_mod.get_app_update_info = update_fn


def start_app(config_path: Path):
    import app.config as config_mod

    config_mod.CONFIG_PATH = config_path
    from app.app import create_app

    flask_app = create_app()
    apply_patches()
    flask_app.config["TESTING"] = True
    from werkzeug.serving import make_server

    server = make_server(HOST, PORT, flask_app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    import urllib.error
    import urllib.request

    deadline = time.time() + 10
    while time.time() < deadline:
        try:
            urllib.request.urlopen(f"{BASE}/login", timeout=0.4)
            return flask_app
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.15)
    raise RuntimeError("Demo-Server startete nicht.")


def capture(page) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    shots = [
        ("/", "Dashboard.png", None),
        ("/shares", "Freigaben.png", None),
        ("/users", "Benutzer.png", None),
        ("/dateien", "Dateien.png", ".files-grid-item, .files-empty, #files-grid"),
        ("/status", "Status.png", None),
        ("/system/updates", "Updates.png", None),
        ("/change-password", "Passwort.png", None),
    ]
    for path, name, wait_sel in shots:
        page.goto(f"{BASE}{path}", wait_until="networkidle")
        page.wait_for_timeout(500)
        if wait_sel:
            page.wait_for_selector(wait_sel, timeout=8000)
            page.wait_for_timeout(400)
        page.evaluate(
            "() => { const el = document.getElementById('files-download-hint'); if (el) el.hidden = true; }"
        )
        dest = OUT_DIR / name
        page.screenshot(path=str(dest), full_page=False)
        print(f"→ {dest.name} ({dest.stat().st_size} bytes)")


def main() -> int:
    os.chdir(ROOT)
    tmp = Path(tempfile.mkdtemp(prefix="sambora-shots-"))
    flask_app = start_app(write_config(tmp))
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            viewport={"width": 1440, "height": 900},
            reduced_motion="reduce",
            color_scheme="dark",
        )
        page = context.new_page()
        page.goto(f"{BASE}/login", wait_until="networkidle")
        page.fill("#username", "admin")
        page.fill("#password", "demo-pass-123")
        page.click("button[type=submit]")
        page.wait_for_url(f"{BASE}/", timeout=15000)
        capture(page)
        browser.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
