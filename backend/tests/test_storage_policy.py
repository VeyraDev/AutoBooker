"""Storage policy unit tests."""

from __future__ import annotations

from app.services.storage_policy import local_business_storage_allowed


def test_local_business_storage_disabled_by_default(monkeypatch):
    monkeypatch.setattr("app.services.storage_policy.settings.ALLOW_LOCAL_BUSINESS_STORAGE", False)
    monkeypatch.setattr("app.services.storage_policy.settings.ASSETS_COMPAT_STATIC", False)
    assert local_business_storage_allowed() is False


def test_local_business_storage_compat_flag(monkeypatch):
    monkeypatch.setattr("app.services.storage_policy.settings.ALLOW_LOCAL_BUSINESS_STORAGE", False)
    monkeypatch.setattr("app.services.storage_policy.settings.ASSETS_COMPAT_STATIC", True)
    assert local_business_storage_allowed() is True
