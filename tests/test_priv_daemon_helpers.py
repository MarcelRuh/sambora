"""Tests für Hilfsfunktionen im Privilege-Daemon."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

DAEMON_PATH = Path(__file__).resolve().parents[1] / "scripts" / "simple-samba-ui-priv-daemon.py"


def _load_daemon_module():
    spec = importlib.util.spec_from_file_location("priv_daemon", DAEMON_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules["priv_daemon"] = module
    spec.loader.exec_module(module)
    return module


def test_app_update_job_lock_defined():
    daemon = _load_daemon_module()
    lock = getattr(daemon, "_app_update_job_lock", None)
    assert lock is not None
    assert hasattr(lock, "acquire")


def test_validate_browser_path_allows_share_root_when_equals_base(tmp_path, monkeypatch):
    daemon = _load_daemon_module()
    base = tmp_path / "raid5"
    base.mkdir()

    monkeypatch.setattr(daemon, "get_shares_base", lambda: base)
    monkeypatch.setattr(daemon, "_get_enabled_share_paths", lambda: [base.resolve()])

    resolved = daemon.validate_browser_path(str(base))
    assert resolved == base.resolve()


def test_validate_browser_path_rejects_base_without_share(tmp_path, monkeypatch):
    daemon = _load_daemon_module()
    base = tmp_path / "shares"
    share = base / "data"
    share.mkdir(parents=True)

    monkeypatch.setattr(daemon, "get_shares_base", lambda: base)
    monkeypatch.setattr(daemon, "_get_enabled_share_paths", lambda: [share.resolve()])

    with pytest.raises(ValueError, match="Basisverzeichnis"):
        daemon.validate_browser_path(str(base))


def test_validate_browser_path_rejects_symlink(tmp_path, monkeypatch):
    daemon = _load_daemon_module()
    base = tmp_path / "shares"
    share = base / "data"
    share.mkdir(parents=True)
    secret = tmp_path / "secret"
    secret.mkdir()
    (share / "link").symlink_to(secret)

    monkeypatch.setattr(daemon, "get_shares_base", lambda: base)
    monkeypatch.setattr(daemon, "_get_enabled_share_paths", lambda: [share.resolve()])

    with pytest.raises(ValueError, match="Symbolische Links"):
        daemon.validate_browser_path(str(share / "link"))


def test_collect_download_files_enforces_limits(tmp_path):
    daemon = _load_daemon_module()
    root = tmp_path / "folder"
    root.mkdir()
    for i in range(5):
        (root / f"file{i}.txt").write_text("x", encoding="utf-8")

    files = daemon._collect_download_files(root, max_files=10, max_bytes=1024)
    assert len(files) == 5

    with pytest.raises(ValueError, match="zu viele Dateien"):
        daemon._collect_download_files(root, max_files=3, max_bytes=1024)


def test_cmd_system_reboot_requires_flag(monkeypatch):
    daemon = _load_daemon_module()
    monkeypatch.setattr(daemon, "_reboot_required", lambda: False)
    ok, msg = daemon.cmd_system_reboot()
    assert not ok
    assert "Kein Neustart" in msg


def test_cleanup_stale_staging_removes_old_files(tmp_path, monkeypatch):
    daemon = _load_daemon_module()
    staging = tmp_path / "file-staging"
    jobs = tmp_path / "download-jobs"
    staging.mkdir()
    jobs.mkdir()

    old_file = staging / "upload-old.bin"
    old_file.write_bytes(b"x" * 10)
    old_ts = 1_000_000_000
    import os

    os.utime(old_file, (old_ts, old_ts))

    monkeypatch.setattr(daemon, "FILE_STAGING_DIR", staging)
    monkeypatch.setattr(daemon, "DOWNLOAD_JOBS_DIR", jobs)
    monkeypatch.setattr(daemon, "STAGING_MAX_AGE_SECONDS", 3600)
    monkeypatch.setattr(daemon, "_ensure_file_staging_dir", lambda: None)

    removed_staging, removed_jobs = daemon.cleanup_stale_staging(max_age_seconds=60)
    assert removed_staging == 1
    assert not old_file.exists()
    assert removed_jobs == 0


def test_github_settings_ignore_config_repo(monkeypatch):
    daemon = _load_daemon_module()
    monkeypatch.setattr(
        daemon,
        "load_app_config",
        lambda: {
            "github_repo": "evil/malware",
            "github_branch": "backdoor",
            "source_clone_dir": "/usr/local/src/sambora",
        },
    )
    clone_dir, repo, branch = daemon._github_settings()
    assert clone_dir == daemon.DEFAULT_SOURCE_CLONE_DIR
    assert repo == "MarcelRuh/sambora"
    assert branch == "main"


def test_safe_clone_dir_rejects_escape(tmp_path):
    daemon = _load_daemon_module()
    assert daemon._safe_clone_dir("/tmp/evil") == daemon.DEFAULT_SOURCE_CLONE_DIR
    assert daemon._safe_clone_dir("/usr/local/src/../tmp") == daemon.DEFAULT_SOURCE_CLONE_DIR
    assert daemon._safe_clone_dir("relative") == daemon.DEFAULT_SOURCE_CLONE_DIR
    allowed = daemon._safe_clone_dir("/usr/local/src/sambora")
    assert allowed == Path("/usr/local/src/sambora")


def test_peer_uid_allowed(monkeypatch):
    daemon = _load_daemon_module()

    class FakePw:
        pw_uid = 1001

    monkeypatch.setattr(daemon.pwd, "getpwnam", lambda name: FakePw())
    assert daemon.peer_uid_allowed(1001)
    assert not daemon.peer_uid_allowed(0)
    assert not daemon.peer_uid_allowed(1002)


def test_apply_share_directory_perms_guest_not_world_writable(tmp_path, monkeypatch):
    daemon = _load_daemon_module()
    path = tmp_path / "public"
    path.mkdir()

    class FakePw:
        pw_uid = 65534
        pw_gid = 65534

    monkeypatch.setattr(daemon.pwd, "getpwnam", lambda name: FakePw())
    chowns: list[tuple] = []
    chmods: list[int] = []
    monkeypatch.setattr(daemon.os, "chown", lambda p, uid, gid: chowns.append((uid, gid)))
    monkeypatch.setattr(daemon.os, "chmod", lambda p, mode: chmods.append(mode))

    daemon.apply_share_directory_perms(path, guest_ok=True, valid_users=[])
    assert chmods == [0o2770]
    assert 0o2777 not in chmods
    assert chowns == [(65534, 65534)]


def test_restore_import_sources(tmp_path):
    daemon = _load_daemon_module()
    src = tmp_path / "smb.conf"
    src.write_text("changed\n", encoding="utf-8")
    backup = tmp_path / "smb.conf.bak"
    backup.write_text("original\n", encoding="utf-8")
    daemon._restore_import_sources(None, {src: backup})
    assert src.read_text(encoding="utf-8") == "original\n"


def test_cmd_smb_connections_retries_with_interfaces_override(monkeypatch, tmp_path):
    import json
    import subprocess

    daemon = _load_daemon_module()
    calls: list[list[str]] = []

    def fake_run_cmd(cmd, input_data=None, timeout=120):
        calls.append(list(cmd))
        if "-s" in cmd:
            return subprocess.CompletedProcess(
                cmd, 0, stdout='{"sessions": {}, "tcons": {}, "open_files": {}}\n', stderr=""
            )
        err = "ERROR: Could not determine network interfaces, you must use a interfaces config line\n"
        return subprocess.CompletedProcess(cmd, 1, stdout=err, stderr=err)

    monkeypatch.setattr(daemon, "run_cmd", fake_run_cmd)
    smb_conf = tmp_path / "smb.conf"
    smb_conf.write_text("[global]\nworkgroup = TEST\n", encoding="utf-8")
    monkeypatch.setattr(daemon, "SMB_CONF", smb_conf)

    ok, output = daemon.cmd_smb_connections()
    assert ok
    payload = json.loads(output)
    assert payload["sessions"] == {}
    assert any("-s" in cmd for cmd in calls)
    assert any("--json" in cmd for cmd in calls)


def test_cmd_pdbedit_list_retries_with_interfaces_override(monkeypatch, tmp_path):
    import subprocess

    daemon = _load_daemon_module()
    calls: list[list[str]] = []

    def fake_run_cmd(cmd, input_data=None, timeout=120):
        calls.append(list(cmd))
        if "-s" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="alice:1001:\nbob:1002:\n", stderr="")
        err = "ERROR: Could not determine network interfaces, you must use a interfaces config line\n"
        return subprocess.CompletedProcess(cmd, 1, stdout="", stderr=err)

    monkeypatch.setattr(daemon, "run_cmd", fake_run_cmd)
    smb_conf = tmp_path / "smb.conf"
    smb_conf.write_text("[global]\nworkgroup = TEST\n", encoding="utf-8")
    monkeypatch.setattr(daemon, "SMB_CONF", smb_conf)

    ok, output = daemon.cmd_pdbedit_list()
    assert ok
    assert "alice:1001:" in output
    assert any(cmd[:2] == [daemon.PDBEDIT, "-s"] for cmd in calls)


def test_cmd_pdbedit_list_humanizes_interfaces_error(monkeypatch, tmp_path):
    import subprocess

    daemon = _load_daemon_module()

    def fake_run_cmd(cmd, input_data=None, timeout=120):
        err = "ERROR: Could not determine network interfaces, you must use a interfaces config line\n"
        return subprocess.CompletedProcess(cmd, 1, stdout=err, stderr=err)

    monkeypatch.setattr(daemon, "run_cmd", fake_run_cmd)
    monkeypatch.setattr(daemon, "SMB_CONF", tmp_path / "missing.conf")

    ok, output = daemon.cmd_pdbedit_list()
    assert not ok
    assert "Netzwerkschnittstellen" in output
    assert "ERROR:" not in output


def test_cmd_pdbedit_list_retries_on_warning_and_drops_stderr(monkeypatch, tmp_path):
    import subprocess

    daemon = _load_daemon_module()

    def fake_run_cmd(cmd, input_data=None, timeout=120):
        if "-s" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="alice:1001:\n", stderr="")
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="alice:1001:\n",
            stderr="WARNING: no network interfaces found\n",
        )

    monkeypatch.setattr(daemon, "run_cmd", fake_run_cmd)
    monkeypatch.setattr(daemon, "SMB_CONF", tmp_path / "smb.conf")
    (tmp_path / "smb.conf").write_text("[global]\n", encoding="utf-8")

    ok, output = daemon.cmd_pdbedit_list()
    assert ok
    assert output == "alice:1001:"
    assert "WARNING" not in output


def test_parse_pdbedit_users_ignores_warnings():
    from app.samba import parse_pdbedit_users

    output = (
        "WARNING: no network interfaces found\n"
        "alice:1001:Alice:/home/alice:/usr/sbin/nologin\n"
        "ERROR: Could not determine network interfaces, you must use a interfaces config line\n"
    )
    assert parse_pdbedit_users(output) == ["alice"]
