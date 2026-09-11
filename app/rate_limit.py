"""Login-Rate-Limit gegen Brute-Force."""

from __future__ import annotations

import fcntl
import json
import os
import time
from pathlib import Path
from typing import Any

from app import config as app_config

MAX_FAILURES = 5
WINDOW_SECONDS = 900
LOCKOUT_SECONDS = 900


class LoginRateLimited(Exception):
    def __init__(self, retry_after: int) -> None:
        super().__init__("Zu viele Fehlversuche.")
        self.retry_after = max(1, int(retry_after))


def attempts_path() -> Path:
    return app_config.CONFIG_PATH.parent / "login_attempts.json"


def _empty_store() -> dict[str, Any]:
    return {}


def _load_locked(fh) -> dict[str, Any]:
    fh.seek(0)
    raw = fh.read()
    if not raw.strip():
        return _empty_store()
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return _empty_store()
    return data if isinstance(data, dict) else _empty_store()


def _write_locked(fh, data: dict[str, Any]) -> None:
    fh.seek(0)
    fh.truncate()
    json.dump(data, fh, ensure_ascii=False)
    fh.write("\n")
    fh.flush()
    os.fsync(fh.fileno())


def _with_store(mutator):
    path = attempts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+", encoding="utf-8") as fh:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
        try:
            os.chmod(path, 0o600)
        except OSError:
            pass
        store = _load_locked(fh)
        result = mutator(store)
        _write_locked(fh, store)
        return result


def check_login_allowed(ip: str) -> None:
    now = time.time()
    key = ip or "unknown"

    def mutate(store: dict[str, Any]):
        entry = store.get(key) or {}
        locked_until = float(entry.get("locked_until") or 0)
        if locked_until > now:
            raise LoginRateLimited(int(locked_until - now))
        if locked_until and locked_until <= now:
            store.pop(key, None)
        return None

    _with_store(mutate)


def record_login_failure(ip: str) -> None:
    now = time.time()
    key = ip or "unknown"

    def mutate(store: dict[str, Any]):
        entry = store.get(key) or {}
        locked_until = float(entry.get("locked_until") or 0)
        if locked_until > now:
            return None
        first = float(entry.get("first") or now)
        failures = int(entry.get("failures") or 0)
        if now - first > WINDOW_SECONDS:
            first = now
            failures = 0
        failures += 1
        updated = {"first": first, "failures": failures, "locked_until": 0}
        if failures >= MAX_FAILURES:
            updated["locked_until"] = now + LOCKOUT_SECONDS
        store[key] = updated
        return None

    _with_store(mutate)


def clear_login_failures(ip: str) -> None:
    key = ip or "unknown"

    def mutate(store: dict[str, Any]):
        store.pop(key, None)
        return None

    _with_store(mutate)
