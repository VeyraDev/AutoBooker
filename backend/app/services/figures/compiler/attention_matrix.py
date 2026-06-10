"""AttentionMatrixCompiler：attention matrix brief → Matrix Native IR。"""

from __future__ import annotations

from typing import Any

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.compiler.base import DiagramCompiler
from app.services.figures.contracts.geometry_kinds import GEOMETRY_MATRIX
from app.services.figures.native.base import NativeIR
from app.services.figures.schemas.diagram import DiagramIntent


class AttentionMatrixCompiler(DiagramCompiler):
    def compile(self, brief: VisualBrief, intent: DiagramIntent) -> NativeIR:
        content = dict(brief.content_brief or {})
        tokens = [str(x).strip() for x in (content.get("tokens") or []) if str(x).strip()]
        size = int(content.get("size") or len(tokens) or 6)
        if not tokens:
            tokens = [f"T{i + 1}" for i in range(size)]
        tokens = tokens[: min(len(tokens), 24)]
        cells = _cells(content.get("cells"), tokens)
        ir = {
            "type": "attention_matrix",
            "geometry_kind": GEOMETRY_MATRIX,
            "subjects": tokens,
            "dimensions": tokens,
            "cells": cells,
            "tokens": tokens,
            "size": len(tokens),
            "window": content.get("window"),
            "comparison_goal": "attention_heatmap",
            "comparison_format": "attention_heatmap",
        }
        return NativeIR(
            diagram_type="attention_matrix",
            title=brief.title or intent.title or "注意力矩阵",
            structure=ir,
            meta={"geometry_kind": GEOMETRY_MATRIX},
        ).with_geometry_kind(GEOMETRY_MATRIX)


def _cells(raw: Any, tokens: list[str]) -> list[dict[str, Any]]:
    if isinstance(raw, list) and raw:
        out: list[dict[str, Any]] = []
        for cell in raw:
            if not isinstance(cell, dict):
                continue
            row = str(cell.get("row") or cell.get("dimension") or "")
            col = str(cell.get("column") or cell.get("subject") or "")
            if row and col:
                out.append({
                    "subject": col,
                    "dimension": row,
                    "row": row,
                    "column": col,
                    "value": cell.get("value", 0.0),
                })
        if out:
            return out
    out = []
    for i, row in enumerate(tokens):
        for j, col in enumerate(tokens):
            out.append({
                "subject": col,
                "dimension": row,
                "row": row,
                "column": col,
                "value": 0.75 if i == j else 0.25,
            })
    return out
