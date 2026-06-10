"""SwotCompiler：SWOT content brief → Matrix Native IR。"""

from __future__ import annotations

from typing import Any

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.compiler.base import DiagramCompiler
from app.services.figures.contracts.geometry_kinds import GEOMETRY_MATRIX
from app.services.figures.native.base import NativeIR
from app.services.figures.schemas.diagram import DiagramIntent

_QUADRANTS = (
    ("strengths", "优势"),
    ("weaknesses", "劣势"),
    ("opportunities", "机会"),
    ("threats", "威胁"),
)


class SwotCompiler(DiagramCompiler):
    def compile(self, brief: VisualBrief, intent: DiagramIntent) -> NativeIR:
        content = dict(brief.content_brief or {})
        quadrants = {key: _items(content.get(key), fallback=label) for key, label in _QUADRANTS}
        dimensions = ["要点"]
        subjects = [label for _, label in _QUADRANTS]
        cells = [
            {"subject": label, "dimension": "要点", "value": "；".join(quadrants[key])}
            for key, label in _QUADRANTS
        ]
        ir = {
            "type": "swot",
            "geometry_kind": GEOMETRY_MATRIX,
            "subjects": subjects,
            "dimensions": dimensions,
            "cells": cells,
            "comparison_goal": "quadrant_analysis",
            "comparison_format": "swot",
            **quadrants,
        }
        return NativeIR(
            diagram_type="swot",
            title=brief.title or intent.title or "SWOT 分析",
            structure=ir,
            meta={"geometry_kind": GEOMETRY_MATRIX},
        ).with_geometry_kind(GEOMETRY_MATRIX)


def _items(raw: Any, *, fallback: str) -> list[str]:
    if isinstance(raw, str):
        raw = [raw]
    out = [str(item).strip() for item in (raw or []) if str(item).strip()]
    return out[:4] or [f"{fallback}项"]
