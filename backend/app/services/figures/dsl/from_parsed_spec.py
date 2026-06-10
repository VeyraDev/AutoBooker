"""parsed_spec → DiagramDSL 转换。"""

from __future__ import annotations

import re
from typing import Any

from app.services.figures.intent.taxonomy import subtype_to_diagram_type
from app.services.figures.parse.hygiene import icon_hint
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram
from app.services.figures.schemas.dsl import DiagramDSL, DiagramEdge, DiagramGroup, DiagramNode, slug_id


def build_dsl_from_parsed(
    intent: DiagramIntent,
    parsed: ParsedDiagram,
    *,
    diagram_type: str | None = None,
) -> DiagramDSL:
    spec = parsed.parsed_spec or {}
    dt = diagram_type or intent.diagram_type or subtype_to_diagram_type(intent.diagram_subtype)
    title = str(spec.get("title") or intent.title or "示意图").strip()
    layout_dir = _layout_direction(dt, spec)
    dsl = DiagramDSL(
        diagram_type=dt,
        title=title,
        layout={"direction": layout_dir, "mode": _layout_mode(dt, spec)},
        style={"theme": "modern_blue"},
        confidence=intent.confidence,
        fallback_allowed=intent.fallback_allowed,
    )

    if spec.get("layers"):
        _from_layers(spec, dsl)
    elif spec.get("nodes") and (spec.get("edges") or _nodes_have_layout(spec)):
        _from_graph(spec, dsl)
    elif spec.get("stages"):
        _from_stages(spec, dsl)
    elif spec.get("events"):
        _from_events(spec, dsl)
    elif spec.get("children") or spec.get("root"):
        _from_taxonomy(spec, dsl)
    elif spec.get("columns") or spec.get("blocks"):
        _from_comparison(spec, dsl)
    elif spec.get("nodes") or spec.get("edges"):
        _from_graph(spec, dsl)
    elif spec.get("connections"):
        _from_connections(spec, dsl)

    if not dsl.nodes:
        from app.services.figures.dsl.defaults import default_dsl_for_type

        fallback = default_dsl_for_type(dt, title=title)
        fallback.confidence = intent.confidence
        return fallback

    _ensure_groups(dsl)
    return dsl


def _layout_direction(diagram_type: str, spec: dict[str, Any]) -> str:
    explicit = str(spec.get("layout") or "").upper()
    if explicit in {"TB", "LR", "BT", "RL"}:
        if diagram_type in {"flowchart", "decision_flow"} and explicit == "LR" and len(spec.get("nodes") or spec.get("stages") or []) > 5:
            return "TB"
        return explicit
    defaults = {
        "flowchart": "TB",
        "decision_flow": "TB",
        "architecture": "TB",
        "dataflow": "LR",
        "sequence": "LR",
        "hierarchy": "TB",
        "taxonomy": "TB",
        "comparison": "LR",
        "matrix": "TB",
        "timeline": "LR",
    }
    return defaults.get(diagram_type, "TB")


def _layout_mode(diagram_type: str, spec: dict[str, Any]) -> str:
    if spec.get("layers"):
        return "layered"
    if diagram_type == "decision_flow":
        return "decision"
    if diagram_type == "timeline":
        return "timeline"
    if diagram_type == "taxonomy":
        return "tree"
    if diagram_type == "comparison":
        return "columns"
    if diagram_type == "matrix":
        return "quadrant"
    return "sequential"


def _node_type(label: str, kind: str = "", *, diagram_type: str = "") -> str:
    text = str(label or "").lower()
    if kind in {"start", "end", "process", "decision"}:
        return kind
    if re.search(r"^开始|^start", text):
        return "start"
    if re.search(r"^结束|^完成|^end", text):
        return "end"
    if re.search(r"是否|判断|达标|满足", text):
        return "decision"
    hint = icon_hint(label, kind)
    mapping = {
        "user": "user",
        "data": "database",
        "service": "service",
        "queue": "queue",
        "ai": "model",
        "search": "api",
        "output": "document",
    }
    return mapping.get(hint, "process" if diagram_type in {"flowchart", "decision_flow"} else "service")


