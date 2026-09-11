#!/usr/bin/env python3
"""Liest das Admin-Passwort von stdin und schreibt einen bcrypt-Hash nach stdout."""

from __future__ import annotations

import sys

import bcrypt


def hash_admin_password(password: bytes, *, rounds: int = 12) -> str:
    secret = password.rstrip(b"\r\n")
    if not secret:
        raise SystemExit("Passwort darf nicht leer sein.")
    return bcrypt.hashpw(secret, bcrypt.gensalt(rounds=rounds)).decode("utf-8")


def main() -> int:
    print(hash_admin_password(sys.stdin.buffer.read()), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
