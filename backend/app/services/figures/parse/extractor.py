"""SemanticExtractor — 两阶段语义抽取输出 DiagramDSL。"""

from __future__ import annotations

from typing import Any

from app.services.figures.dsl import build_dsl_from_parsed, default_dsl_for_type
from app.services.figures.dsl.to_parsed_spec import dsl_to_parsed_spec
from app.services.figures.intent.taxonomy import subtype_to_diagram_type
from app.services.figures.parse.hygiene import clean_label, icon_hint
from app.services.figures.parse.registry import parse_diagram_fallback
from app.services.figures.parse.semantic_plan import _validate_semantic, call_semantic_plan
from app.services.figures.plan.render_planner import (
    _apply_topology_layout,
    _rule_based_render_plan,
    _validate_render_plan,
    call_render_planner,
)
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext
from app.services.figures.schemas.dsl import DiagramDSL, DiagramEdge, DiagramGroup, DiagramNode, slug_id

_SIZE_IMPORTANCE = {"sm": 1, "md": 2, "lg": 3}
_LAYOUT_MODE_MAP = {
    "LR": "linear",
    "TB": "layered",
    "LAYERED": "layered",
    "GRID": "grid",
    "RADIAL": "radial",
}


def extract_semantics(ctx: PipelineContext, intent: DiagramIntent) -> DiagramDSL:
    """两阶段语义解构(A) → 渲染规划(B) → 拓扑校正 → DSL。"""
    semantic = call_semantic_plan(ctx, intent)
    if semantic:
        usable, _ = _validate_semantic(semantic)
        if usable:
            render_plan = call_render_planner(semantic, ctx=ctx)
            if render_plan:
                ok, _ = _validate_render_plan(semantic, render_plan)
                if not ok:
                    render_plan = _rule_based_render_plan(semantic)
            else:
                render_plan = _rule_based_render_plan(semantic)
            render_plan = _apply_topology_layout(semantic, render_plan)
            return _thin_sanitize(_render_plan_to_dsl(semantic, render_plan, intent))

    parsed = parse_diagram_fallback(ctx, intent)
    dt = intent.diagram_type or subtype_to_diagram_type(intent.diagram_subtype)
    dsl = build_dsl_from_parsed(intent, parsed, diagram_type=dt)
    dsl = _thin_sanitize(dsl)
    if not dsl.nodes and intent.fallback_allowed:
        dsl = default_dsl_for_type(dt, title=intent.title or dsl.title)
        dsl.confidence = max(0.5, intent.confidence - 0.1)
        dsl.notes.append("fallback_placeholder")
    return dsl


