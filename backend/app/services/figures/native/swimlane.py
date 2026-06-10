"""Swimlane Native IR schema。"""

from __future__ import annotations

from typing import Any


def empty_swimlane_ir() -> dict[str, Any]:
    return {
        "type": "swimlane",
        "lanes": [],
        "steps": [],
        "handoffs": [],
        "control_graph": {"nodes": [], "edges": []},
    }
