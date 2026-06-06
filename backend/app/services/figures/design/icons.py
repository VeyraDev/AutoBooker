"""SVG symbol 图标。"""

from __future__ import annotations

ICONS = {
    "database": "🗄",
    "queue": "📨",
    "gateway": "⛩",
    "user": "👤",
    "service": "⚙",
}


def icon_for_kind(kind: str) -> str:
    return ICONS.get(kind, "")
