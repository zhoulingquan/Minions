# -*- coding: utf-8 -*-
from __future__ import annotations

from types import SimpleNamespace

from minions.app.auth import AuthMiddleware, is_auth_enabled


def test_explicit_tenancy_requires_auth_before_first_registration(monkeypatch):
    monkeypatch.setenv("MINIONS_TENANCY_ENABLED", "true")
    monkeypatch.delenv("MINIONS_AUTH_ENABLED", raising=False)
    monkeypatch.setattr("minions.app.auth.has_registered_users", lambda: False)
    request = SimpleNamespace(
        method="GET",
        url=SimpleNamespace(path="/api/agents"),
    )

    assert is_auth_enabled() is True
    assert AuthMiddleware._should_skip_auth(request) is False
