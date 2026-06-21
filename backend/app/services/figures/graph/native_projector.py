"""Native Structure → GraphIR 类型化投影。"""

from __future__ import annotations

import re
from typing import Any

from app.services.figures.graph.schema import GraphEdge, GraphIR, GraphNode
from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.schemas.diagram import DiagramIntent
from app.services.figures.schemas.dsl import slug_id
from app.services.figures.semantic.schema import SemanticIR


def project_native_to_graph(ir: SemanticIR, intent: DiagramIntent) -> GraphIR | None:
    native = ir.native_structure or {}
    ntype = ir.native_type()
    if not ntype:
        return None

    projectors = {
        "comparison_matrix": _project_comparison,
        "comparison": _project_comparison,
        "timeline": _project_timeline,
        "timeline_roadmap": _project_timeline,
        "taxonomy": _project_taxonomy,
        "taxonomy_map": _project_taxonomy,
        "process_flow": _project_flow,
        "flowchart": _project_flow,
        "pipeline": _project_flow,
        "shared_architecture": _project_architecture,
        "architecture": _project_architecture,
        "system_architecture": _project_architecture,
        "mechanism": _project_mechanism,
        "mechanism_diagram": _project_mechanism,
        "decision_tree": _project_decision,
        "decision_flow": _project_decision,
        "concept": _project_concept,
        "concept_diagram": _project_concept,
        "infographic": _project_infographic,
        "chapter_summary": _project_infographic,
    }
    fn = projectors.get(ntype)
    if not fn:
        return None
    graph = fn(native, ir, intent)
    if graph:
        hints = list(ir.layout_hints)
        subtype = canonical_subtype(intent.diagram_subtype)
        if subtype == "taxonomy_map" and "tree_tb" not in hints:
            hints.append("tree_tb")
        if subtype == "system_architecture" and "layered_architecture" not in hints:
            hints.append("layered_architecture")
        graph.layout_constraints = {"hints": hints}
        graph.style_hints = list(ir.style_hints)
    return graph


def _project_comparison(native: dict, ir: SemanticIR, intent: DiagramIntent) -> GraphIR:
    subjects = [str(x) for x in (native.get("subjects") or native.get("columns") or [])]
    dimensions = [str(x) for x in (native.get("dimensions") or [])]
    nodes = [GraphNode(id="matrix", label=ir.title or "对比", kind="module", shape="rounded")]
    edges: list[GraphEdge] = []
    for i, dim in enumerate(dimensions):
        did = f"d{i}"
        nodes.append(GraphNode(id=did, label=dim, kind="module", shape="box"))
        edges.append(GraphEdge(source="matrix", target=did, label=""))
    for j, subj in enumerate(subjects):
        cid = f"c{j}"
        nodes.append(GraphNode(id=cid, label=subj, kind="tag", shape="tag"))
        if dimensions:
            edges.append(GraphEdge(source=f"d{min(j, len(dimensions) - 1)}", target=cid, label=""))
    return GraphIR(
        diagram_type="comparison",
        title=ir.title or intent.title or "对比",
        nodes=nodes,
        edges=edges,
    )


def _project_timeline(native: dict, ir: SemanticIR, intent: DiagramIntent) -> GraphIR:
    milestones = native.get("milestones") or native.get("events") or []
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    for i, m in enumerate(milestones):
        if not isinstance(m, dict):
            continue
        label = f"{m.get('time', '')} {m.get('label', '')}".strip()
        nid = f"e{i}"
        nodes.append(GraphNode(id=nid, label=label or f"节点{i + 1}", kind="process", shape="rounded"))
        if i > 0:
            edges.append(GraphEdge(source=f"e{i - 1}", target=nid, label=""))
    return GraphIR(diagram_type="timeline", title=ir.title or intent.title or "时间线", nodes=nodes, edges=edges)


def _project_taxonomy(native: dict, ir: SemanticIR, intent: DiagramIntent) -> GraphIR:
    from app.services.figures.contracts.geometry_projector import _project_tree_graph

    payload = {"root": str(native.get("root") or ir.title or "根"), "children": native.get("children") or []}
    return _project_tree_graph(payload)


