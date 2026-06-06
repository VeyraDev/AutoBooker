"""空图/模糊输入时的占位 DSL。"""

from __future__ import annotations

from app.services.figures.schemas.dsl import DiagramDSL, DiagramEdge, DiagramGroup, DiagramNode, slug_id


def default_dsl_for_type(diagram_type: str, *, title: str = "示意图") -> DiagramDSL:
    dt = (diagram_type or "flowchart").strip().lower()
    if dt in {"flowchart", "process_flow", "workflow"}:
        return _flowchart_default(title)
    if dt in {"decision_flow", "decision_tree", "decision"}:
        return _decision_default(title)
    if dt in {"architecture", "system_architecture", "microservice_architecture", "rag", "agent"}:
        return _architecture_default(title)
    if dt in {"timeline", "timeline_roadmap"}:
        return _timeline_default(title)
    if dt in {"taxonomy", "taxonomy_map", "hierarchy", "org_chart"}:
        return _taxonomy_default(title)
    if dt in {"comparison", "comparison_matrix"}:
        return _comparison_default(title)
    if dt in {"matrix", "swot", "quadrant_matrix"}:
        return _matrix_default(title)
    return _flowchart_default(title)


def _flowchart_default(title: str) -> DiagramDSL:
    labels = ["开始", "步骤一", "步骤二", "完成"]
    nodes = []
    for i, label in enumerate(labels):
        ntype = "start" if i == 0 else ("end" if i == len(labels) - 1 else "process")
        nodes.append(DiagramNode(id=f"s{i}", label=label, type=ntype))
    edges = [DiagramEdge(source=f"s{i}", target=f"s{i + 1}") for i in range(len(nodes) - 1)]
    return DiagramDSL(
        diagram_type="flowchart",
        title=title or "流程图",
        nodes=nodes,
        edges=edges,
        layout={"direction": "TB", "mode": "sequential"},
    )


def _decision_default(title: str) -> DiagramDSL:
    nodes = [
        DiagramNode(id="start", label="开始", type="start"),
        DiagramNode(id="check", label="是否满足条件", type="decision"),
        DiagramNode(id="yes", label="结束", type="end"),
        DiagramNode(id="no", label="重试", type="process"),
    ]
    edges = [
        DiagramEdge(source="start", target="check"),
        DiagramEdge(source="check", target="yes", label="是"),
        DiagramEdge(source="check", target="no", label="否", type="fallback"),
        DiagramEdge(source="no", target="check", type="return"),
    ]
    return DiagramDSL(
        diagram_type="decision_flow",
        title=title or "决策流程",
        nodes=nodes,
        edges=edges,
        layout={"direction": "TB", "mode": "decision"},
    )


def _architecture_default(title: str) -> DiagramDSL:
    layers = [
        ("入口层", ["API网关"]),
        ("服务层", ["用户服务", "订单服务"]),
        ("基础设施层", ["数据库"]),
    ]
    nodes: list[DiagramNode] = []
    groups: list[DiagramGroup] = []
    for layer_label, modules in layers:
        gid = slug_id(layer_label, "layer")
        node_ids: list[str] = []
        for mod in modules:
            nid = slug_id(mod)
            ntype = "gateway" if "网关" in mod else ("database" if "库" in mod else "service")
            nodes.append(DiagramNode(id=nid, label=mod, type=ntype, group=layer_label))
            node_ids.append(nid)
        groups.append(DiagramGroup(id=gid, label=layer_label, type="layer", nodes=node_ids, layout="row"))
    edges = [
        DiagramEdge(source=slug_id("API网关"), target=slug_id("用户服务")),
        DiagramEdge(source=slug_id("API网关"), target=slug_id("订单服务")),
        DiagramEdge(source=slug_id("订单服务"), target=slug_id("数据库"), type="data"),
    ]
    return DiagramDSL(
        diagram_type="architecture",
        title=title or "系统架构",
        nodes=nodes,
        edges=edges,
        groups=groups,
        layout={"direction": "TB", "mode": "layered"},
    )


def _timeline_default(title: str) -> DiagramDSL:
    labels = ["阶段一", "阶段二", "阶段三"]
    nodes = [DiagramNode(id=f"t{i}", label=lb, type="process") for i, lb in enumerate(labels)]
    edges = [DiagramEdge(source=f"t{i}", target=f"t{i + 1}") for i in range(len(nodes) - 1)]
    return DiagramDSL(
        diagram_type="timeline",
        title=title or "时间线",
        nodes=nodes,
        edges=edges,
        layout={"direction": "LR", "mode": "timeline"},
    )


def _taxonomy_default(title: str) -> DiagramDSL:
    root = DiagramNode(id="root", label=title or "核心主题", type="module", importance=2)
    children = [DiagramNode(id=f"c{i}", label=lb, type="module", group="分支") for i, lb in enumerate(["分支A", "分支B", "分支C"])]
    edges = [DiagramEdge(source="root", target=c.id) for c in children]
    return DiagramDSL(
        diagram_type="taxonomy",
        title=title or "分类图",
        nodes=[root, *children],
        edges=edges,
        layout={"direction": "TB", "mode": "tree"},
    )


def _comparison_default(title: str) -> DiagramDSL:
    nodes = [
        DiagramNode(id="opt_a", label="方案A", type="module"),
        DiagramNode(id="opt_b", label="方案B", type="module"),
    ]
    return DiagramDSL(
        diagram_type="comparison",
        title=title or "方案对比",
        nodes=nodes,
        edges=[],
        layout={"direction": "LR", "mode": "columns"},
    )


def _matrix_default(title: str) -> DiagramDSL:
    nodes = [
        DiagramNode(id="q1", label="优势", type="module", group="S"),
        DiagramNode(id="q2", label="劣势", type="module", group="W"),
        DiagramNode(id="q3", label="机会", type="module", group="O"),
        DiagramNode(id="q4", label="威胁", type="module", group="T"),
    ]
    return DiagramDSL(
        diagram_type="matrix",
        title=title or "四象限",
        nodes=nodes,
        edges=[],
        layout={"direction": "TB", "mode": "quadrant"},
    )
