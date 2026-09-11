"""Tests für smbstatus JSON Parser."""

from __future__ import annotations

from app.smbstatus_parser import (
    extract_json_object,
    humanize_smbstatus_error,
    parse_smbstatus_json,
    unique_error_text,
)


def test_parse_smbstatus_json_empty():
    summary = parse_smbstatus_json({
        "version": "4.22.8",
        "sessions": {},
        "tcons": {},
        "open_files": {},
    })
    assert summary.session_count == 0
    assert summary.open_files_count == 0
    assert summary.connections == []
    assert summary.version == "4.22.8"


def test_parse_smbstatus_json_with_tcons():
    summary = parse_smbstatus_json({
        "version": "4.22.8",
        "sessions": {
            "1": {
                "session_id": 1,
                "username": "alice",
                "remote_machine": "192.168.1.10",
                "hostname": "PC-01",
            }
        },
        "tcons": {
            "9": {
                "session_id": 1,
                "service": "data",
                "machine": "192.168.1.10",
                "connected_at": "2026-07-07T12:34:56",
            }
        },
        "open_files": {
            "42": {"name": "doc.pdf"}
        },
    })
    assert summary.session_count == 1
    assert summary.open_files_count == 1
    assert len(summary.connections) == 1
    conn = summary.connections[0]
    assert conn.user == "alice"
    assert conn.machine == "192.168.1.10"
    assert conn.share == "data"
    assert conn.connected_at == "2026-07-07T12:34:56"


def test_parse_smbstatus_json_sessions_only():
    summary = parse_smbstatus_json({
        "sessions": {
            "2": {
                "username": "bob",
                "hostname": "NAS-CLIENT",
            }
        },
        "tcons": {},
        "open_files": {},
    })
    assert len(summary.connections) == 1
    assert summary.connections[0].user == "bob"
    assert summary.connections[0].machine == "NAS-CLIENT"
    assert summary.connections[0].share == "—"


def test_extract_json_object_from_mixed_output():
    mixed = (
        "ERROR: Could not determine network interfaces, you must use a interfaces config line\n"
        '{"sessions": {}, "tcons": {}, "open_files": {}}\n'
    )
    data = extract_json_object(mixed)
    assert data == {"sessions": {}, "tcons": {}, "open_files": {}}
    assert extract_json_object("kein json") is None


def test_unique_error_text_dedupes_duplicate_lines():
    msg = "ERROR: Could not determine network interfaces, you must use a interfaces config line"
    assert unique_error_text(msg, msg) == msg
    assert unique_error_text(msg + "\n" + msg, "") == msg


def test_humanize_smbstatus_interfaces_error():
    raw = (
        "ERROR: Could not determine network interfaces, you must use a interfaces config line "
        "ERROR: Could not determine network interfaces, you must use a interfaces config line"
    )
    text = humanize_smbstatus_error(raw)
    assert "Netzwerkschnittstellen" in text
    assert "interfaces =" in text
    assert "ERROR:" not in text

