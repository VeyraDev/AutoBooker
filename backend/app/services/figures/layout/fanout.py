"""Hub 扇出布局（支持多层后续链路）。"""

from __future__ import annotations

import math
from collections import defaultdict

from app.services.figures.graph.schema import GraphIR
from app.services.figures.layout.schema import LayoutResult, NodePosition

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

    for depth, layer_nodes in enumerate(layers):
        y = 40.0 + depth * (_NODE_H + _V_GAP)
        if depth == 0:
            _place_row(layer_nodes, y, positions, hub_scale=1.15)
        elif depth == 1 and len(layer_nodes) <= 6:
            _place_fan_children(layer_nodes, y, positions, hub_x=_hub_x(positions, hub_id))
        else:
            _place_row(layer_nodes, y, positions)

    for n in graph.nodes:
        if n.id not in positions:
            positions[n.id] = NodePosition(id=n.id, x=40, y=40 + len(layers) * (_NODE_H + _V_GAP), width=_NODE_W, height=_NODE_H)

    return LayoutResult(strategy="fanout", direction="TB", node_positions=positions)


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


def _place_row(nodes: list[str], y: float, positions: dict[str, NodePosition], *, hub_scale: float = 1.0) -> None:
    if not nodes:
        return
    w = _NODE_W * hub_scale if hub_scale != 1.0 else _NODE_W
    span = len(nodes) * w + max(0, len(nodes) - 1) * _H_GAP
    x = max(32.0, (_CANVAS_W - span) / 2)
    for nid in nodes:
        positions[nid] = NodePosition(id=nid, x=x, y=y, width=w, height=_NODE_H * (hub_scale if hub_scale != 1.0 else 1.0))
        x += w + _H_GAP


def _place_fan_children(children: list[str], y: float, positions: dict[str, NodePosition], *, hub_x: float) -> None:
    n = len(children)
    if n == 1:
        positions[children[0]] = NodePosition(id=children[0], x=hub_x - _NODE_W / 2, y=y, width=_NODE_W, height=_NODE_H)
        return
    if n == 2:
        positions[children[0]] = NodePosition(id=children[0], x=hub_x - _NODE_W - _H_GAP, y=y, width=_NODE_W, height=_NODE_H)
        positions[children[1]] = NodePosition(id=children[1], x=hub_x + _H_GAP, y=y, width=_NODE_W, height=_NODE_H)
        return
    if n == 3:
        positions[children[0]] = NodePosition(id=children[0], x=hub_x - _NODE_W - _H_GAP, y=y, width=_NODE_W, height=_NODE_H)
        positions[children[1]] = NodePosition(id=children[1], x=hub_x - _NODE_W / 2, y=y + 24, width=_NODE_W, height=_NODE_H)
        positions[children[2]] = NodePosition(id=children[2], x=hub_x + _H_GAP, y=y, width=_NODE_W, height=_NODE_H)
        return
    radius = min(220.0, 80.0 + n * 28.0)
    for i, nid in enumerate(children):
        angle = math.pi * (i + 1) / (n + 1)
        cx = hub_x + radius * math.cos(angle) - _NODE_W / 2
        cy = y + radius * math.sin(angle) * 0.35
        positions[nid] = NodePosition(id=nid, x=cx, y=cy, width=_NODE_W, height=_NODE_H)
