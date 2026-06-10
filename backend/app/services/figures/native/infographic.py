"""Infographic Native IR schema。"""

from __future__ import annotations

from typing import Any


def empty_infographic_ir() -> dict[str, Any]:
    return {
        "type": "infographic",
        "blocks": [],
        "style_notes": [],
    }