def _project_flow(native: dict, ir: SemanticIR, intent: DiagramIntent) -> GraphIR:
    from app.services.figures.semantic.flow_semantic import (
        coerce_process_flow_native,
        derive_flow_columns,
        derive_flow_layers,
    )

    flow = coerce_process_flow_native(native)
    flow_nodes = [n for n in (flow.get("nodes") or []) if isinstance(n, dict)]
    flow_edges = [e for e in (flow.get("edges") or []) if isinstance(e, dict)]
    layers = derive_flow_layers(flow)
    columns = derive_flow_columns(flow, layers)

    kind_to_graph = {
        "start": ("process", "rounded"),
        "end": ("process", "rounded"),
        "task": ("process", "rounded"),
        "decision": ("decision", "diamond"),
        "parallel_split": ("process", "rounded"),
        "parallel_join": ("process", "rounded"),
        "subprocess": ("process", "box"),
        "swimlane": ("module", "box"),
    }

    nodes: list[GraphNode] = []
    id_map: dict[str, str] = {}
    for i, raw in enumerate(flow_nodes):
        nid = str(raw.get("id") or f"n{i}")
        label = str(raw.get("label") or nid)
        raw_kind = str(raw.get("kind") or "task").lower()
        if raw_kind == "decision" or re.search(r"是否|判断", label):
            gkind, shape = "decision", "diamond"
        else:
            gkind, shape = kind_to_graph.get(raw_kind, ("process", "rounded"))
        level = layers.get(nid, 0)
        column = columns.get(nid, 0)
        nodes.append(
            GraphNode(
                id=nid,
                label=label,
                kind=gkind,
                shape=shape,
                layout_constraints={
                    "level": level,
                    "column": column,
                    "flow_kind": raw_kind,
                    "parallel": raw_kind in {"parallel_split", "parallel_join"},
                },
            )
        )
        id_map[nid] = nid

    edges: list[GraphEdge] = []
    for edge in flow_edges:
        src = str(edge.get("from") or "")
        tgt = str(edge.get("to") or "")
        if src not in id_map or tgt not in id_map:
            continue
        label = str(edge.get("label") or "")
        edge_kind = str(edge.get("kind") or "default").lower()
        is_loop = edge_kind == "loop_back" or label in {"不达标", "返回", "重试", "未达标"}
        edges.append(
            GraphEdge(
                source=src,
                target=tgt,
                label=label,
                edge_type="return" if is_loop else "sync",
                style="dashed" if is_loop else "solid",
            )
        )

    hints = list(ir.layout_hints)
    if any(str(n.get("kind") or "") in {"parallel_split", "parallel_join"} for n in flow_nodes):
        if "parallel_merge" not in hints:
            hints.append("parallel_merge")
    if any(e.edge_type == "return" for e in edges) and "TB_Decision" not in hints:
        hints.append("TB_Decision")
    return GraphIR(
        diagram_type="flowchart",
        title=ir.title or intent.title or "流程",
        nodes=nodes,
        edges=edges,
        layout_constraints={"hints": hints},
        style_hints=list(ir.style_hints),
    )


def _project_architecture(native: dict, ir: SemanticIR, intent: DiagramIntent) -> GraphIR:
    components = [str(c) for c in (native.get("components") or [])]
    groups_raw = native.get("groups") or ir.groups or []
    nodes: list[GraphNode] = []
    comp_to_id: dict[str, str] = {}
    for i, comp in enumerate(components):
        nid = slug_id(comp) or f"m{i}"
        comp_to_id[comp] = nid
        group = ""
        for g in groups_raw:
            if isinstance(g, dict) and comp in [str(m) for m in (g.get("members") or [])]:
                group = str(g.get("label") or g.get("id") or "")
        nodes.append(GraphNode(id=nid, label=comp, kind="service", group=group, shape="box"))
    edges: list[GraphEdge] = []
    for inter in native.get("interactions") or []:
        if not isinstance(inter, dict):
            continue
        src = comp_to_id.get(str(inter.get("from") or ""), str(inter.get("from") or ""))
        tgt = comp_to_id.get(str(inter.get("to") or ""), str(inter.get("to") or ""))
        if src and tgt:
            edges.append(GraphEdge(source=src, target=tgt, label=str(inter.get("label") or "")))
    groups = [dict(g) for g in groups_raw if isinstance(g, dict)]
    return GraphIR(
        diagram_type="architecture",
        title=ir.title or intent.title or "架构",
        nodes=nodes,
        edges=edges,
        groups=groups,
    )


