"""调用 B：渲染规划 — layout/nodes/edges/groups/canvas。"""

from __future__ import annotations

import json
import logging
import re
from collections import deque
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.prompts import format_prompt
from app.services.figures.schemas.diagram import PipelineContext
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

_VALID_LAYOUTS = frozenset({"LR", "TB", "LAYERED", "GRID", "RADIAL"})
_VALID_ROUTING = frozenset({"LR", "TB", "side", "curved"})
_VALID_SHAPES = frozenset({"rounded", "box", "diamond", "pill", "cylinder"})
_VALID_COLORS = frozenset({"blue", "teal", "amber", "purple", "coral", "gray", "green"})
_TYPE_SHAPE = {
    "service": "rounded",
    "gateway": "rounded",
    "user": "pill",
    "external": "pill",
    "database": "cylinder",
    "data": "cylinder",
    "process": "box",
    "decision": "diamond",
    "module": "rounded",
    "queue": "cylinder",
}
_TYPE_COLOR = {
    "service": "blue",
    "gateway": "blue",
    "database": "teal",
    "data": "teal",
    "user": "purple",
    "decision": "amber",
}
_GROUP_COLORS = ["blue", "teal", "purple", "amber", "coral", "green"]
_FEEDBACK_RE = re.compile(r"返回|重试|不达标|未达标|回流|retry|fail|否", re.I)
_FLOW_TYPES = frozenset({"flowchart", "decision_flow", "dataflow", "timeline"})


def _is_feedback_relation(rel: dict[str, Any]) -> bool:
    text = f"{rel.get('label', '')} {rel.get('verb', '')}"
    return bool(_FEEDBACK_RE.search(str(text)))


def _graph_has_branching(relations: list[dict[str, Any]]) -> bool:
    out_deg: dict[str, int] = {}
    in_deg: dict[str, int] = {}
    for rel in relations:
        src = str(rel.get("from") or "")
        dst = str(rel.get("to") or "")
        if not src or not dst or _is_feedback_relation(rel):
            continue
        out_deg[src] = out_deg.get(src, 0) + 1
        in_deg[dst] = in_deg.get(dst, 0) + 1
    return any(c > 1 for c in out_deg.values()) or any(c > 1 for c in in_deg.values())


def _relations_topology(
    entities: list[dict[str, Any]],
    relations: list[dict[str, Any]],
) -> tuple[dict[str, tuple[int, int]], str]:
    """根据 relations 拓扑计算 level/column 与 layout（不依赖 LLM 坐标）。"""
    ids = [str(e.get("id") or "") for e in entities if str(e.get("id") or "")]
    id_set = set(ids)
    if not ids:
        return {}, "TB"

    forward: list[tuple[str, str]] = []
    has_feedback = False
    for rel in relations:
        src = str(rel.get("from") or "")
        dst = str(rel.get("to") or "")
        if src not in id_set or dst not in id_set or src == dst:
            continue
        if _is_feedback_relation(rel):
            has_feedback = True
            continue
        forward.append((src, dst))

    in_deg = {i: 0 for i in ids}
    succ: dict[str, list[str]] = {i: [] for i in ids}
    for src, dst in forward:
        succ[src].append(dst)
        in_deg[dst] = in_deg.get(dst, 0) + 1

    roots = [i for i in ids if in_deg.get(i, 0) == 0] or [ids[0]]
    level: dict[str, int] = {i: 0 for i in ids}
    q: deque[str] = deque(roots)
    visited: set[str] = set(roots)
    while q:
        cur = q.popleft()
        for child in succ.get(cur, []):
            level[child] = max(level.get(child, 0), level[cur] + 1)
            in_deg[child] -= 1
            if in_deg[child] <= 0 and child not in visited:
                visited.add(child)
                q.append(child)

    by_level: dict[int, list[str]] = {}
    for eid in ids:
        by_level.setdefault(level.get(eid, 0), []).append(eid)

    positions: dict[str, tuple[int, int]] = {}
    for lv in sorted(by_level):
        group = by_level[lv]
        order = sorted(group, key=lambda x: ids.index(x))
        for col, eid in enumerate(order):
            positions[eid] = (lv, col)

    has_decision = any(str(e.get("type")) == "decision" for e in entities)
    branching = _graph_has_branching(relations) or len(roots) > 1
    # 书稿内页优先竖向排版，避免 ≤5 节点流程被拉成 3:1+ 横条
    layout = "TB"
    return positions, layout


