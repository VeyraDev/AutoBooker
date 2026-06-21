"""规则兜底：从文本推断 nodes/edges。"""

from __future__ import annotations

import re

from app.services.figures.render.legacy_svg.figure_structure import infer_structured_spec
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext

_STOP_CN = {"一个", "一种", "可以", "通过", "进行", "使用", "需要", "包括", "以及", "之间", "关系", "示意图", "核心"}


def _short_title(text: str, *, fallback: str = "概念示意图") -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip())
    raw = re.sub(r"^图\s*\d+\s*[-–—]\s*\d+\s*[:：]\s*", "", raw).strip(" ：:，,。")
    if not raw:
        return fallback
    first = re.split(r"[，,。；;：:\n]", raw, 1)[0].strip(" ：:，,。")
    return (first or raw)[:24].strip(" ：:，,。") or fallback


def _fallback_concept_graph(ctx: PipelineContext, intent: DiagramIntent) -> dict:
    text = ctx.normalized_input.strip()
    title = _short_title(intent.title or text, fallback="概念示意图")
    root_label = re.sub(r"^(请|生成|绘制|画一张)", "", title).strip("：: ，,。")[:16] or "核心概念"

    cn_terms = []
    for term in re.findall(r"[\u4e00-\u9fffA-Za-z0-9+_.-]{2,12}", text):
        if term in _STOP_CN or term == root_label or term in root_label:
            continue
        if term not in cn_terms:
            cn_terms.append(term)
        if len(cn_terms) >= 6:
            break
    if not cn_terms:
        cn_terms = ["输入", "处理", "输出"] if intent.diagram_subtype in {"process_flow", "mechanism_diagram"} else ["要素", "关系", "结果"]

    layout = "LR" if intent.diagram_subtype in {"process_flow", "timeline_roadmap"} else "TB"
    nodes = [{"id": "root", "label": root_label, "shape": "rounded", "level": 0, "column": 0}]
    edges = []
    if layout == "LR":
        prev = "root"
        for i, term in enumerate(cn_terms[:6], start=1):
            nid = f"n{i}"
            nodes.append({"id": nid, "label": term, "shape": "box", "level": i, "column": 0})
            edges.append({"from": prev, "to": nid})
            prev = nid
    else:
        for i, term in enumerate(cn_terms[:6]):
            nid = f"n{i}"
            nodes.append({"id": nid, "label": term, "shape": "box", "level": 1, "column": i})
            edges.append({"from": "root", "to": nid})
    return {"layout": layout, "title": title, "structure_summary": "规则兜底生成的概念结构", "nodes": nodes, "edges": edges}


def parse_fallback(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    spec = infer_structured_spec(ctx.normalized_input) or {}
    if spec:
        return ParsedDiagram(spec, "fallback")
    return ParsedDiagram(_fallback_concept_graph(ctx, intent), "fallback_concept")
