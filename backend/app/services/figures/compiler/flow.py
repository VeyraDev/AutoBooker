"""FlowCompiler：content_brief → Flow Native IR。"""

from __future__ import annotations

import re
from typing import Any

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.compiler.base import DiagramCompiler
from app.services.figures.compiler.patterns import (
    apply_dependencies,
    apply_interrupt_branches,
    apply_optional_branches,
)
from app.services.figures.contracts.field_registry import pick_str
from app.services.figures.contracts.geometry_kinds import GEOMETRY_GRAPH
from app.services.figures.contracts.normalize import normalize_content_brief, normalize_graph_decisions
from app.services.figures.native.base import NativeIR
from app.services.figures.native.flow import empty_flow_ir
from app.services.figures.schemas.diagram import DiagramIntent


def _slug(label: str, idx: int) -> str:
    base = re.sub(r"[^a-zA-Z0-9\u4e00-\u9fff]+", "_", label.strip())[:12] or f"s{idx}"
    return base


class FlowCompiler(DiagramCompiler):
    def compile(self, brief: VisualBrief, intent: DiagramIntent) -> NativeIR:
        content = normalize_content_brief(brief.diagram_type or intent.diagram_subtype, dict(brief.content_brief or {}))
        ir = empty_flow_ir()
        ir["geometry_kind"] = GEOMETRY_GRAPH
        ir["steps"] = _extract_steps(content)
        ir["parallel_groups"] = list(content.get("parallel_groups") or [])
        ir["decisions"] = normalize_graph_decisions(list(content.get("decisions") or []))
        ir["loops"] = list(content.get("loops") or [])
        ir["dependencies"] = list(content.get("dependencies") or [])
        ir["optional_branches"] = list(content.get("optional_branches") or [])
        ir["interrupt_branches"] = list(content.get("interrupt_branches") or [])
        ir["joins"] = _derive_joins(ir)
        ir["control_graph"] = _build_control_graph(ir)
        hints: list[str] = []
        vb = brief.visual_brief or {}
        ro = str(vb.get("reading_order") or "")
        if ro in {"left_to_right", "lr"}:
            hints.append("LR_flow")
        ir["layout_hints"] = hints
        return NativeIR(
            diagram_type="process_flow",
            title=brief.title or intent.title or "流程图",
            structure=ir,
            meta={"geometry_kind": GEOMETRY_GRAPH},
        ).with_geometry_kind(GEOMETRY_GRAPH)


def _extract_steps(content: dict[str, Any]) -> list[dict[str, Any]]:
    steps: list[dict[str, Any]] = []
    for i, item in enumerate(content.get("main_flow") or []):
        if isinstance(item, str):
            label = item.strip()
        elif isinstance(item, dict):
            label = str(item.get("label") or item.get("name") or "").strip()
        else:
            continue
        if label:
            steps.append({"id": _slug(label, i), "label": label})
    if not steps:
        for i, lane in enumerate(content.get("lanes") or []):
            if isinstance(lane, dict):
                for j, it in enumerate(lane.get("items") or []):
                    label = str(it if isinstance(it, str) else (it.get("label") if isinstance(it, dict) else ""))
                    if label:
                        steps.append({"id": _slug(label, len(steps)), "label": label})
    return steps[:24]


def _derive_joins(ir: dict[str, Any]) -> list[dict[str, Any]]:
    joins: list[dict[str, Any]] = []
    for pg in ir.get("parallel_groups") or []:
        if not isinstance(pg, dict):
            continue
        merge = str(pg.get("merge_before") or "")
        if merge:
            joins.append({"before": merge, "items": list(pg.get("items") or [])})
    return joins