def _add_node(dsl: DiagramDSL, label: str, *, nid: str = "", group: str = "", kind: str = "") -> str:
    label = str(label or "").strip()
    if not label:
        return ""
    node_id = nid or slug_id(label)
    existing = {n.id: n for n in dsl.nodes}
    if node_id in existing:
        return node_id
    for n in dsl.nodes:
        if n.label == label:
            return n.id
    ntype = _node_type(label, kind, diagram_type=dsl.diagram_type)
    dsl.nodes.append(
        DiagramNode(
            id=node_id,
            label=label,
            type=ntype,
            group=group,
            icon="auto" if ntype != "decision" else "decision",
        )
    )
    return node_id


def _add_edge(dsl: DiagramDSL, source: str, target: str, *, label: str = "", etype: str = "sync") -> None:
    if not source or not target or source == target:
        return
    key = (source, target, label)
    seen = {(e.source, e.target, e.label) for e in dsl.edges}
    if key in seen:
        return
    edge_type = etype
    if re.search(r"异步|消息|事件|queue|kafka", label, re.I):
        edge_type = "async"
    elif re.search(r"返回|回流|重试|retry|否", label):
        edge_type = "return" if "否" in label else "fallback"
    dsl.edges.append(DiagramEdge(source=source, target=target, label=label, type=edge_type))


def _from_layers(spec: dict[str, Any], dsl: DiagramDSL) -> None:
    for layer in spec.get("layers") or []:
        if not isinstance(layer, dict):
            continue
        layer_label = str(layer.get("label") or "").strip()
        gid = slug_id(layer_label, "layer")
        node_ids: list[str] = []
        for mod in layer.get("modules") or []:
            nid = _add_node(dsl, str(mod), group=layer_label)
            if nid:
                node_ids.append(nid)
        if layer_label and node_ids:
            dsl.groups.append(DiagramGroup(id=gid, label=layer_label, type="layer", nodes=node_ids, layout="row"))
    for conn in spec.get("connections") or []:
        if not isinstance(conn, dict):
            continue
        src = _resolve_ref(dsl, conn.get("from") or conn.get("source"))
        tgt = _resolve_ref(dsl, conn.get("to") or conn.get("target"))
        _add_edge(dsl, src, tgt, label=str(conn.get("label") or ""))


def _nodes_have_layout(spec: dict[str, Any]) -> bool:
    return any(
        isinstance(n, dict) and (n.get("level") is not None or n.get("column") is not None)
        for n in (spec.get("nodes") or [])
    )


def _apply_node_layout(node: DiagramNode, raw: dict[str, Any], *, kind: str = "") -> None:
    try:
        node.level = int(raw.get("level", node.level))
    except (TypeError, ValueError):
        pass
    try:
        node.column = int(raw.get("column", node.column))
    except (TypeError, ValueError):
        pass
    shape = str(raw.get("shape") or "").strip()
    if shape:
        node.shape = shape
    elif kind == "decision":
        node.shape = "diamond"
    if kind == "decision":
        node.type = "decision"
        node.icon = "decision"


def _from_stages(spec: dict[str, Any], dsl: DiagramDSL) -> None:
    stages = [s for s in (spec.get("stages") or []) if isinstance(s, dict)]
    explicit_edges = [e for e in (spec.get("edges") or []) if isinstance(e, dict)]
    feedback = [e for e in (spec.get("feedback") or []) if isinstance(e, dict)]
    branched = bool(explicit_edges) or bool(feedback) or any(
        str(s.get("kind") or "") in {"parallel", "decision"} for s in stages
    )
    prev = ""
    for i, stage in enumerate(stages):
        label = str(stage.get("label") or stage.get("name") or f"步骤{i + 1}")
        kind = str(stage.get("type") or stage.get("kind") or "")
        nid = str(stage.get("id") or f"s{i}")
        added = _add_node(dsl, label, nid=nid, kind=kind)
        for node in dsl.nodes:
            if node.id == added:
                _apply_node_layout(node, stage, kind=kind)
                break
        if not branched and prev and added:
            _add_edge(dsl, prev, added, label=str(stage.get("edge_label") or ""))
        prev = added or prev
    for edge in explicit_edges + feedback:
        src = _resolve_ref(dsl, edge.get("from") or edge.get("source"))
        tgt = _resolve_ref(dsl, edge.get("to") or edge.get("target"))
        _add_edge(dsl, src, tgt, label=str(edge.get("label") or ""))