def _project_mechanism(native: dict, ir: SemanticIR, intent: DiagramIntent) -> GraphIR:
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    label_to_id: dict[str, str] = {}

    def _label_of(item: Any) -> str:
        if isinstance(item, str):
            return item.strip()
        if isinstance(item, dict):
            return str(item.get("name") or item.get("label") or item.get("id") or "").strip()
        return ""

    def _ensure_node(label: str, *, kind: str = "process") -> str:
        text = _short_mechanism_label(label)
        if not text:
            return ""
        if text in label_to_id:
            return label_to_id[text]
        nid = slug_id(text) or f"m{len(nodes)}"
        label_to_id[text] = nid
        nodes.append(GraphNode(id=nid, label=text, kind=kind))
        return nid

    for actor in native.get("actors") or []:
        _ensure_node(_label_of(actor), kind="module")
    for state in native.get("states") or []:
        _ensure_node(_label_of(state), kind="process")

    def _add_edge(src_label: str, tgt_label: str, *, label: str = "", style: str = "solid") -> None:
        src = _ensure_node(src_label)
        tgt = _ensure_node(tgt_label)
        if src and tgt and src != tgt:
            edges.append(GraphEdge(source=src, target=tgt, label=label[:12], style=style))

    legacy_relation_field = "trans" + "fers"
    relation_items = native.get("interactions") or native.get(legacy_relation_field) or []
    for relation in relation_items:
        if not isinstance(relation, dict):
            continue
        effect = str(relation.get("effect") or "")
        style = "dashed" if effect in {"feedback", "inhibit"} else "solid"
        _add_edge(
            str(relation.get("from") or ""),
            str(relation.get("to") or ""),
            label=str(relation.get("what") or ""),
            style=style,
        )

    for link in native.get("causal_links") or []:
        if isinstance(link, dict):
            _add_edge(str(link.get("from") or ""), str(link.get("to") or ""), label=str(link.get("polarity") or ""))

    for fb in list(native.get("feedbacks") or []) + list(native.get("positive_feedbacks") or []) + list(native.get("negative_feedbacks") or []):
        if isinstance(fb, dict):
            _add_edge(str(fb.get("from") or ""), str(fb.get("to") or ""), label=str(fb.get("meaning") or "反馈")[:12], style="dashed")

    has_relation_edges = bool(edges)
    if not has_relation_edges:
        prev = ""
        for i, inp in enumerate(native.get("inputs") or []):
            nid = _ensure_node(_label_of(inp) or f"输入{i + 1}")
            if prev:
                edges.append(GraphEdge(source=prev, target=nid, label=""))
            prev = nid
        for j, step in enumerate(native.get("steps") or []):
            nid = _ensure_node(_label_of(step) or f"步骤{j + 1}")
            if prev:
                edges.append(GraphEdge(source=prev, target=nid, label=""))
            prev = nid
        for k, out in enumerate(native.get("outputs") or []):
            nid = _ensure_node(_label_of(out) or f"输出{k + 1}")
            if prev:
                edges.append(GraphEdge(source=prev, target=nid, label=""))
    else:
        for i, inp in enumerate(native.get("inputs") or []):
            _ensure_node(_label_of(inp) or f"输入{i + 1}", kind="module")
        for j, step in enumerate(native.get("steps") or []):
            _ensure_node(_label_of(step) or f"步骤{j + 1}")
        for k, out in enumerate(native.get("outputs") or []):
            _ensure_node(_label_of(out) or f"输出{k + 1}")
        for i, n in enumerate(nodes):
            lbl = (n.label or "").lower()
            if any(k in lbl for k in ("输入", "input", "序列")):
                n.layout_constraints = {"level": 0}
            elif any(k in lbl for k in ("输出", "output", "向量")):
                n.layout_constraints = {"level": 2}
            else:
                n.layout_constraints = {"level": 1}

    if not nodes:
        title = _short_mechanism_label(ir.title or intent.title or "机制")
        _ensure_node(title or "机制")

    hints = list(ir.layout_hints)
    if edges and len(nodes) >= 3:
        hints.append("mechanism_layered")
    return GraphIR(
        diagram_type="mechanism_diagram",
        title=ir.title or intent.title or "机制",
        nodes=nodes,
        edges=edges,
        layout_constraints={"hints": list(dict.fromkeys(hints))},
    )


def _short_mechanism_label(text: str, limit: int = 48) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip()).strip(" ：:，,。")
    return raw[:limit]


