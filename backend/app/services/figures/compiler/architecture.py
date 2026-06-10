"""ArchitectureCompiler。"""

from __future__ import annotations

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.compiler.base import DiagramCompiler
from app.services.figures.contracts.field_registry import pick_str
from app.services.figures.contracts.geometry_kinds import GEOMETRY_GRAPH
from app.services.figures.native.architecture import empty_architecture_ir
from app.services.figures.native.base import NativeIR
from app.services.figures.schemas.diagram import DiagramIntent


class ArchitectureCompiler(DiagramCompiler):
    def compile(self, brief: VisualBrief, intent: DiagramIntent) -> NativeIR:
        content = dict(brief.content_brief or {})
        ir = empty_architecture_ir()
        ir["geometry_kind"] = GEOMETRY_GRAPH
        ir["components"] = [
            pick_str(c, "label", str(c)) if isinstance(c, dict) else str(c)
            for c in (content.get("components") or [])
        ]
        ir["containers"] = list(content.get("containers") or [])
        ir["interactions"] = list(content.get("interactions") or [])
        ir["shared_resources"] = list(content.get("shared_resources") or [])
        ir["architecture_pattern"] = str(content.get("architecture_pattern") or "layered")
        ir["pipeline_stages"] = list(content.get("pipeline_stages") or [])
        hints: list[str] = []
        vb = brief.visual_brief or {}
        li = str(vb.get("layout_intent") or "")
        if li in {"dual_column", "left_right_containers", "lr_architecture"} or ir["containers"]:
            hints.append("dual_column")
        else:
            hints.append("layered_architecture")
        if not ir["interactions"] and len(ir["components"]) >= 2:
            ir["interactions"] = _infer_star_interactions(ir["components"])
        ir["layout_hints"] = hints
        if ir["architecture_pattern"] == "pipeline_architecture" and ir["pipeline_stages"]:
            ir["groups"] = [
                {"label": str(stage.get("name") or f"阶段{i+1}"), "members": list(stage.get("components") or [])}
                for i, stage in enumerate(ir["pipeline_stages"])
                if isinstance(stage, dict)
            ]
        return NativeIR(
            diagram_type="shared_architecture",
            title=brief.title or intent.title or "架构图",
            structure=ir,
            meta={"geometry_kind": GEOMETRY_GRAPH},
        ).with_geometry_kind(GEOMETRY_GRAPH)


def _infer_star_interactions(components: list[str]) -> list[dict[str, str]]:
    gateway = next((c for c in components if any(k in c for k in ("网关", "Gateway", "API"))), "")
    if gateway:
        return [{"from": gateway, "to": c, "label": "请求转发"} for c in components if c != gateway]
    if len(components) == 3:
        return [
            {"from": components[0], "to": components[1], "label": "HTTP请求"},
            {"from": components[1], "to": components[2], "label": "数据访问"},
        ]
    out: list[dict[str, str]] = []
    for i in range(len(components) - 1):
        out.append({"from": components[i], "to": components[i + 1], "label": ""})
    return out
