"""泳道图布局：按 lane 分行、lane 内 LR 排列。"""

from __future__ import annotations

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult, NodePosition

_LANE_HEADER_H = 36.0
_LANE_PAD_X = 48.0
_LANE_PAD_Y = 24.0
_NODE_GAP_X = 56.0
_LANE_GAP_Y = 20.0


def layout_swimlane(graph: GraphIR) -> LayoutResult:
    lanes: list[dict] = list((graph.layout_constraints or {}).get("lanes") or [])
    node_lane: dict[str, str] = dict((graph.layout_constraints or {}).get("node_lane") or {})
    if not lanes:
        lanes = _infer_lanes(graph, node_lane)

    positions: dict[str, NodePosition] = {}
    y = _LANE_PAD_Y
    lane_height = 72.0

    for lane in lanes:
        lid = str(lane.get("id") or lane.get("label") or "")
        members = [str(m) for m in (lane.get("members") or lane.get("items") or [])]
        if not members:
            members = [n.id for n in graph.nodes if node_lane.get(n.id) == lid]
        x = _LANE_PAD_X
        for mid in members:
            node = next((n for n in graph.nodes if n.id == mid), None)
            if not node:
                continue
            label = str(getattr(node, "label", "") or mid)
            w = min(160.0, max(100.0, len(label) * 14.0))
            h = 48.0
            positions[mid] = NodePosition(id=mid, x=x, y=y + _LANE_HEADER_H, width=w, height=h)
            x += w + _NODE_GAP_X
        lane_height = max(lane_height, _LANE_HEADER_H + 56.0)
        y += lane_height + _LANE_GAP_Y

    for node in graph.nodes:
        if node.id not in positions:
            positions[node.id] = NodePosition(
                id=node.id, x=_LANE_PAD_X, y=y, width=120.0, height=48.0,
            )

    return LayoutResult(
        strategy="swimlane",
        direction="LR",
        node_positions=positions,
        edge_routes=[],
        canvas={"width": 960.0, "height": max(y + 80, 400.0), "padding": _LANE_PAD_X},
        meta={"lanes": lanes},
    )


def _infer_lanes(graph: GraphIR, node_lane: dict[str, str]) -> list[dict]:
    by_lane: dict[str, list[str]] = {}
    for nid, lane in node_lane.items():
        by_lane.setdefault(lane, []).append(nid)
    if by_lane:
        return [{"id": k, "label": k, "members": v} for k, v in by_lane.items()]
    ids = [n.id for n in graph.nodes]
    if not ids:
        return []
    chunk = max(1, len(ids) // 3)
    return [
        {"id": "lane_a", "label": "Lane A", "members": ids[:chunk]},
        {"id": "lane_b", "label": "Lane B", "members": ids[chunk : chunk * 2]},
        {"id": "lane_c", "label": "Lane C", "members": ids[chunk * 2 :]},
    ]