def _from_events(spec: dict[str, Any], dsl: DiagramDSL) -> None:
    prev = ""
    for i, event in enumerate(spec.get("events") or []):
        if not isinstance(event, dict):
            continue
        label = str(event.get("label") or event.get("event") or f"事件{i + 1}")
        nid = _add_node(dsl, label, nid=f"t{i}")
        if prev and nid:
            _add_edge(dsl, prev, nid)
        prev = nid or prev


def _from_taxonomy(spec: dict[str, Any], dsl: DiagramDSL) -> None:
    if spec.get("nodes") and spec.get("edges"):
        _from_graph(spec, dsl)
        return
    root_label = str(spec.get("root") or spec.get("title") or "核心主题")
    root_id = _add_node(dsl, root_label, nid="root", kind="module")

    def walk_children(parent_id: str, children: list, *, prefix: str) -> None:
        for i, child in enumerate(children):
            if not isinstance(child, dict):
                continue
            cid = _add_node(dsl, str(child.get("label") or f"分支{i + 1}"), nid=f"{prefix}{i}")
            if parent_id and cid:
                _add_edge(dsl, parent_id, cid)
            walk_children(cid, child.get("children") or [], prefix=f"{prefix}{i}_")

    walk_children(root_id, spec.get("children") or [], prefix="c")


def _from_comparison(spec: dict[str, Any], dsl: DiagramDSL) -> None:
    for i, col in enumerate(spec.get("columns") or spec.get("blocks") or []):
        if isinstance(col, dict):
            _add_node(dsl, str(col.get("label") or col.get("title") or f"选项{i + 1}"), nid=f"opt_{i}")
        else:
            _add_node(dsl, str(col), nid=f"opt_{i}")


def _from_graph(spec: dict[str, Any], dsl: DiagramDSL) -> None:
    id_map: dict[str, str] = {}
    for i, node in enumerate(spec.get("nodes") or []):
        if not isinstance(node, dict):
            continue
        label = str(node.get("label") or node.get("name") or f"节点{i + 1}")
        nid = str(node.get("id") or slug_id(label))
        kind = str(node.get("type") or node.get("kind") or "")
        id_map[nid] = _add_node(
            dsl,
            label,
            nid=nid,
            group=str(node.get("group") or node.get("lane") or ""),
            kind=kind,
        )
        id_map[label] = id_map[nid]
        for added in dsl.nodes:
            if added.id == id_map[nid]:
                _apply_node_layout(added, node, kind=kind)
                break
    for edge in spec.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        src = _resolve_ref(dsl, edge.get("from") or edge.get("source"), id_map)
        tgt = _resolve_ref(dsl, edge.get("to") or edge.get("target"), id_map)
        _add_edge(dsl, src, tgt, label=str(edge.get("label") or ""), etype=str(edge.get("type") or "sync"))


def _from_connections(spec: dict[str, Any], dsl: DiagramDSL) -> None:
    entities: set[str] = set()
    for conn in spec.get("connections") or []:
        if not isinstance(conn, dict):
            continue
        entities.add(str(conn.get("from") or ""))
        entities.add(str(conn.get("to") or ""))
    for ent in sorted(x for x in entities if x.strip()):
        _add_node(dsl, ent)
    _from_layers({"layers": spec.get("layers") or [], "connections": spec.get("connections")}, dsl)


def _resolve_ref(dsl: DiagramDSL, ref: Any, id_map: dict[str, str] | None = None) -> str:
    raw = str(ref or "").strip()
    if not raw:
        return ""
    if id_map and raw in id_map:
        return id_map[raw]
    for n in dsl.nodes:
        if n.id == raw or n.label == raw:
            return n.id
    return _add_node(dsl, raw)


def _ensure_groups(dsl: DiagramDSL) -> None:
    grouped: dict[str, list[str]] = {}
    for n in dsl.nodes:
        if n.group:
            grouped.setdefault(n.group, []).append(n.id)
    existing = {g.label for g in dsl.groups}
    for label, nids in grouped.items():
        if label not in existing:
            dsl.groups.append(DiagramGroup(id=slug_id(label, "layer"), label=label, type="layer", nodes=nids, layout="row"))
