"""SwimlaneCompiler：泳道流程 → Native IR。"""

from __future__ import annotations

import re
from typing import Any

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.compiler.base import DiagramCompiler
from app.services.figures.compiler.flow import _build_control_graph, _derive_joins, _slug
from app.services.figures.contracts.geometry_kinds import GEOMETRY_LANES
from app.services.figures.contracts.normalize import normalize_content_brief, normalize_graph_decisions
from app.services.figures.native.base import NativeIR
from app.services.figures.native.swimlane import empty_swimlane_ir
from app.services.figures.schemas.diagram import DiagramIntent


class SwimlaneCompiler(DiagramCompiler):
    def compile(self, brief: VisualBrief, intent: DiagramIntent) -> NativeIR:
        content = normalize_content_brief(brief.diagram_type or intent.diagram_subtype, dict(brief.content_brief or {}))
        ir = empty_swimlane_ir()
        ir["geometry_kind"] = GEOMETRY_LANES
        ir["lanes"] = _extract_lanes(content)
        ir["steps"] = _extract_lane_steps(content, ir["lanes"])
        ir["handoffs"] = list(content.get("handoffs") or content.get("cross_lane_edges") or [])
        ir["parallel_groups"] = list(content.get("parallel_groups") or [])
        ir["decisions"] = normalize_graph_decisions(list(content.get("decisions") or []))
        ir["loops"] = list(content.get("loops") or [])

        flow_ir = {
            "steps": ir["steps"],
            "parallel_groups": ir["parallel_groups"],
            "decisions": ir["decisions"],
            "loops": ir["loops"],
            "dependencies": list(content.get("dependencies") or []),
            "optional_branches": list(content.get("optional_branches") or []),
            "interrupt_branches": list(content.get("interrupt_branches") or []),
            "joins": _derive_joins({"parallel_groups": ir["parallel_groups"]}),
        }
        ir["control_graph"] = _build_control_graph(flow_ir)
        ir["layout_hints"] = ["swimlane"]
        ir["node_lane"] = {s["id"]: s.get("lane", "") for s in ir["steps"] if isinstance(s, dict)}
        return NativeIR(
            diagram_type="swimlane",
            title=brief.title or intent.title or "泳道图",
            structure=ir,
            meta={"geometry_kind": GEOMETRY_LANES},
        ).with_geometry_kind(GEOMETRY_LANES)


def _extract_lanes(content: dict[str, Any]) -> list[dict[str, Any]]:
    lanes: list[dict[str, Any]] = []
    for i, lane in enumerate(content.get("lanes") or []):
        if isinstance(lane, str):
            lanes.append({"id": _slug(lane, i), "label": lane.strip(), "members": []})
        elif isinstance(lane, dict):
            lid = str(lane.get("id") or _slug(str(lane.get("label") or lane.get("name") or f"lane{i}"), i))
            lanes.append({
                "id": lid,
                "label": str(lane.get("label") or lane.get("name") or lid),
                "members": list(lane.get("items") or lane.get("members") or []),
                "role": str(lane.get("role") or ""),
            })
    if not lanes:
        lanes = [
            {"id": "user", "label": "用户", "members": []},
            {"id": "system", "label": "系统", "members": []},
            {"id": "backend", "label": "后台", "members": []},
        ]
    return lanes[:8]


def _extract_lane_steps(content: dict[str, Any], lanes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    lane_ids = [str(l.get("id") or "") for l in lanes]
    lane_by_label = {str(l.get("label") or ""): str(l.get("id") or "") for l in lanes}
    steps: list[dict[str, Any]] = []

    for lane in lanes:
        lid = str(lane.get("id") or "")
        for j, item in enumerate(lane.get("members") or []):
            if isinstance(item, str):
                label = item.strip()
            elif isinstance(item, dict):
                label = str(item.get("label") or item.get("name") or "")
            else:
                continue
            if label:
                sid = _slug(label, len(steps))
                steps.append({"id": sid, "label": label[:16], "lane": lid})

    for i, item in enumerate(content.get("main_flow") or []):
        if isinstance(item, str):
            label = item.strip()
            lane = lane_ids[i % len(lane_ids)] if lane_ids else ""
        elif isinstance(item, dict):
            label = str(item.get("label") or item.get("name") or "").strip()
            lane = str(item.get("lane") or lane_by_label.get(str(item.get("lane_label") or ""), "") or "")
            if not lane and lane_ids:
                lane = lane_ids[i % len(lane_ids)]
        else:
            continue
        if label:
            steps.append({"id": _slug(label, len(steps)), "label": label[:16], "lane": lane})

    if not steps:
        steps = _extract_steps(content)
        for i, step in enumerate(steps):
            if lane_ids:
                step["lane"] = lane_ids[i % len(lane_ids)]
    return steps[:24]
