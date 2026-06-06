"""DiagramDSL → parsed_spec 反向兼容。"""

from __future__ import annotations

from typing import Any

from app.services.figures.schemas.dsl import DiagramDSL


def dsl_to_parsed_spec(dsl: DiagramDSL) -> dict[str, Any]:
    """将 DSL 转回 renderer 可消费的 parsed_spec。"""
    dt = dsl.diagram_type
    layout_dir = str(dsl.layout.get("direction") or "TB").strip().upper()
    if layout_dir == "LAYERED":
        layout_dir = "LR"
    base: dict[str, Any] = {
        "title": dsl.title,
        "layout": layout_dir,
        "diagram_type": dt,
        "notes": list(dsl.notes),
    }

    canvas = dsl.layout.get("canvas") if isinstance(dsl.layout.get("canvas"), dict) else {}
    if canvas:
        base["canvas"] = dict(canvas)
    node_positions = dsl.layout.get("node_positions")
    if isinstance(node_positions, dict) and node_positions:
        base["layout_result"] = {"node_positions": node_positions, "canvas": dict(canvas or {})}

    if dt == "architecture" and dsl.groups:
        base["layers"] = [
            {"label": g.label, "modules": [_label_for(dsl, nid) for nid in g.nodes]}
            for g in dsl.groups
        ]
        base["connections"] = [
            {"from": _label_for(dsl, e.source), "to": _label_for(dsl, e.target), "label": e.label}
            for e in dsl.edges
        ]
        base["groups"] = [g.to_dict() for g in dsl.groups]
        _append_nodes_edges(base, dsl, dt)
        return base

    if dt == "timeline":
        base["events"] = [{"label": n.label, "time": ""} for n in dsl.nodes]
        _append_nodes_edges(base, dsl, dt)
        return base

    if dt in {"taxonomy", "hierarchy"}:
        root = dsl.nodes[0] if dsl.nodes else None
        base["root"] = root.label if root else dsl.title
        base["children"] = [{"label": n.label} for n in dsl.nodes[1:]]
        _append_nodes_edges(base, dsl, dt)
        return base

    if dt == "comparison":
        base["columns"] = [n.label for n in dsl.nodes]
        _append_nodes_edges(base, dsl, dt)
        return base

    if dt in {"flowchart", "decision_flow", "dataflow", "sequence"} or dsl.nodes:
        _append_nodes_edges(base, dsl, dt)
        if dt in {"flowchart", "decision_flow"}:
            base["stages"] = [{"label": n.label, "id": n.id, "type": n.type} for n in dsl.nodes]
        return base

    return base


def _append_nodes_edges(base: dict[str, Any], dsl: DiagramDSL, dt: str) -> None:
    """SVG renderer 依赖 nodes/edges，各图类均保留。"""
    base["nodes"] = [
        {
            "id": n.id,
            "label": n.label,
            "type": n.type,
            "group": n.group,
            "icon": n.icon,
            "level": n.level,
            "column": n.column,
            **({"shape": n.shape} if n.shape else {}),
            **({"color": n.color} if n.color else {}),
        }
        for n in dsl.nodes
    ]
    base["edges"] = [
        {
            "from": e.source,
            "to": e.target,
            "source": e.source,
            "target": e.target,
            "label": e.label,
            "type": e.type,
            **({"routing": e.routing} if e.routing else {}),
            **({"style": e.style} if e.style else {}),
        }
        for e in dsl.edges
    ]
    base["diagram_type"] = dt


def _label_for(dsl: DiagramDSL, node_id: str) -> str:
    for n in dsl.nodes:
        if n.id == node_id:
            return n.label
    return node_id
