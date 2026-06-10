"""DiagramDSL → parsed_spec（薄包装，优先保真字段）。"""

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
        "schema_version": "1.0",
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
        base["layout_result"] = {
            "node_positions": node_positions,
            "canvas": dict(canvas or {}),
            "strategy": dsl.layout.get("mode"),
            "direction": layout_dir,
        }

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
        base["geometry_kind"] = "graph"
        return base

    if dt == "timeline":
        base["geometry_kind"] = "timeline"
        base["events"] = []
        for n in dsl.nodes:
            lc = getattr(n, "layout_constraints", None) or {}
            time_val = lc.get("time", "") if isinstance(lc, dict) else ""
            base["events"].append({"label": n.label, "time": str(time_val or "")})
        _append_nodes_edges(base, dsl, dt)
        return base

    if dt in {"taxonomy", "hierarchy"}:
        root = dsl.nodes[0] if dsl.nodes else None
        base["geometry_kind"] = "tree"
        base["root"] = root.label if root else dsl.title
        base["children"] = _taxonomy_children_from_dsl(dsl, root.id if root else "root")
        _append_nodes_edges(base, dsl, dt)
        return base

    if dt == "comparison":
        base["geometry_kind"] = "matrix"
        base["columns"] = [n.label for n in dsl.nodes if n.type != "module"]
        base["subjects"] = base["columns"]
        _append_nodes_edges(base, dsl, dt)
        return base

    if dt == "infographic" or "infographic" in (dsl.notes or []):
        blocks = []
        for g in dsl.groups:
            blocks.append({"label": g.label, "items": []})
        if not blocks:
            blocks = [{"label": n.label, "items": []} for n in dsl.nodes if n.id != "summary"]
        if blocks:
            base["blocks"] = blocks
            base["extensions"] = {"blocks": blocks}
        base["geometry_kind"] = "blocks"
        _append_nodes_edges(base, dsl, dt)
        base["diagram_subtype"] = "infographic"
        return base

    if dt in {"flowchart", "decision_flow", "dataflow", "sequence"} or dsl.nodes:
        base["geometry_kind"] = "graph"
        _append_nodes_edges(base, dsl, dt)
        if dt in {"flowchart", "decision_flow"}:
            base["stages"] = [{"label": n.label, "id": n.id, "type": n.type} for n in dsl.nodes]
        return base

    base["geometry_kind"] = "graph"
    return base


def _append_nodes_edges(base: dict[str, Any], dsl: DiagramDSL, dt: str) -> None:
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


def _taxonomy_children_from_dsl(dsl: DiagramDSL, root_id: str) -> list[dict[str, Any]]:
    child_map: dict[str, list[str]] = {}
    for edge in dsl.edges:
        child_map.setdefault(edge.source, []).append(edge.target)

    def build_subtree(parent_id: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for cid in child_map.get(parent_id, []):
            label = _label_for(dsl, cid)
            out.append({"label": label, "children": build_subtree(cid)})
        return out

    return build_subtree(root_id)
