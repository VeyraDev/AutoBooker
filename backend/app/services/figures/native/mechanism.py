"""Mechanism Native IR schema helpers。"""

from __future__ import annotations

from typing import Any


def empty_mechanism_ir() -> dict[str, Any]:
    return {
        "type": "mechanism",
        "actors": [],
        "states": [],
        "effects": [],
        "feedbacks": [],
        "causal_links": [],
        "positive_feedbacks": [],
        "negative_feedbacks": [],
        "interactions": [],
        "notations": [],
    }
