"""Taxonomy / hierarchy parser."""

from __future__ import annotations

import re
from typing import Any

from app.services.figures.parse.llm_helpers import call_llm_json, llm_available
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext

_PROMPT = """解析分类树 JSON。只输出 JSON：
{{
  "title": "短标题",
  "root": "根节点",
  "children": [
    {{"label":"一级分类", "children":[{{"label":"二级分类"}}]}}
  ]
}}
规则：
1. 保留父子层级；不要输出平铺节点列表；label 必须短。
2. 「一级分为 A、B、C」「A 下分/下面有 …」「B 下设 …」必须落成 children 嵌套，禁止把所有叶子都挂到同一个一级节点。
3. 例1：「一级分为甲类与乙类，甲类下有甲一、甲二，乙类下有乙一」→ root + 两级 children。
4. 例2：「一级分为感知、认知、行动三类，感知下分图像识别和语音识别，认知下分自然语言处理和知识推理，行动下分机器人控制和决策优化」
   → children=[{{"label":"感知","children":[...]}}, {{"label":"认知","children":[...]}}, {{"label":"行动","children":[...]}}]
5. label 只写分类名（如「自然语言处理」），禁止把「认知下分」等结构词写进 label。
6. 禁止写“左侧分支”“完整分类图”“图中展示”等版式说明。
描述：{text}
"""


def _short(text: Any, limit: int = 22) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip()).strip(" ：:，,。\"“”")
    return raw[:limit].strip(" ：:，,。\"“”")


def _split_items(text: str) -> list[str]:
    cleaned = re.sub(r"(两类|三类|四类|五类|六类|七类|八类|类别|分类)$", "", str(text or ""))
    parts = re.split(r"[、,，/]|和|与", cleaned)
    return [_clean_taxonomy_label(p) for p in parts if _clean_taxonomy_label(p)]


def _clean_taxonomy_label(text: Any) -> str:
    """去掉误入 label 的「X下分/下有」结构词，只保留分类名。"""
    raw = _short(text, 22)
    raw = re.sub(r"^[^，。；;\s]{0,12}下(?:面)?(?:有|为|分|包含|包括)", "", raw)
    raw = re.sub(r"^(?:一级)?分为", "", raw)
    return _short(raw, 18)


