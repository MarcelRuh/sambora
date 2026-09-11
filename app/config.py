"""Konfigurationsverwaltung für Sambora."""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

CONFIG_PATH = Path("/etc/simple-samba-ui/config.json")

DEFAULT_MAX_UPLOAD_BYTES = 512 * 1024 * 1024
DEFAULT_MAX_FOLDER_DOWNLOAD_FILES = 5000
DEFAULT_MAX_FOLDER_DOWNLOAD_BYTES = 20 * 1024 * 1024 * 1024

DEFAULT_CONFIG: dict[str, Any] = {
    "bind_host": "127.0.0.1",
    "bind_port": 8443,
    "http_port": 8080,
    "shares_base_path": "/srv/shares",
    "samba_shares_file": "/etc/samba/smb-shares.conf",
    "admin_username": "admin",
    "admin_password_hash": "",
    "session_secret": "",
    "session_lifetime_hours": 8,
    "github_repo": "MarcelRuh/sambora",
    "github_branch": "main",
    "update_check_enabled": True,
    "update_check_interval_hours": 6,
    "source_clone_dir": "/usr/local/src/sambora",
    "max_upload_bytes": DEFAULT_MAX_UPLOAD_BYTES,
    "max_folder_download_files": DEFAULT_MAX_FOLDER_DOWNLOAD_FILES,
    "max_folder_download_bytes": DEFAULT_MAX_FOLDER_DOWNLOAD_BYTES,
    "tls_enabled": True,
    "tls_cert_file": "/etc/simple-samba-ui/tls/server.crt",
    "tls_key_file": "/etc/simple-samba-ui/tls/server.key",
    "public_hostname": "",
}


class ConfigError(Exception):
    """Fehler beim Laden oder Speichern der Konfiguration."""


def pin_github_source(data: dict[str, Any]) -> dict[str, Any]:
    """Update-Quelle ist fest – Config darf das Repo nicht umbiegen."""
    data["github_repo"] = DEFAULT_CONFIG["github_repo"]
    data["github_branch"] = DEFAULT_CONFIG["github_branch"]
    return data


def load_config() -> dict[str, Any]:
    if not CONFIG_PATH.is_file():
        raise ConfigError(f"Konfigurationsdatei nicht gefunden: {CONFIG_PATH}")
    try:
        with CONFIG_PATH.open(encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError(f"Konfiguration unlesbar: {exc}") from exc

    merged = pin_github_source({**DEFAULT_CONFIG, **data})
    if not merged.get("session_secret"):
        raise ConfigError("session_secret fehlt in der Konfiguration")
    if not merged.get("admin_password_hash"):
        raise ConfigError("admin_password_hash fehlt in der Konfiguration")
    return merged


def save_config(data: dict[str, Any]) -> None:
    data = pin_github_source(dict(data))
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = CONFIG_PATH.with_suffix(".json.tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2, ensure_ascii=False)
        fh.write("\n")
    os.chmod(tmp, 0o600)
    tmp.replace(CONFIG_PATH)


def generate_session_secret() -> str:
    return secrets.token_hex(32)
