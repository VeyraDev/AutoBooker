"""Relationship network / knowledge graph parser."""

from __future__ import annotations

import re
from typing import Any

from app.services.figures.parse.llm_helpers import call_llm_json, llm_available
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext

_PROMPT = """解析关系网络/知识图谱 JSON。只输出 JSON：
{
  "title": "短标题",
  "center": "中心概念",
  "nodes": [{"id":"n1", "label":"概念短名", "role":"center|concept"}],
  "edges": [{"from":"center", "to":"n1", "label":"关系短语"}]
}
规则：
1. 这是关系网络，不是分类树；保留关系边标签；节点 4-10 个。
2. node.label 只写概念短名，edge.label 只写关系短语；禁止写“完整关系图”“中心节点”“横向子节点”等版式说明。
描述：{text}
"""


def _short(text: Any, limit: int = 20) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip()).strip(" ：:，,。\"“”")
    return raw[:limit].strip(" ：:，,。\"“”")


def _split_items(text: str) -> list[str]:
    parts = re.split(r"[、,，/]|和|与", str(text or ""))
    return [_short(p, 18) for p in parts if _short(p, 18)]


def _rule_network(text: str, intent: DiagramIntent) -> tuple[str, list[str], list[dict[str, str]]]:
    center = ""
    m = re.search(r"([^，。；;\s]{2,24})(?:中心|为中心|核心)", text)
    if m:
        center = _short(m.group(1), 18)
    if not center:
        q = re.search(r"[\"“]([^\"”]{2,24})[\"”]", text)
        center = _short(q.group(1), 18) if q else _short(intent.title, 18) or "核心概念"

    relation_clause = ""
    m = re.search(r"(?:连接|关联|周围连接)([^。；;]+)", text)
    if m:
        relation_clause = m.group(1)
    items = [item for item in _split_items(relation_clause or text) if item != center][:8]
    if not items:
        items = ["要素", "关系", "影响"]

    edges = []
    rels = re.findall(r"([^，。；;\s]{2,18})[^，。；;]*?(?:标注|关系类型如|关系为)[\"“]?([^\"”。，,；;]+)", text)
    rel_map = {k: _short(v, 12) for k, v in rels}
    for item in items:
        edges.append({"from": "center", "to": item, "label": rel_map.get(item, "")})
    return center, items, edges


def _normalize_nodes(raw: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return out
    for i, item in enumerate(raw[:10]):
        if isinstance(item, str):
            label = _short(item, 18)
            nid = f"n{i}"
            role = "concept"
        elif isinstance(item, dict):
            label = _short(item.get("label") or item.get("name"), 18)
            nid = str(item.get("id") or f"n{i}").strip()
            role = str(item.get("role") or "concept").strip()
        else:
            continue
        if label:
            out.append({"id": nid, "label": label, "role": role})
    return out


def _normalize_edges(raw: Any, valid: set[str]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    if not isinstance(raw, list):
        return out
    for item in raw[:18]:
        if not isinstance(item, dict):
            continue
        src = str(item.get("from") or item.get("source") or "").strip()
        dst = str(item.get("to") or item.get("target") or "").strip()
        label = _short(item.get("label") or item.get("relation") or "", 12)
        if src in valid and dst in valid and src != dst:
            out.append({"from": src, "to": dst, "label": label})
    return out


def _to_graph(title: str, center: str, concepts: list[str], relation_edges: list[dict[str, str]] | None = None) -> dict[str, Any]:
    nodes = [{"id": "center", "label": center, "shape": "rounded", "level": 0, "column": max(0, len(concepts) // 2)}]
    edges: list[dict[str, str]] = []
    for i, concept in enumerate(concepts):
        nid = f"n{i}"
        nodes.append({"id": nid, "label": concept, "shape": "box", "level": 1, "column": i})
        edge_label = ""
        for edge in relation_edges or []:
            if edge.get("to") in {concept, nid}:
                edge_label = edge.get("label", "")
                break
        edges.append({"from": "center", "to": nid, "label": edge_label})
    return {
        "diagram_subtype": "knowledge_graph",
        "layout": "TB",
        "title": title,
        "structure_summary": f"{center} 的关系网络",
        "center": center,
        "concepts": concepts,
        "nodes": nodes,
        "edges": edges,
    }


def parse_network(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    if llm_available(ctx):
        try:
            data = call_llm_json(ctx, _PROMPT)
            if isinstance(data, dict):
                raw_nodes = _normalize_nodes(data.get("nodes"))
                center_node = next((n for n in raw_nodes if n["role"] == "center"), None)
                center = _short(data.get("center") or (center_node or {}).get("label"), 18)
                concepts = [n["label"] for n in raw_nodes if n["role"] != "center"]
                if center and concepts:
                    valid_ids = {n["id"] for n in raw_nodes} | {"center"}
                    edges = _normalize_edges(data.get("edges"), valid_ids)
                    return ParsedDiagram(_to_graph(_short(data.get("title") or intent.title or center, 24), center, concepts, edges), "llm_network")
        except Exception:
            pass
    center, concepts, edges = _rule_network(ctx.normalized_input, intent)
    return ParsedDiagram(_to_graph(_short(intent.title or center, 24), center, concepts, edges), "rules_network")
