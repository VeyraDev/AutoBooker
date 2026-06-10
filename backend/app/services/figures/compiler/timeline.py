"""TimelineCompiler。"""

from __future__ import annotations

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.compiler.base import DiagramCompiler
from app.services.figures.contracts.geometry_kinds import GEOMETRY_TIMELINE
from app.services.figures.contracts.normalize import normalize_content_brief
from app.services.figures.native.base import NativeIR
from app.services.figures.schemas.diagram import DiagramIntent


class TimelineCompiler(DiagramCompiler):
    def compile(self, brief: VisualBrief, intent: DiagramIntent) -> NativeIR:
        content = normalize_content_brief(brief.diagram_type or intent.diagram_subtype, dict(brief.content_brief or {}))
        events = list(content.get("events") or [])
        ir = {
            "type": "timeline",
            "geometry_kind": GEOMETRY_TIMELINE,
            "events": events,
            "milestones": events,
            "time_granularity": content.get("time_granularity"),
            "sequence_type": content.get("sequence_type"),
        }
        return NativeIR(
            diagram_type="timeline",
            title=brief.title or intent.title or "时间线",
            structure=ir,
            meta={"geometry_kind": GEOMETRY_TIMELINE},
        ).with_geometry_kind(GEOMETRY_TIMELINE)
