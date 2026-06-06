"""Hub 扇出布局（支持多层后续链路）。"""

from __future__ import annotations

import math
from collections import defaultdict

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult, NodePosition
from app.services.figures.layout.sizing import estimate_node_size

_NODE_W = 116.0
_NODE_H = 46.0
_H_GAP = 48.0
_V_GAP = 80.0
_CANVAS_W = 800.0


def layout_fanout(graph: GraphIR, hub_id: str) -> LayoutResult:
    out_map: dict[str, list[str]] = defaultdict(list)
    in_map: dict[str, list[str]] = defaultdict(list)
    for e in graph.edges:
        out_map[e.source].append(e.target)
        in_map[e.target].append(e.source)

    layers = _bfs_layers(hub_id, out_map, {n.id for n in graph.nodes})
    positions: dict[str, NodePosition] = {}
    sizes = {n.id: estimate_node_size(n.label, min_width=_NODE_W, max_width=220.0) for n in graph.nodes}

    y = 40.0
    for depth, layer_nodes in enumerate(layers):
        if depth == 0:
            _place_row(layer_nodes, y, positions, sizes, hub_scale=1.15)
        elif depth == 1 and len(layer_nodes) <= 6:
            _place_fan_children(layer_nodes, y, positions, sizes, hub_x=_hub_x(positions, hub_id))
        else:
            _place_row(layer_nodes, y, positions, sizes)
        y += max((sizes.get(nid, (_NODE_W, _NODE_H))[1] for nid in layer_nodes), default=_NODE_H) + _V_GAP

    for n in graph.nodes:
        if n.id not in positions:
            w, h = sizes.get(n.id, (_NODE_W, _NODE_H))
            positions[n.id] = NodePosition(id=n.id, x=40, y=y, width=w, height=h)

    canvas_h = max(460.0, max((p.y + p.height for p in positions.values()), default=0.0) + 48.0)
    return LayoutResult(strategy="fanout", direction="TB", node_positions=positions, canvas={"width": _CANVAS_W, "height": canvas_h})


def _bfs_layers(hub_id: str, out_map: dict[str, list[str]], all_ids: set[str]) -> list[list[str]]:
    layers: list[list[str]] = [[hub_id]]
    seen = {hub_id}
    frontier = [hub_id]
    while frontier:
        nxt_layer: list[str] = []
        for nid in frontier:
            for child in out_map.get(nid, []):
                if child not in seen and child in all_ids:
                    seen.add(child)
                    nxt_layer.append(child)
        if not nxt_layer:
            break
        layers.append(nxt_layer)
        frontier = nxt_layer
    remaining = [nid for nid in all_ids if nid not in seen]
    if remaining:
        layers.append(remaining)
    return layers


def _hub_x(positions: dict[str, NodePosition], hub_id: str) -> float:
    pos = positions.get(hub_id)
    return pos.x + pos.width / 2 if pos else _CANVAS_W / 2


def _place_row(
    nodes: list[str],
    y: float,
    positions: dict[str, NodePosition],
    sizes: dict[str, tuple[float, float]],
    *,
    hub_scale: float = 1.0,
) -> None:
    if not nodes:
        return
    widths = [sizes.get(nid, (_NODE_W, _NODE_H))[0] * hub_scale for nid in nodes]
    heights = [sizes.get(nid, (_NODE_W, _NODE_H))[1] * hub_scale for nid in nodes]
    row_h = max(heights, default=_NODE_H)
    span = sum(widths) + max(0, len(nodes) - 1) * _H_GAP
    x = max(32.0, (_CANVAS_W - span) / 2)
    for nid, w, h in zip(nodes, widths, heights):
        positions[nid] = NodePosition(id=nid, x=x, y=y + (row_h - h) / 2, width=w, height=h)
        x += w + _H_GAP


def _place_fan_children(
    children: list[str],
    y: float,
    positions: dict[str, NodePosition],
    sizes: dict[str, tuple[float, float]],
    *,
    hub_x: float,
) -> None:
    n = len(children)
    if n <= 3:
        widths = [sizes.get(nid, (_NODE_W, _NODE_H))[0] for nid in children]
        heights = [sizes.get(nid, (_NODE_W, _NODE_H))[1] for nid in children]
        span = sum(widths) + max(0, n - 1) * _H_GAP
        x = max(32.0, min(_CANVAS_W - span - 32.0, hub_x - span / 2))
        row_h = max(heights, default=_NODE_H)
        for nid, w, h in zip(children, widths, heights):
            positions[nid] = NodePosition(id=nid, x=x, y=y + (row_h - h) / 2, width=w, height=h)
            x += w + _H_GAP
        return
    radius = min(220.0, 80.0 + n * 28.0)
    for i, nid in enumerate(children):
        angle = math.pi * (i + 1) / (n + 1)
        w, h = sizes.get(nid, (_NODE_W, _NODE_H))
        cx = hub_x + radius * math.cos(angle) - w / 2
        cy = y + radius * math.sin(angle) * 0.35
        positions[nid] = NodePosition(id=nid, x=cx, y=cy, width=w, height=h)
