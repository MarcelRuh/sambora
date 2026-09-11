"""Tests für System-Übersicht und apt-Cache."""

from __future__ import annotations

from app.system import (
    check_upgradable_safe,
    invalidate_upgradable_cache,
)


def test_check_upgradable_safe_uses_cache(monkeypatch):
    invalidate_upgradable_cache()
    calls = {"n": 0}

    def fake_list():
        calls["n"] += 1
        return ["pkg"], "Listing..."

    monkeypatch.setattr("app.system.apt_list_upgradable", fake_list)
    first, _ = check_upgradable_safe()
    second, _ = check_upgradable_safe()
    assert first == ["pkg"]
    assert second == ["pkg"]
    assert calls["n"] == 1

    third, _ = check_upgradable_safe(force=True)
    assert third == ["pkg"]
    assert calls["n"] == 2
    invalidate_upgradable_cache()
