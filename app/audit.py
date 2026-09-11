"""Audit-Protokoll für Admin-Aktionen."""

from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

AUDIT_LOG_PATH = Path("/var/log/simple-samba-ui/audit.log")
MAX_READ_LINES = 500
MAX_LOG_BYTES = 5 * 1024 * 1024
_READ_CHUNK = 8192
_LOG = logging.getLogger(__name__)

ACTION_LABELS: dict[str, str] = {
    "auth.login": "Anmeldung",
    "auth.login_failed": "Anmeldung fehlgeschlagen",
    "auth.logout": "Abmeldung",
    "auth.password_changed": "Admin-Passwort geändert",
    "share.create": "Freigabe erstellt",
    "share.update": "Freigabe bearbeitet",
    "share.delete": "Freigabe gelöscht",
    "share.import": "Freigaben importiert",
    "share.toggle": "Freigabe ein/aus",
    "user.create": "Benutzer angelegt",
    "user.password": "Benutzer-Passwort geändert",
    "user.delete": "Benutzer gelöscht",
    "file.upload": "Datei hochgeladen",
    "file.mkdir": "Ordner erstellt",
    "file.delete": "Datei/Ordner gelöscht",
    "service.reload": "Samba neu geladen",
    "service.restart": "Samba neu gestartet",
    "system.apt_update": "Paketlisten aktualisiert",
    "system.app_update": "App-Update gestartet",
    "system.reboot": "System-Neustart",
    "backup.restore": "Backup wiederhergestellt",
}


def action_label(action: str) -> str:
    return ACTION_LABELS.get(action, action)


def _actor(user: str | None) -> str:
    if user:
        return user
    try:
        from flask import has_request_context, session

        if has_request_context():
            return str(session.get("username") or "admin")
    except Exception:
        pass
    return "system"


def _rotate_if_needed() -> None:
    try:
        if not AUDIT_LOG_PATH.is_file():
            return
        if AUDIT_LOG_PATH.stat().st_size < MAX_LOG_BYTES:
            return
        rotated = AUDIT_LOG_PATH.with_name(AUDIT_LOG_PATH.name + ".1")
        if rotated.exists():
            rotated.unlink()
        AUDIT_LOG_PATH.replace(rotated)
        os.chmod(rotated, 0o640)
    except OSError as exc:
        _LOG.warning("Audit-Log Rotation fehlgeschlagen: %s", exc)


def audit_log(action: str, detail: str = "", *, user: str | None = None) -> None:
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "user": _actor(user),
        "action": action,
        "detail": detail,
    }
    try:
        AUDIT_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        _rotate_if_needed()
        line = json.dumps(entry, ensure_ascii=False) + "\n"
        with AUDIT_LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(line)
        os.chmod(AUDIT_LOG_PATH, 0o640)
    except OSError as exc:
        _LOG.warning("Audit-Log nicht schreibbar (%s): %s", AUDIT_LOG_PATH, exc)


def _tail_lines(path: Path, limit: int) -> list[str]:
    if limit <= 0:
        return []
    try:
        with path.open("rb") as fh:
            fh.seek(0, os.SEEK_END)
            pos = fh.tell()
            buffer = b""
            while pos > 0 and buffer.count(b"\n") <= limit:
                read_size = min(_READ_CHUNK, pos)
                pos -= read_size
                fh.seek(pos)
                buffer = fh.read(read_size) + buffer
    except OSError:
        return []
    text = buffer.decode("utf-8", errors="replace")
    return text.splitlines()[-limit:]


def read_audit_log(limit: int = MAX_READ_LINES) -> list[dict[str, Any]]:
    if not AUDIT_LOG_PATH.is_file():
        return []
    entries: list[dict[str, Any]] = []
    for line in _tail_lines(AUDIT_LOG_PATH, max(1, int(limit))):
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            if isinstance(data, dict):
                entries.append(data)
        except json.JSONDecodeError:
            continue
    entries.reverse()
    return entries