def _build_control_graph(ir: dict[str, Any]) -> dict[str, Any]:
    """Flow IR → 控制流 nodes/edges（供 Layout 投影）。"""
    steps = ir.get("steps") or []
    label_index = {str(s.get("label") or ""): str(s.get("id") or "") for s in steps if isinstance(s, dict)}
    nodes: list[dict[str, Any]] = [{"id": "start", "label": "开始", "kind": "start"}]
    edges: list[dict[str, Any]] = []
    prev = "start"

    parallel_groups = ir.get("parallel_groups") or []
    if parallel_groups:
        nodes.append({"id": "split1", "label": "并行开始", "kind": "parallel_split"})
        edges.append({"from": prev, "to": "split1"})
        branch_ids: list[str] = []
        for gi, pg in enumerate(parallel_groups):
            if not isinstance(pg, dict):
                continue
            items = pg.get("items") or []
            for ii, item in enumerate(items):
                label = str(item if isinstance(item, str) else (item.get("label") if isinstance(item, dict) else ""))
                if not label:
                    continue
                nid = f"p{gi}_{ii}"
                nodes.append({"id": nid, "label": label, "kind": "task"})
                edges.append({"from": "split1", "to": nid})
                branch_ids.append(nid)
                label_index[label] = nid
        join_id = "join1"
        nodes.append({"id": join_id, "label": "汇合", "kind": "parallel_join"})
        for bid in branch_ids:
            edges.append({"from": bid, "to": join_id})
        prev = join_id
    else:
        for i, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            nid = str(step.get("id") or f"s{i}")
            nodes.append({"id": nid, "label": str(step.get("label") or nid), "kind": "task"})
            edges.append({"from": prev, "to": nid})
            prev = nid
            label_index[str(step.get("label") or "")] = nid

    for di, dec in enumerate(ir.get("decisions") or []):
        if not isinstance(dec, dict):
            continue
        did = f"decision_{di}"
        cond = pick_str(dec, "condition", "是否")
        nodes.append({"id": did, "label": cond, "kind": "decision"})
        edges.append({"from": prev, "to": did})
        branches = list(dec.get("branches") or [])
        if len(branches) == 2 and all(not (isinstance(b, dict) and b.get("label")) for b in branches):
            branches = normalize_graph_decisions([dec])[0].get("branches", branches)
        for br in branches:
            if not isinstance(br, dict):
                continue
            tgt_label = str(br.get("target") or "")
            if tgt_label in {"结束", "end", "完成"}:
                tgt = "end"
            else:
                tgt = label_index.get(tgt_label, tgt_label)
            action = str(br.get("action") or "continue")
            edge: dict[str, Any] = {"from": did, "to": tgt, "label": pick_str(br, "label")}
            if action == "loop_back":
                edge["kind"] = "loop_back"
            edges.append(edge)
        prev = did

    nodes.append({"id": "end", "label": "结束", "kind": "end"})
    node_ids = {n["id"] for n in nodes}
    has_out: dict[str, int] = {}
    for e in edges:
        has_out[e["from"]] = has_out.get(e["from"], 0) + 1
    loop_sources = {e["from"] for e in edges if e.get("kind") == "loop_back"}
    for nid in node_ids:
        if nid in {"end", "start"} or nid in loop_sources:
            continue
        if has_out.get(nid, 0) == 0:
            edges.append({"from": nid, "to": "end"})
    if has_out.get(prev, 0) == 0 and prev not in {"end", "start"}:
        edges.append({"from": prev, "to": "end"})

    for loop in ir.get("loops") or []:
        if not isinstance(loop, dict):
            continue
        src = label_index.get(str(loop.get("from") or ""), str(loop.get("from") or ""))
        tgt = label_index.get(str(loop.get("to") or ""), str(loop.get("to") or ""))
        if src and tgt:
            edges.append({"from": src, "to": tgt, "label": str(loop.get("condition") or "返回"), "kind": "loop_back"})

    nodes, edges = apply_dependencies(nodes, edges, ir.get("dependencies"), label_index)
    nodes, edges = apply_optional_branches(nodes, edges, ir.get("optional_branches"), label_index)
    nodes, edges = apply_interrupt_branches(nodes, edges, ir.get("interrupt_branches"), label_index)

    return {"nodes": nodes, "edges": edges}