def _project_decision(native: dict, ir: SemanticIR, intent: DiagramIntent) -> GraphIR:
    from app.services.figures.contracts.field_registry import pick_str

    decisions = native.get("decisions") or []
    if decisions:
        from app.services.figures.contracts.geometry_projector import _project_decision_tree

        return _project_decision_tree(native, ir.title or intent.title or "决策")

    root = pick_str(native, "root_decision", pick_str(native, "root", ir.title or "起点"))
    nodes = [GraphNode(id="root", label=root, kind="start", shape="rounded")]
    edges: list[GraphEdge] = []
    for i, br in enumerate(native.get("branches") or []):
        if not isinstance(br, dict):
            continue
        cond = pick_str(br, "condition", f"判断{i + 1}")
        cid = f"d{i}"
        nodes.append(GraphNode(id=cid, label=cond, kind="decision", shape="diamond"))
        edges.append(GraphEdge(source="root", target=cid, label=""))
        for key, suffix in (("yes", "y"), ("no", "n")):
            val = br.get(key)
            if val:
                oid = f"{cid}_{suffix}"
                nodes.append(GraphNode(id=oid, label=str(val), kind="process"))
                edges.append(GraphEdge(source=cid, target=oid, label=key))
    return GraphIR(diagram_type="decision_flow", title=ir.title or intent.title or "决策", nodes=nodes, edges=edges)


def _project_infographic(native: dict, ir: SemanticIR, intent: DiagramIntent) -> GraphIR:
    blocks = []
    for item in native.get("blocks") or []:
        if isinstance(item, str):
            blocks.append({"label": _short_mechanism_label(item), "items": []})
        elif isinstance(item, dict):
            label = _short_mechanism_label(str(item.get("label") or item.get("title") or ""))
            if label:
                items = [_short_mechanism_label(str(x)) for x in (item.get("items") or []) if _short_mechanism_label(str(x))]
                blocks.append({"label": label, "items": items[:2]})
    if not blocks:
        blocks = [{"label": _short_mechanism_label(ir.title or "要点"), "items": []}]

    title = _short_mechanism_label(ir.title or intent.title or "信息图", 24)
    nodes: list[GraphNode] = [GraphNode(id="summary", label=title or "信息图", kind="module", shape="rounded")]
    edges: list[GraphEdge] = []
    for i, block in enumerate(blocks):
        bid = f"b{i}"
        nodes.append(GraphNode(id=bid, label=block["label"], kind="module", shape="box", group="block"))
        edges.append(GraphEdge(source="summary", target=bid, label=""))
        for j, item in enumerate(block.get("items") or []):
            iid = f"b{i}_{j}"
            nodes.append(GraphNode(id=iid, label=item, kind="process", shape="tag", group=bid))
            edges.append(GraphEdge(source=bid, target=iid, label=""))

    graph = GraphIR(
        diagram_type="infographic",
        title=title or "信息图",
        nodes=nodes,
        edges=edges,
    )
    graph.layout_constraints = {"hints": ["grid_2x4"], "blocks": blocks}
    return graph


def _project_concept(native: dict, ir: SemanticIR, intent: DiagramIntent) -> GraphIR:
    concepts = [str(c) for c in (native.get("concepts") or [])]
    center = str(native.get("center") or "").strip()
    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    name_to_id: dict[str, str] = {}

    if center:
        cid = slug_id(center) or "center"
        nodes.append(GraphNode(id=cid, label=center, kind="module", shape="rounded"))
        name_to_id[center] = cid

    for i, c in enumerate(concepts):
        if c == center:
            continue
        nid = slug_id(c) or f"c{i}"
        nodes.append(GraphNode(id=nid, label=c, kind="module", shape="box"))
        name_to_id[c] = nid
        if center and name_to_id.get(center):
            edges.append(GraphEdge(source=name_to_id[center], target=nid, label=""))

    for rel in native.get("relations") or ir.relations or []:
        if not isinstance(rel, dict):
            continue
        src = str(rel.get("from") or "")
        tgt = str(rel.get("to") or "")
        s = name_to_id.get(src, slug_id(src) if src else "")
        t = name_to_id.get(tgt, slug_id(tgt) if tgt else "")
        if s and t and s != t:
            edges.append(GraphEdge(source=s, target=t, label=str(rel.get("label") or "")))

    if not nodes and concepts:
        nodes = [GraphNode(id=slug_id(c) or f"c{i}", label=c, kind="module") for i, c in enumerate(concepts)]

    return GraphIR(
        diagram_type="concept",
        title=ir.title or intent.title or "概念图",
        nodes=nodes,
        edges=edges,
        layout_constraints={"hints": ["radial"]},
    )
