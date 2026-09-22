"""smbstatus --json in eine Dashboard-Struktur umwandeln."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass
class SmbConnection:
    user: str
    machine: str
    share: str
    connected_at: str


@dataclass
class SmbStatusSummary:
    connections: list[SmbConnection]
    session_count: int
    open_files_count: int
    version: str


def extract_json_object(text: str) -> dict[str, Any] | None:
    """Erstes JSON-Objekt aus gemischter smbstatus-Ausgabe."""
    if not text:
        return None
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def unique_error_text(*parts: str) -> str:
    seen: set[str] = set()
    lines: list[str] = []
    for part in parts:
        for line in (part or "").splitlines():
            cleaned = line.strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            lines.append(cleaned)
    return "\n".join(lines)


def humanize_smbstatus_error(err: str) -> str:
    low = (err or "").lower()
    if (
        "could not determine network interfaces" in low
        or "interfaces config line" in low
        or "no network interfaces found" in low
    ):
        return (
            "Samba findet keine Netzwerkschnittstellen. "
            "In /etc/samba/smb.conf unter [global] z. B. "
            "interfaces = 127.0.0.0/8 0.0.0.0/0 setzen und smbd neu laden."
        )
    return err.strip() or "smbstatus fehlgeschlagen."


def _session_index(sessions: dict[str, Any]) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for key, session in sessions.items():
        if not isinstance(session, dict):
            continue
        sid = str(session.get("session_id") or key)
        indexed[sid] = session
    return indexed


def parse_smbstatus_json(data: dict[str, Any]) -> SmbStatusSummary:
    sessions = data.get("sessions") or {}
    tcons = data.get("tcons") or {}
    open_files = data.get("open_files") or {}
    if not isinstance(sessions, dict):
        sessions = {}
    if not isinstance(tcons, dict):
        tcons = {}
    if not isinstance(open_files, dict):
        open_files = {}

    session_by_id = _session_index(sessions)
    connections: list[SmbConnection] = []

    for key, tcon in tcons.items():
        if not isinstance(tcon, dict):
            continue
        sid = str(tcon.get("session_id") or "")
        session = session_by_id.get(sid, {})
        user = str(
            session.get("username")
            or session.get("auth_user")
            or tcon.get("username")
            or "—"
        )
        machine = str(
            tcon.get("machine")
            or session.get("remote_machine")
            or session.get("hostname")
            or "—"
        )
        share = str(tcon.get("service") or tcon.get("share") or "—")
        connected_at = str(
            tcon.get("connected_at")
            or tcon.get("creation_time")
            or session.get("creation_time")
            or ""
        )
        connections.append(
            SmbConnection(
                user=user,
                machine=machine,
                share=share,
                connected_at=connected_at,
            )
        )

    if not connections:
        for key, session in sessions.items():
            if not isinstance(session, dict):
                continue
            connections.append(
                SmbConnection(
                    user=str(session.get("username") or session.get("auth_user") or "—"),
                    machine=str(
                        session.get("remote_machine")
                        or session.get("hostname")
                        or "—"
                    ),
                    share="—",
                    connected_at=str(session.get("creation_time") or ""),
                )
            )

    connections.sort(key=lambda item: (item.share.lower(), item.machine.lower(), item.user.lower()))

    return SmbStatusSummary(
        connections=connections,
        session_count=len(sessions),
        open_files_count=len(open_files),
        version=str(data.get("version") or ""),
    )
