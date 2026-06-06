"""Taxonomy / hierarchy parser."""

from __future__ import annotations

import re
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.utils.json_llm import parse_llm_json

_PROMPT = """解析分类树 JSON。只输出 JSON：
{
  "title": "短标题",
  "root": "根节点",
  "children": [
    {"label":"一级分类", "children":[{"label":"二级分类"}]}
  ]
}
规则：
1. 保留父子层级；不要输出平铺节点列表；label 必须短。
2. label 只写分类名，禁止写“左侧分支”“完整分类图”“图中展示”等版式说明。
描述：{text}
"""


def _short(text: Any, limit: int = 22) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip()).strip(" ：:，,。\"“”")
    return raw[:limit].strip(" ：:，,。\"“”")


def _split_items(text: str) -> list[str]:
    cleaned = re.sub(r"(两类|三类|四类|五类|六类|七类|八类|类别|分类)$", "", str(text or ""))
    parts = re.split(r"[、,，/]|和|与", cleaned)
    return [_short(p, 18) for p in parts if _short(p, 18)]


def _normalize_children(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for item in raw[:8]:
        if isinstance(item, str):
            label = _short(item)
            children: list[dict[str, Any]] = []
        elif isinstance(item, dict):
            label = _short(item.get("label") or item.get("name") or item.get("category"))
            children = _normalize_children(item.get("children") or item.get("items") or [])
        else:
            continue
        if label:
            out.append({"label": label, "children": children})
    return out


def _rule_tree(text: str, intent: DiagramIntent) -> tuple[str, list[dict[str, Any]]]:
    root = ""
    m = re.search(r"根节点为[\"“]?([^\"”。，,；;]+)", text)
    if m:
        root = _short(m.group(1), 20)
    if not root:
        q = re.search(r"[\"“]([^\"”]{2,24})[\"”]", text)
        if q:
            root = _short(q.group(1), 20)
    if not root:
        root = _short(intent.title, 20) or "核心分类"

    groups: list[dict[str, Any]] = []
    top = re.search(r"(?:分为|一级分为)([^。；;]+?)(?:两类|三类|四类|五类|六类|七类|八类|$)", text)
    if top:
        groups = [{"label": item, "children": []} for item in _split_items(top.group(1))]

    if not groups:
        groups = [{"label": item, "children": []} for item in _split_items(text)[:4]]

    by_label = {g["label"]: g for g in groups}
    for clause in re.split(r"[，,；;。]", text):
        m = re.search(r"([^，。；;\s]{2,18})下(?:有|分)(.+)", clause)
        if not m:
            continue
        parent = _short(m.group(1), 18)
        children = [{"label": item, "children": []} for item in _split_items(m.group(2))]
        if parent not in by_label:
            group = {"label": parent, "children": []}
            groups.append(group)
            by_label[parent] = group
        if children:
            by_label[parent]["children"] = children[:8]
    return root, groups[:8]


def _to_graph(title: str, root: str, children: list[dict[str, Any]]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = [{"id": "root", "label": root, "shape": "rounded", "level": 0, "column": 0}]
    edges: list[dict[str, str]] = []
    for i, child in enumerate(children):
        cid = f"c{i}"
        nodes.append({"id": cid, "label": child["label"], "shape": "box", "level": 1, "column": i})
        edges.append({"from": "root", "to": cid, "label": ""})
        for j, grand in enumerate((child.get("children") or [])[:8]):
            gid = f"c{i}_{j}"
            nodes.append({"id": gid, "label": grand["label"], "shape": "tag", "level": 2, "column": i, "parent": cid})
            edges.append({"from": cid, "to": gid, "label": ""})
    return {
        "diagram_subtype": "taxonomy_map",
        "layout": "TB",
        "title": title,
        "structure_summary": f"{root} 的分类树",
        "root": root,
        "children": children,
        "nodes": nodes,
        "edges": edges,
    }


def parse_taxonomy(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    model = (ctx.model or settings.intent_model).strip()
    if ctx.use_llm and model:
        try:
            out = LLMClient().chat_completion(
                [{"role": "user", "content": _PROMPT.format(text=ctx.normalized_input[:2500])}],
                model=model,
                max_tokens=2200,
                temperature=0.1,
            )
            data = parse_llm_json(out)
            if isinstance(data, dict):
                root = _short(data.get("root"), 20)
                children = _normalize_children(data.get("children"))
                if root and children:
                    title = _short(data.get("title") or intent.title or root, 24)
                    return ParsedDiagram(_to_graph(title, root, children), "llm_taxonomy")
        except Exception:
            pass
    root, children = _rule_tree(ctx.normalized_input, intent)
    return ParsedDiagram(_to_graph(_short(intent.title or root, 24), root, children), "rules_taxonomy")
