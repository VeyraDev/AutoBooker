"""ComparisonCompiler — 内容 IR only。"""

from __future__ import annotations

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.compiler.base import DiagramCompiler
from app.services.figures.contracts.comparison_fill import fill_comparison_cells, infer_comparison_format
from app.services.figures.contracts.geometry_kinds import GEOMETRY_MATRIX
from app.services.figures.contracts.normalize import normalize_content_brief
from app.services.figures.native.base import NativeIR
from app.services.figures.schemas.diagram import DiagramIntent


class ComparisonCompiler(DiagramCompiler):
    def compile(self, brief: VisualBrief, intent: DiagramIntent) -> NativeIR:
        content = normalize_content_brief(brief.diagram_type or intent.diagram_subtype, dict(brief.content_brief or {}))
        vb = brief.visual_brief or {}
        source = " ".join(
            part for part in (
                str(brief.title or intent.title or ""),
                str(vb.get("source_text") or ""),
            )
            if part
        )
        fmt = infer_comparison_format(source, vb) or str(content.get("comparison_format") or "")
        filled = fill_comparison_cells(content, source_text=source)
        if fmt:
            filled["comparison_format"] = fmt
        ir = {
            "type": "comparison_matrix",
            "geometry_kind": GEOMETRY_MATRIX,
            "subjects": list(filled.get("subjects") or []),
            "dimensions": list(filled.get("dimensions") or []),
            "cells": list(filled.get("cells") or []),
            "comparison_goal": str(filled.get("comparison_goal") or content.get("comparison_goal") or "compare"),
            "comparison_format": str(filled.get("comparison_format") or fmt or "matrix"),
        }
        return NativeIR(
            diagram_type="comparison",
            title=brief.title or intent.title or "对比",
            structure=ir,
            meta={"geometry_kind": GEOMETRY_MATRIX},
        ).with_geometry_kind(GEOMETRY_MATRIX)