def _normalize_children(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for item in raw[:8]:
        if isinstance(item, str):
            label = _clean_taxonomy_label(item)
            children: list[dict[str, Any]] = []
        elif isinstance(item, dict):
            label = _clean_taxonomy_label(item.get("label") or item.get("name") or item.get("category"))
            children = _normalize_children(item.get("children") or item.get("items") or [])
        else:
            continue
        if label:
            out.append({"label": label, "children": children})
    return out


_CHILD_UNDER_RE = re.compile(
    r"([^，。；;\s]{2,20})下(?:面)?(?:有|为|分|包含|包括)(.+)",
)
_CHILD_BRANCH_RE = re.compile(
    r"([^，。；;\s]{2,20})(?:下设|分支(?:中|里)?(?:有|包括)|之下(?:有|包括))(.+)",
)


def _match_parent_label(parent_raw: str, by_label: dict[str, dict[str, Any]]) -> str | None:
    parent = _short(parent_raw, 18)
    if not parent:
        return None
    if parent in by_label:
        return parent
    for label in by_label:
        if label in parent or parent in label:
            return label
    return parent


def _attach_children(
    by_label: dict[str, dict[str, Any]],
    groups: list[dict[str, Any]],
    parent_raw: str,
    items_text: str,
) -> None:
    parent_key = _match_parent_label(parent_raw, by_label)
    if not parent_key:
        return
    if parent_key not in by_label:
        group = {"label": parent_key, "children": []}
        groups.append(group)
        by_label[parent_key] = group
    children = [{"label": item, "children": []} for item in _split_items(items_text)]
    if children:
        by_label[parent_key]["children"] = children[:8]


def _iter_parent_child_clauses(text: str) -> list[tuple[str, str]]:
    """从正文中提取所有「父节点下分/下有 …」子句（按逗号切段，避免 .+ 吞掉后续父节点）。"""
    pairs: list[tuple[str, str]] = []
    for clause in re.split(r"[。；;]", text or ""):
        for segment in re.split(r"[，,]", clause):
            segment = segment.strip()
            if not segment:
                continue
            for rx in (_CHILD_UNDER_RE, _CHILD_BRANCH_RE):
                m = rx.search(segment)
                if not m:
                    continue
                parent = m.group(1).strip()
                items = m.group(2).strip()
                if parent and items:
                    pairs.append((parent, items))
                break
    return pairs


def _parse_top_level_groups(text: str) -> list[dict[str, Any]]:
    """解析「一级分为 A、B、C（N类）」得到一级 children。"""
    top = re.search(
        r"(?:一级)?分为([^。；;]+?)(?:两类|三类|四类|五类|六类|七类|八类)(?:[，,；;。]|$)",
        text,
    )
    if top:
        return [{"label": item, "children": []} for item in _split_items(top.group(1))]
    m2 = re.search(
        r"(?:一级)?分为([^。；;]+?)(?:两类|三类|四类|五类|六类|七类|八类)",
        text,
    )
    if m2:
        return [{"label": item, "children": []} for item in _split_items(m2.group(1))[:8]]
    m3 = re.search(r"分为([^。；;]+?)(?:两类|三类|四类|五类|六类|七类|八类)", text)
    if m3:
        return [{"label": item, "children": []} for item in _split_items(m3.group(1))[:8]]
    return []


def _infer_root(text: str, intent: DiagramIntent) -> str:
    for pat in (
        r"根节点为[\"“]?([^\"”。，,；;]+)",
        r"以[\"“]([^\"”]{2,24})[\"”]为根",
        r"中心(?:节点|主题)(?:为|是)[\"“]?([^\"”。，,；;]+)",
        r"(.+?)分类图",
        r"(.+?)体系图",
    ):
        m = re.search(pat, text)
        if m:
            root = _short(m.group(1), 20)
            if root and root not in {"完整", "如图", "如下"}:
                return root
    q = re.search(r"[\"“]([^\"”]{2,24})[\"”]", text)
    if q:
        return _short(q.group(1), 20)
    title = _short(intent.title, 20)
    if title and not title.endswith("图"):
        return title
    return title or "核心分类"


def _rule_tree(text: str, intent: DiagramIntent) -> tuple[str, list[dict[str, Any]]]:
    root = _infer_root(text, intent)

    groups = _parse_top_level_groups(text)
    if not groups:
        groups = [{"label": item, "children": []} for item in _split_items(text)[:4]]

    by_label = {g["label"]: g for g in groups}
    for parent_raw, items_text in _iter_parent_child_clauses(text):
        _attach_children(by_label, groups, parent_raw, items_text)
    return root, groups[:8]


def taxonomy_spec_depth(spec: dict[str, Any]) -> int:
    """分类树深度：有孙节点则 >=2。"""
    children = spec.get("children") or []
    if not children:
        edges = spec.get("edges") or []
        if not edges:
            return 0
        depth = 0
        for e in edges:
            if isinstance(e, dict) and e.get("from") == "root":
                depth = max(depth, 1)
            src = str(e.get("from") or "")
            if "_" in src and src.startswith("c"):
                depth = max(depth, 2)
        return depth
    if any(isinstance(c, dict) and c.get("children") for c in children):
        return 2
    return 1 if children else 0


def text_has_taxonomy_hierarchy(text: str) -> bool:
    return bool(
        re.search(
            r"一级分为|分为.{2,40}(?:两类|三类|四类|五类|六类)|"
            r"下(?:面)?(?:有|为|分|包含|包括)|下设|分支(?:中|里)?(?:有|包括)",
            text or "",
            re.I,
        )
    )


def prefer_taxonomy_spec(spec: dict[str, Any], text: str) -> bool:
    if not spec.get("root") or not spec.get("children"):
        return False
    if taxonomy_spec_depth(spec) >= 2:
        return True
    if text_has_taxonomy_hierarchy(text) and len(spec.get("children") or []) >= 2:
        return True
    return False


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
    if llm_available(ctx):
        data = call_llm_json(ctx, _PROMPT)
        if isinstance(data, dict):
            root = _short(data.get("root"), 20)
            children = _normalize_children(data.get("children"))
            if root and children:
                spec = _to_graph(
                    _short(data.get("title") or intent.title or root, 24),
                    root,
                    children,
                )
                if prefer_taxonomy_spec(spec, ctx.normalized_input):
                    return ParsedDiagram(spec, "llm_taxonomy")
        return ParsedDiagram({"title": intent.title or "分类图"}, "llm_taxonomy_failed")

    root, children = _rule_tree(ctx.normalized_input, intent)
    return ParsedDiagram(
        _to_graph(_short(intent.title or root, 24), root, children),
        "rules_taxonomy_fallback",
    )