def _routing_for_edge(
    layout: str,
    src_pos: tuple[int, int],
    dst_pos: tuple[int, int],
    *,
    is_feedback: bool,
) -> str:
    if is_feedback:
        return "curved"
    layout_u = layout.upper()
    if layout_u == "LR":
        return "LR"
    src_lv, src_col = src_pos
    dst_lv, dst_col = dst_pos
    if src_lv != dst_lv:
        return "TB"
    if src_col != dst_col:
        return "side"
    return "TB"


def _sync_edges_from_relations(
    semantic: dict[str, Any],
    plan: dict[str, Any],
    positions: dict[str, tuple[int, int]],
) -> None:
    relations = [r for r in (semantic.get("relations") or []) if isinstance(r, dict)]
    if not relations:
        return
    layout = str(plan.get("layout") or "TB")
    edges: list[dict[str, Any]] = []
    for rel in relations:
        src = str(rel.get("from") or "")
        dst = str(rel.get("to") or "")
        if not src or not dst:
            continue
        feedback = _is_feedback_relation(rel)
        async_flag = bool(rel.get("async", False))
        label = str(rel.get("label") or rel.get("verb") or "").strip()
        edges.append({
            "from": src,
            "to": dst,
            "label": label,
            "style": "dashed" if (async_flag or feedback) else "solid",
            "routing": _routing_for_edge(
                layout,
                positions.get(src, (0, 0)),
                positions.get(dst, (0, 0)),
                is_feedback=feedback,
            ),
        })
    plan["edges"] = edges


