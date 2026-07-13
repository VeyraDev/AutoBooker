"""Central policy for whether local business directories may be read/written."""

from __future__ import annotations

from app.config import settings


def local_business_storage_allowed() -> bool:
    """True only for legacy dev/migration; production must use PostgreSQL binary_assets."""
    return bool(settings.ALLOW_LOCAL_BUSINESS_STORAGE or settings.ASSETS_COMPAT_STATIC)
