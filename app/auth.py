"""Authentifizierung und Session-Verwaltung."""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Callable

import bcrypt
from flask import Flask, jsonify, redirect, request, session, url_for

from app.config import load_config

_LOG = logging.getLogger(__name__)
INITIAL_PASSWORD_FILE = "/etc/simple-samba-ui/initial-password.txt"
_PASSWORD_CHANGE_EXEMPT = frozenset({"login", "logout", "change_password", "static"})


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def configure_session(app: Flask) -> None:
    config = load_config()
    app.secret_key = config["session_secret"]
    lifetime = int(config.get("session_lifetime_hours", 8))
    app.permanent_session_lifetime = timedelta(hours=lifetime)
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Strict"
    app.config["SESSION_COOKIE_SECURE"] = False

    @app.before_request
    def _session_security() -> None:
        session.permanent = True
        secure = request.is_secure
        try:
            cfg = load_config()
            secure = secure or bool(cfg.get("tls_enabled"))
        except Exception:
            pass
        app.config["SESSION_COOKIE_SECURE"] = secure


def login_user(username: str) -> None:
    session.clear()
    session["authenticated"] = True
    session["username"] = username
    session["login_at"] = datetime.now(timezone.utc).isoformat()


def logout_user() -> None:
    session.clear()


def is_authenticated() -> bool:
    if not session.get("authenticated"):
        return False
    config = load_config()
    lifetime = timedelta(hours=int(config.get("session_lifetime_hours", 8)))
    login_at_raw = session.get("login_at")
    if not login_at_raw:
        return False
    try:
        login_at = datetime.fromisoformat(login_at_raw)
    except ValueError:
        return False
    if datetime.now(timezone.utc) - login_at > lifetime:
        session.clear()
        return False
    return True


def initial_password_pending() -> bool:
    path = Path(INITIAL_PASSWORD_FILE)
    try:
        if not path.is_file():
            return False
        return bool(path.read_text(encoding="utf-8").strip())
    except OSError:
        return False


def clear_initial_password_file() -> bool:
    path = Path(INITIAL_PASSWORD_FILE)
    try:
        path.unlink(missing_ok=True)
        if not path.exists():
            return True
    except OSError as exc:
        _LOG.warning("initial-password.txt nicht löschbar: %s", exc)
    try:
        path.write_text("", encoding="utf-8")
        os.chmod(path, 0o600)
        return not bool(path.read_text(encoding="utf-8").strip())
    except OSError as exc:
        _LOG.warning("initial-password.txt nicht leeren: %s", exc)
        return False


def password_change_required() -> bool:
    return is_authenticated() and initial_password_pending()


def read_reauth_password() -> str:
    data = request.get_json(silent=True)
    if isinstance(data, dict):
        raw = data.get("password") or data.get("confirm_password")
        if raw:
            return str(raw)
    return (
        request.form.get("confirm_password")
        or request.form.get("admin_password")
        or ""
    )


def verify_admin_reauth(password: str | None = None) -> bool:
    secret = read_reauth_password() if password is None else password
    if not secret:
        return False
    config = load_config()
    return verify_password(secret, config["admin_password_hash"])


def reauth_failure_response():
    return jsonify({"ok": False, "error": "Admin-Passwort erforderlich."}), 403


def enforce_password_change():
    if request.endpoint in _PASSWORD_CHANGE_EXEMPT or request.endpoint is None:
        return None
    if not password_change_required():
        return None
    if request.path.startswith("/api/") or request.is_json:
        return jsonify({
            "ok": False,
            "error": "Admin-Passwort muss zuerst geändert werden.",
            "code": "password_change_required",
        }), 403
    return redirect(url_for("change_password"))


def login_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not is_authenticated():
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def attempt_login(username: str, password: str) -> bool:
    config = load_config()
    if username != config.get("admin_username", "admin"):
        return False
    return verify_password(password, config["admin_password_hash"])


def safe_redirect_target(next_url: str | None, default: str) -> str:
    """Erlaubt nur relative Pfade ohne Open-Redirect (z. B. //evil.example)."""
    if not next_url:
        return default
    target = next_url.strip()
    if not target.startswith("/") or target.startswith("//") or target.startswith("/\\"):
        return default
    return target