def _apply_topology_layout(semantic: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    """用 A 阶段 relations 校正 B 阶段的 level/column/edges/layout（保留 B 的形状与配色）。"""
    diagram_type = str(semantic.get("diagram_type") or "flowchart")
    if diagram_type not in _FLOW_TYPES:
        return plan

    entities = [e for e in (semantic.get("entities") or []) if isinstance(e, dict)]
    relations = [r for r in (semantic.get("relations") or []) if isinstance(r, dict)]
    if not entities or not relations:
        return plan

    positions, layout = _relations_topology(entities, relations)
    if not positions:
        return plan

    out = dict(plan)
    out["layout"] = layout
    entity_by_id = {str(e.get("id")): e for e in entities}

    nodes_out: list[dict[str, Any]] = []
    for node in out.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        eid = str(node.get("entity_id") or "")
        if eid not in positions:
            continue
        lv, col = positions[eid]
        ent = entity_by_id.get(eid, {})
        etype = str(ent.get("type") or "process")
        patched = dict(node)
        patched["level"] = lv
        patched["column"] = col
        if etype == "decision":
            patched["shape"] = "diamond"
            patched["color"] = patched.get("color") or "amber"
        elif not patched.get("shape"):
            patched["shape"] = _TYPE_SHAPE.get(etype, "rounded")
        nodes_out.append(patched)

    if nodes_out:
        out["nodes"] = nodes_out
    _sync_edges_from_relations(semantic, out, positions)
    return out


def call_render_planner(
    semantic: dict[str, Any],
    *,
    ctx: PipelineContext | None = None,
) -> dict[str, Any] | None:
    model = ((ctx.model if ctx else None) or settings.intent_model).strip()
    if ctx and not ctx.use_llm:
        return None
    if not model:
        return None
    try:
        prompt = format_prompt(
            "render",
            semantic_json=json.dumps(semantic, ensure_ascii=False, indent=2)[:4000],
        )
    except OSError:
        return None
    try:
        out = LLMClient().chat_completion(
            [{"role": "system", "content": "只输出合法 JSON。"}, {"role": "user", "content": prompt}],
            model=model,
            max_tokens=1200,
            temperature=0.1,
        )
        data = parse_llm_json(out)
    except Exception as e:
        logger.warning("render planner LLM failed: %s", e)
        return None
    if not isinstance(data, dict):
        return None
    return _normalize_render_plan(semantic, data)


def _normalize_render_plan(semantic: dict[str, Any], plan: dict[str, Any]) -> dict[str, Any]:
    layout = str(plan.get("layout") or "").strip().upper()
    if layout not in _VALID_LAYOUTS:
        layout = _default_layout(semantic)
    entities = semantic.get("entities") or []
    entity_by_id = {str(e.get("id")): e for e in entities if isinstance(e, dict)}

    nodes_out: list[dict[str, Any]] = []
    for node in plan.get("nodes") or []:
        if not isinstance(node, dict):
            continue
        eid = str(node.get("entity_id") or "").strip()
        ent = entity_by_id.get(eid)
        if not ent:
            continue
        etype = str(ent.get("type") or "process")
        shape = str(node.get("shape") or _TYPE_SHAPE.get(etype, "rounded"))
        if shape not in _VALID_SHAPES:
            shape = _TYPE_SHAPE.get(etype, "rounded")
        color = str(node.get("color") or _TYPE_COLOR.get(etype, "gray"))
        if color not in _VALID_COLORS:
            color = "gray"
        nodes_out.append({
            "entity_id": eid,
            "label": str(ent.get("name") or node.get("label") or ""),
            "shape": shape,
            "color": color,
            "size": str(node.get("size") or "md"),
            "group_id": str(node.get("group_id") or ""),
            "level": int(node.get("level") or 0),
            "column": int(node.get("column") or 0),
        })

    edges_out: list[dict[str, Any]] = []
    for edge in plan.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        routing = str(edge.get("routing") or _default_routing(layout)).upper()
        if routing == "SIDE":
            routing = "side"
        elif routing not in _VALID_ROUTING:
            routing = _default_routing(layout)
        style = str(edge.get("style") or "solid")
        if style not in {"solid", "dashed"}:
            style = "solid"
        edges_out.append({
            "from": str(edge.get("from") or "").strip(),
            "to": str(edge.get("to") or "").strip(),
            "label": str(edge.get("label") or "").strip(),
            "style": style,
            "routing": routing,
        })

    groups_out: list[dict[str, Any]] = []
    for grp in plan.get("groups") or []:
        if not isinstance(grp, dict):
            continue
        color = str(grp.get("color") or "blue")
        if color not in _VALID_COLORS:
            color = "blue"
        groups_out.append({
            "id": str(grp.get("id") or ""),
            "label": str(grp.get("label") or ""),
            "color": color,
            "node_ids": [str(x) for x in (grp.get("node_ids") or [])],
        })

    canvas = plan.get("canvas") if isinstance(plan.get("canvas"), dict) else {}
    return {
        "layout": layout,
        "canvas": {
            "width": int(canvas.get("width") or 0),
            "height": int(canvas.get("height") or 0),
        },
        "nodes": nodes_out,
        "edges": edges_out,
        "groups": groups_out,
    }


def _validate_render_plan(semantic: dict[str, Any], plan: dict[str, Any]) -> tuple[bool, list[str]]:
    warnings: list[str] = []
    entities = [e for e in (semantic.get("entities") or []) if isinstance(e, dict)]
    entity_ids = {str(e.get("id") or "") for e in entities}
    entity_ids.discard("")

    nodes = plan.get("nodes") or []
    node_ids = {str(n.get("entity_id") or "") for n in nodes if isinstance(n, dict)}
    node_ids.discard("")

    missing = entity_ids - node_ids
    extra = node_ids - entity_ids
    if missing:
        warnings.append(f"missing_nodes:{len(missing)}")
        for eid in missing:
            ent = next((e for e in entities if str(e.get("id")) == eid), None)
            if ent:
                etype = str(ent.get("type") or "process")
                nodes.append({
                    "entity_id": eid,
                    "label": str(ent.get("name") or ""),
                    "shape": _TYPE_SHAPE.get(etype, "rounded"),
                    "color": _TYPE_COLOR.get(etype, "gray"),
                    "size": "md",
                    "group_id": "",
                    "level": 0,
                    "column": len(nodes),
                })
    if extra:
        warnings.append(f"extra_nodes:{len(extra)}")
        plan["nodes"] = [n for n in nodes if str(n.get("entity_id") or "") in entity_ids]
    else:
        plan["nodes"] = nodes

    valid_edges: list[dict[str, Any]] = []
    for edge in plan.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        src = str(edge.get("from") or "").strip()
        dst = str(edge.get("to") or "").strip()
        if src not in entity_ids or dst not in entity_ids:
            warnings.append(f"invalid_edge:{src}->{dst}")
            continue
        routing = str(edge.get("routing") or "LR")
        if routing not in _VALID_ROUTING:
            routing = _default_routing(str(plan.get("layout") or "LR"))
            warnings.append(f"invalid_routing_fixed:{routing}")
        edge["routing"] = routing
        valid_edges.append(edge)
    plan["edges"] = valid_edges

    canvas = plan.get("canvas") if isinstance(plan.get("canvas"), dict) else {}
    n_ent = len(entity_ids)
    n_grp = len(semantic.get("groups") or [])
    levels = {int(n.get("level") or 0) for n in plan.get("nodes") or [] if isinstance(n, dict)}
    n_levels = max(len(levels), 1)
    if not int(canvas.get("width") or 0):
        canvas["width"] = min(1400, max(800, n_ent * 180, n_grp * 260))
    if not int(canvas.get("height") or 0):
        canvas["height"] = min(1000, max(500, n_levels * 160 + 120))
    plan["canvas"] = canvas

    is_usable = len(plan.get("nodes") or []) >= 2
    return is_usable, warnings


def _rule_based_render_plan(semantic: dict[str, Any]) -> dict[str, Any]:
    """调用 B 失败时的规则兜底。"""
    entities = [e for e in (semantic.get("entities") or []) if isinstance(e, dict)]
    relations = [r for r in (semantic.get("relations") or []) if isinstance(r, dict)]
    groups_sem = [g for g in (semantic.get("groups") or []) if isinstance(g, dict)]
    diagram_type = str(semantic.get("diagram_type") or "flowchart")
    layout = _default_layout(semantic)

    entity_order = _topo_order(entities, relations)
    group_color: dict[str, str] = {}
    entity_group: dict[str, str] = {}
    for gi, grp in enumerate(groups_sem):
        gid = str(grp.get("id") or f"g{gi + 1}")
        group_color[gid] = _GROUP_COLORS[gi % len(_GROUP_COLORS)]
        for mid in grp.get("members") or []:
            entity_group[str(mid)] = gid

    nodes: list[dict[str, Any]] = []
    if layout == "LAYERED" and groups_sem:
        for gi, grp in enumerate(groups_sem):
            members = [str(m) for m in (grp.get("members") or [])]
            col = 0
            for eid in members:
                ent = next((e for e in entities if str(e.get("id")) == eid), None)
                if not ent:
                    continue
                etype = str(ent.get("type") or "process")
                gid = str(grp.get("id") or f"g{gi + 1}")
                nodes.append({
                    "entity_id": eid,
                    "label": str(ent.get("name") or ""),
                    "shape": _TYPE_SHAPE.get(etype, "rounded"),
                    "color": group_color.get(gid, "blue"),
                    "size": "md",
                    "group_id": gid,
                    "level": gi,
                    "column": col,
                })
                col += 1
    else:
        if diagram_type in _FLOW_TYPES and relations:
            positions, layout = _relations_topology(entities, relations)
            for eid, (lv, col) in positions.items():
                ent = next((e for e in entities if str(e.get("id")) == eid), None)
                if not ent:
                    continue
                etype = str(ent.get("type") or "process")
                gid = entity_group.get(eid, "")
                nodes.append({
                    "entity_id": eid,
                    "label": str(ent.get("name") or ""),
                    "shape": _TYPE_SHAPE.get(etype, "rounded"),
                    "color": group_color.get(gid) or _TYPE_COLOR.get(etype, "gray"),
                    "size": "md",
                    "group_id": gid,
                    "level": lv,
                    "column": col,
                })
        else:
            for i, eid in enumerate(entity_order):
                ent = next((e for e in entities if str(e.get("id")) == eid), None)
                if not ent:
                    continue
                etype = str(ent.get("type") or "process")
                gid = entity_group.get(eid, "")
                nodes.append({
                    "entity_id": eid,
                    "label": str(ent.get("name") or ""),
                    "shape": _TYPE_SHAPE.get(etype, "rounded"),
                    "color": group_color.get(gid) or _TYPE_COLOR.get(etype, "gray"),
                    "size": "md",
                    "group_id": gid,
                    "level": i,
                    "column": 0,
                })

    edges: list[dict[str, Any]] = []
    if diagram_type in _FLOW_TYPES and relations:
        positions = {str(n["entity_id"]): (int(n["level"]), int(n["column"])) for n in nodes}
        tmp_plan = {"layout": layout, "edges": []}
        _sync_edges_from_relations(semantic, tmp_plan, positions)
        edges = tmp_plan["edges"]
    else:
        for rel in relations:
            src = str(rel.get("from") or "")
            dst = str(rel.get("to") or "")
            if not src or not dst:
                continue
            async_flag = bool(rel.get("async", False))
            edges.append({
                "from": src,
                "to": dst,
                "label": str(rel.get("label") or rel.get("verb") or "").strip(),
                "style": "dashed" if async_flag else "solid",
                "routing": _edge_routing(layout, src, dst, entity_group),
            })
        if not edges and len(entity_order) > 1 and diagram_type in {"flowchart", "timeline", "dataflow"}:
            for left, right in zip(entity_order, entity_order[1:]):
                edges.append({
                    "from": left,
                    "to": right,
                    "label": "",
                    "style": "solid",
                    "routing": "LR" if layout == "LR" else "TB",
                })

    groups_out = [
        {
            "id": str(grp.get("id") or f"g{gi + 1}"),
            "label": str(grp.get("label") or ""),
            "color": group_color.get(str(grp.get("id") or f"g{gi + 1}"), _GROUP_COLORS[gi % len(_GROUP_COLORS)]),
            "node_ids": [str(m) for m in (grp.get("members") or [])],
        }
        for gi, grp in enumerate(groups_sem)
    ]

    n_ent = len(entities)
    n_grp = len(groups_sem)
    levels = {int(n.get("level") or 0) for n in nodes}
    plan = {
        "layout": layout,
        "canvas": {
            "width": min(1400, max(800, n_ent * 180, n_grp * 260)),
            "height": min(1000, max(500, max(len(levels), 1) * 160 + 120)),
        },
        "nodes": nodes,
        "edges": edges,
        "groups": groups_out,
    }
    _validate_render_plan(semantic, plan)
    return plan


def _default_layout(semantic: dict[str, Any]) -> str:
    diagram_type = str(semantic.get("diagram_type") or "flowchart")
    entities = semantic.get("entities") or []
    has_decision = any(str(e.get("type")) == "decision" for e in entities if isinstance(e, dict))
    n = len(entities)
    if diagram_type == "architecture" and semantic.get("groups"):
        return "LAYERED"
    if diagram_type in {"comparison"}:
        return "GRID"
    if diagram_type in {"taxonomy", "hierarchy"}:
        return "RADIAL"
    if diagram_type == "timeline":
        return "LR"
    if diagram_type in {"flowchart", "dataflow"}:
        if n <= 5 and not has_decision:
            return "LR"
        return "TB"
    if diagram_type == "architecture":
        return "LAYERED" if semantic.get("groups") else "TB"
    return "TB"


def _default_routing(layout: str) -> str:
    layout = layout.upper()
    if layout == "LR":
        return "LR"
    if layout == "LAYERED":
        return "LR"
    if layout == "GRID":
        return "side"
    return "TB"


def _edge_routing(layout: str, src: str, dst: str, entity_group: dict[str, str]) -> str:
    layout_u = layout.upper()
    if layout_u == "LAYERED":
        sg, dg = entity_group.get(src, ""), entity_group.get(dst, "")
        if sg and dg and sg != dg:
            return "LR"
        return "side"
    return _default_routing(layout)


def _topo_order(entities: list[dict], relations: list[dict]) -> list[str]:
    ids = [str(e.get("id") or "") for e in entities if str(e.get("id") or "")]
    if not relations:
        return ids
    succ: dict[str, list[str]] = {i: [] for i in ids}
    pred_count: dict[str, int] = {i: 0 for i in ids}
    for rel in relations:
        src = str(rel.get("from") or "")
        dst = str(rel.get("to") or "")
        if src in succ and dst in pred_count and src != dst:
            succ[src].append(dst)
            pred_count[dst] = pred_count.get(dst, 0) + 1
    queue = [i for i in ids if pred_count.get(i, 0) == 0]
    order: list[str] = []
    while queue:
        cur = queue.pop(0)
        order.append(cur)
        for nxt in succ.get(cur, []):
            pred_count[nxt] -= 1
            if pred_count[nxt] == 0:
                queue.append(nxt)
    for i in ids:
        if i not in order:
            order.append(i)
    return order
