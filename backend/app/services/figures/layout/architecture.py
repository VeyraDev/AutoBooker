"""架构图专用布局：分层 / 网关扇出 / 三列。"""
from __future__ import annotations

from app.services.figures.graph.schema import GraphIR, GraphNode
from app.services.figures.layout.schema import LayoutResult, NodePosition
from app.services.figures.layout.sizing import estimate_node_size

_TIER_KEYWORDS = {
    "frontend": ("前端", "frontend", "react", "vue", "客户端", "浏览器"),
    "backend": ("后端", "backend", "api", "fastapi", "服务", "gateway", "网关", "server"),
    "data": ("数据库", "database", "postgres", "mysql", "redis", "存储", "向量"),
}


def _tier_of(node: GraphNode) -> str:
    label = (node.label or "").lower()
    group = (node.group or "").lower()
    for tier, keys in _TIER_KEYWORDS.items():
        if any(k in label or k in group for k in keys):
            return tier
    if "gateway" in (node.kind or ""):
        return "backend"
    if node.kind == "database":
        return "data"
    return "backend"


def layout_architecture(graph: GraphIR) -> LayoutResult:
    nodes = list(graph.nodes)
    if not nodes:
        return LayoutResult(strategy="layered_architecture", direction="TB", node_positions={}, canvas={"width": 800, "height": 500})

    groups = graph.groups or []
    if groups:
        return _layout_by_groups(graph, nodes, groups)

    by_tier: dict[str, list[GraphNode]] = {"frontend": [], "backend": [], "data": []}
    for n in nodes:
        by_tier.setdefault(_tier_of(n), []).append(n)

    if by_tier["frontend"] and (by_tier["backend"] or by_tier["data"]):
        return _layout_three_tier(by_tier)

    if len(by_tier.get("backend") or []) >= 3:
        gw = next((n for n in by_tier["backend"] if any(k in (n.label or "") for k in ("网关", "Gateway", "gateway"))), None)
        if gw:
            return _layout_fanout(graph, nodes, gw)

    hub = _find_hub(graph)
    if hub and len(nodes) >= 3:
        return _layout_fanout(graph, nodes, hub)

    return _layout_horizontal_services(nodes)


def _layout_three_tier(by_tier: dict[str, list[GraphNode]]) -> LayoutResult:
    positions: dict[str, NodePosition] = {}
    max_w = 200.0
    canvas_w, canvas_h = 880.0, 520.0

    fe = by_tier.get("frontend") or []
    be = by_tier.get("backend") or []
    da = by_tier.get("data") or []

    y_fe = 80.0
    for i, n in enumerate(fe):
        w, h = estimate_node_size(n.label, min_width=130.0, max_width=220.0)
        positions[n.id] = NodePosition(id=n.id, x=80.0, y=y_fe + i * (h + 40), width=w, height=h)

    y_be = 60.0
    for i, n in enumerate(be):
        w, h = estimate_node_size(n.label, min_width=130.0, max_width=220.0)
        positions[n.id] = NodePosition(id=n.id, x=480.0, y=y_be + i * (h + 36), width=w, height=h)

    y_da = 340.0
    for i, n in enumerate(da):
        w, h = estimate_node_size(n.label, min_width=130.0, max_width=220.0)
        positions[n.id] = NodePosition(id=n.id, x=480.0, y=y_da + i * (h + 36), width=w, height=h)

    return LayoutResult(
        strategy="layered_architecture",
        direction="LR",
        node_positions=positions,
        canvas={"width": canvas_w, "height": canvas_h},
    )


def _find_hub(graph: GraphIR) -> GraphNode | None:
    out_deg: dict[str, int] = {}
    for e in graph.edges:
        out_deg[e.source] = out_deg.get(e.source, 0) + 1
    if not out_deg:
        return None
    best_id = max(out_deg, key=lambda k: out_deg[k])
    if out_deg[best_id] < 2:
        for n in graph.nodes:
            if any(k in (n.label or "") for k in ("网关", "Gateway", "API")):
                return n
        return None
    for n in graph.nodes:
        if n.id == best_id:
            return n
    return None


def _layout_fanout(graph: GraphIR, nodes: list[GraphNode], hub: GraphNode) -> LayoutResult:
    positions: dict[str, NodePosition] = {}
    hw, hh = estimate_node_size(hub.label, min_width=140.0, max_width=220.0)
    positions[hub.id] = NodePosition(id=hub.id, x=80.0, y=200.0, width=hw, height=hh)

    children = [n for n in nodes if n.id != hub.id]
    y = 60.0
    for n in children:
        w, h = estimate_node_size(n.label, min_width=120.0, max_width=200.0)
        positions[n.id] = NodePosition(id=n.id, x=380.0, y=y, width=w, height=h)
        y += h + 48.0

    return LayoutResult(
        strategy="layered_architecture",
        direction="LR",
        node_positions=positions,
        canvas={"width": 720.0, "height": max(420.0, y + 60)},
    )


def _layout_horizontal_services(nodes: list[GraphNode]) -> LayoutResult:
    positions: dict[str, NodePosition] = {}
    x = 48.0
    max_h = 0.0
    for n in nodes:
        w, h = estimate_node_size(n.label, min_width=110.0, max_width=180.0)
        positions[n.id] = NodePosition(id=n.id, x=x, y=120.0, width=w, height=h)
        x += w + 64.0
        max_h = max(max_h, h)
    return LayoutResult(
        strategy="layered_architecture",
        direction="LR",
        node_positions=positions,
        canvas={"width": max(800.0, x + 48), "height": max_h + 200},
    )


def _layout_by_groups(graph: GraphIR, nodes: list[GraphNode], groups: list) -> LayoutResult:
    positions: dict[str, NodePosition] = {}
    member_to_group: dict[str, str] = {}
    for g in groups:
        if not isinstance(g, dict):
            continue
        gid = str(g.get("id") or g.get("label") or "")
        for m in g.get("members") or g.get("nodes") or []:
            member_to_group[str(m)] = gid

    buckets: dict[str, list[GraphNode]] = {}
    for n in nodes:
        g = n.group or member_to_group.get(n.label) or member_to_group.get(n.id) or "default"
        buckets.setdefault(g, []).append(n)

    col_x = 48.0
    max_y = 0.0
    for _gid, bucket in buckets.items():
        y = 80.0
        for n in bucket:
            w, h = estimate_node_size(n.label, min_width=120.0, max_width=200.0)
            positions[n.id] = NodePosition(id=n.id, x=col_x, y=y, width=w, height=h)
            y += h + 40.0
        max_y = max(max_y, y)
        col_x += 260.0

    return LayoutResult(
        strategy="layered_architecture",
        direction="LR",
        node_positions=positions,
        canvas={"width": col_x + 48, "height": max(400.0, max_y + 48)},
        meta={"groups": [g.get("label") for g in groups if isinstance(g, dict)]},
    )