def _render_plan_to_dsl(
    semantic: dict[str, Any],
    render_plan: dict[str, Any],
    intent: DiagramIntent,
) -> DiagramDSL:
    diagram_type = str(semantic.get("diagram_type") or intent.diagram_type or "flowchart")
    layout_dir = str(render_plan.get("layout") or "TB")
    canvas = render_plan.get("canvas") if isinstance(render_plan.get("canvas"), dict) else {}

    entity_by_id = {
        str(e.get("id")): e for e in (semantic.get("entities") or []) if isinstance(e, dict)
    }

    dsl = DiagramDSL(
        diagram_type=diagram_type,
        title=str(semantic.get("title") or intent.title or "示意图"),
        layout={
            "direction": layout_dir,
            "mode": _LAYOUT_MODE_MAP.get(layout_dir.upper(), "layered"),
            "canvas": dict(canvas),
        },
        style={"theme": "modern_blue"},
        confidence=intent.confidence,
        fallback_allowed=intent.fallback_allowed,
        notes=[str(n) for n in (semantic.get("notes") or [])],
    )

    group_labels: dict[str, str] = {}
    for grp in render_plan.get("groups") or []:
        if not isinstance(grp, dict):
            continue
        gid = str(grp.get("id") or "")
        label = str(grp.get("label") or gid)
        if gid:
            group_labels[gid] = label
            dsl.groups.append(
                DiagramGroup(
                    id=gid,
                    label=label,
                    type="layer",
                    nodes=[str(x) for x in (grp.get("node_ids") or [])],
                )
            )

    for node in render_plan.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        eid = str(node.get("entity_id") or "")
        ent = entity_by_id.get(eid, {})
        etype = str(ent.get("type") or "process")
        gid = str(node.get("group_id") or "")
        size = str(node.get("size") or "md")
        dsl.nodes.append(
            DiagramNode(
                id=eid or slug_id(str(node.get("label") or "")),
                label=str(node.get("label") or ent.get("name") or ""),
                type=etype,
                group=group_labels.get(gid, gid),
                icon=icon_hint(str(node.get("label") or ""), etype),
                importance=_SIZE_IMPORTANCE.get(size, 2),
                level=int(node.get("level") or 0),
                column=int(node.get("column") or 0),
                shape=str(node.get("shape") or ""),
                color=str(node.get("color") or ""),
                size=size,
            )
        )

    for edge in render_plan.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        src = str(edge.get("from") or "")
        dst = str(edge.get("to") or "")
        if not src or not dst:
            continue
        style = str(edge.get("style") or "solid")
        edge_type = "async" if style == "dashed" else "sync"
        dsl.edges.append(
            DiagramEdge(
                source=src,
                target=dst,
                label=str(edge.get("label") or ""),
                type=edge_type,
                routing=str(edge.get("routing") or ""),
                style=style,
            )
        )

    if not dsl.edges and len(dsl.nodes) > 1:
        relations = semantic.get("relations") or []
        if relations:
            for rel in relations:
                if not isinstance(rel, dict):
                    continue
                src = str(rel.get("from") or "")
                dst = str(rel.get("to") or "")
                if not src or not dst:
                    continue
                label = str(rel.get("label") or rel.get("verb") or "")
                async_flag = bool(rel.get("async", False))
                style = "dashed" if async_flag else "solid"
                edge_type = "async" if async_flag else "sync"
                if any(k in label for k in ("返回", "重试", "不达标", "未达标")):
                    edge_type = "return"
                    style = "dashed"
                routing = "curved" if edge_type == "return" else ("LR" if layout_dir.upper() == "LR" else "TB")
                dsl.edges.append(
                    DiagramEdge(source=src, target=dst, label=label, type=edge_type, routing=routing, style=style)
                )
        elif diagram_type in {"flowchart", "timeline", "dataflow"}:
            routing = "LR" if layout_dir.upper() == "LR" else "TB"
            for left, right in zip(dsl.nodes, dsl.nodes[1:]):
                dsl.edges.append(DiagramEdge(source=left.id, target=right.id, routing=routing))

    return dsl


def _thin_sanitize(dsl: DiagramDSL) -> DiagramDSL:
    """极薄清洗：仅去空 label、去重边。"""
    clean_nodes: list[DiagramNode] = []
    for node in dsl.nodes:
        label = node.label.strip()
        if not label:
            continue
        cleaned, _ = clean_label(label, max_units=14)
        if cleaned:
            node.label = cleaned
            clean_nodes.append(node)
    dsl.nodes = clean_nodes
    dsl.edges = _dedupe_edges(dsl.edges)
    _ensure_groups_from_nodes(dsl)
    return dsl


def dsl_to_render_spec(dsl: DiagramDSL) -> dict[str, Any]:
    """DSL 转 renderer 可用的 parsed_spec。"""
    return dsl_to_parsed_spec(dsl)


def _dedupe_edges(edges: list[DiagramEdge]) -> list[DiagramEdge]:
    seen: set[tuple[str, str, str]] = set()
    out: list[DiagramEdge] = []
    for e in edges:
        key = (e.source, e.target, e.label)
        if key not in seen and e.source and e.target and e.source != e.target:
            seen.add(key)
            out.append(e)
    return out


def _ensure_groups_from_nodes(dsl: DiagramDSL) -> None:
    grouped: dict[str, list[str]] = {}
    for n in dsl.nodes:
        if n.group:
            grouped.setdefault(n.group, []).append(n.id)
    existing = {g.label for g in dsl.groups}
    for label, nids in grouped.items():
        if label not in existing:
            dsl.groups.append(DiagramGroup(id=slug_id(label, "layer"), label=label, type="layer", nodes=nids))
