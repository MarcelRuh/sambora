"""Login, Logout und Admin-Passwort."""

from __future__ import annotations

from flask import Flask, flash, redirect, render_template, request, session, url_for

from app.audit import audit_log
from app.auth import (
    attempt_login,
    clear_initial_password_file,
    hash_password,
    initial_password_pending,
    login_required,
    login_user,
    logout_user,
    safe_redirect_target,
    verify_password,
    is_authenticated,
)
from app.config import load_config, save_config
from app.rate_limit import (
    LoginRateLimited,
    check_login_allowed,
    clear_login_failures,
    record_login_failure,
)
from app.validators import ValidationError, validate_password


def register(app: Flask) -> None:
    @app.route("/login", methods=["GET", "POST"])
    def login():
        if is_authenticated():
            if initial_password_pending():
                return redirect(url_for("change_password"))
            return redirect(url_for("index"))
        error = None
        if request.method == "POST":
            username = (request.form.get("username") or "").strip()
            password = request.form.get("password") or ""
            client_ip = request.remote_addr or "unknown"
            try:
                check_login_allowed(client_ip)
            except LoginRateLimited as exc:
                minutes = max(1, (exc.retry_after + 59) // 60)
                error = f"Zu viele Fehlversuche. Bitte in {minutes} Min. erneut versuchen."
                return render_template("login.html", error=error)
            if attempt_login(username, password):
                clear_login_failures(client_ip)
                login_user(username)
                audit_log("auth.login", "success", user=username)
                if initial_password_pending():
                    return redirect(url_for("change_password"))
                next_url = safe_redirect_target(request.args.get("next"), url_for("index"))
                return redirect(next_url)
            record_login_failure(client_ip)
            audit_log("auth.login_failed", f"user={username}", user=username)
            error = "Ungültiger Benutzername oder Passwort."
        return render_template("login.html", error=error)

    @app.route("/logout", methods=["POST"])
    @login_required
    def logout():
        user = session.get("username", "admin")
        logout_user()
        audit_log("auth.logout", user=user)
        return redirect(url_for("login"))

    @app.route("/change-password", methods=["GET", "POST"])
    @login_required
    def change_password():
        error = None
        success = None
        forced = initial_password_pending()
        if request.method == "POST":
            current = request.form.get("current_password") or ""
            new_pw = request.form.get("new_password") or ""
            confirm = request.form.get("confirm_password") or ""
            config = load_config()
            if not verify_password(current, config["admin_password_hash"]):
                error = "Aktuelles Passwort ist falsch."
            elif new_pw != confirm:
                error = "Neue Passwörter stimmen nicht überein."
            elif new_pw == current:
                error = "Das neue Passwort muss sich vom aktuellen unterscheiden."
            else:
                try:
                    validate_password(new_pw, "Neues Passwort")
                    config["admin_password_hash"] = hash_password(new_pw)
                    save_config(config)
                    audit_log("auth.password_changed")
                    clear_initial_password_file()
                    forced = initial_password_pending()
                    if not forced:
                        flash("Admin-Passwort wurde geändert.", "success")
                        return redirect(url_for("index"))
                    success = "Admin-Passwort wurde geändert."
                except ValidationError as exc:
                    error = str(exc)
        return render_template(
            "change_password.html",
            error=error,
            success=success,
            initial_password_exists=forced,
            force_password_change=forced,
        )
