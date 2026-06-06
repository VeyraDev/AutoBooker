"""Comparison matrix parser."""

from __future__ import annotations

import re
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.utils.json_llm import parse_llm_json

_PROMPT = """解析对比矩阵 JSON。只输出 JSON：
{
  "title": "短标题",
  "columns": ["对象A", "对象B"],
  "dimensions": ["维度1", "维度2"],
  "cells": [{"dimension":"维度1", "values":{"对象A":"短语", "对象B":"短语"}}]
}
规则：
1. columns 是被比较对象；dimensions 是比较维度；不要输出节点连线图。
2. 根据语义识别对象和维度，不要依赖标点位置。
3. label 只保留对象名或维度名，禁止写“左侧”“右侧”“完整对比图”“横向展示”等版式说明。
4. 如果描述给了每格取值，写入 cells；没有取值时 cells 可为空。
描述：{text}
"""


def _short(text: Any, limit: int = 20) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip()).strip(" ：:，,。")
    return raw[:limit].strip(" ：:，,。")


def _split_items(text: str) -> list[str]:
    parts = re.split(r"[、,，/]|和|与", str(text or ""))
    out: list[str] = []
    for part in parts:
        cleaned = re.sub(r"^(?:对比对象|对象|列|包括|包含|有|为)[:：]?\s*", "", part.strip())
        cleaned = re.sub(r"^(?:两种|三种|四种|五种|六种|多个)\s*", "", cleaned)
        cleaned = re.sub(r"(?:两种|三种|四种|五种|六种)?(?:推理框架|框架|模型|方案|工具|对象|方法)$", "", cleaned)
        item = _short(cleaned, 18)
        if item:
            out.append(item)
    return out


def _rule_columns(text: str) -> list[str]:
    cleaned = re.sub(r"^图\s*\d+\s*[-–—]\s*\d+\s*[:：]\s*", "", text)
    head = re.split(r"(?:对比维度|维度包括|比较维度|从以下维度|评价维度)", cleaned, 1)[0]
    explicit = re.search(r"(?:对比对象|比较对象|列为|对象包括|对象为)[:：]?\s*([^。；;]+)", head)
    if explicit:
        head = explicit.group(1)
    elif "对比" in head:
        left, right = re.split(r"对比", head, 1)
        if re.search(r"[、,，/]|和|与|vs\.?", left, re.I):
            head = left
        elif re.search(r"[:：]", right):
            head = re.split(r"[:：]", right, 1)[1]
        elif re.search(r"[、,，/]|和|与|vs\.?", right, re.I):
            head = right
        else:
            head = left
    if re.search(r"[:：]", head):
        before, after = re.split(r"[:：]", head, 1)
        if re.search(r"[、,，/]|和|与|vs\.?", after, re.I):
            head = after
        else:
            head = before
    head = re.sub(r"(?:对比图|比较图|矩阵图|图表|图)$", "", head.strip())
    head = re.sub(r"(?:三种|两种|四种|五种|六种|多个|不同)$", "", head)
    head = re.sub(r"\bvs\.?\b", "、", head, flags=re.I)
    cols = _split_items(head)
    return cols[:5]


def _rule_dimensions(text: str) -> list[str]:
    m = re.search(r"(?:对比维度包括|对比维度|维度包括|包括)[:：]?\s*([^。；;]+)", text)
    if not m:
        return []
    raw = re.split(r"(?:，横向|，用|，以|，可|，或)", m.group(1), 1)[0]
    raw = re.sub(r"^(?:\d+|[一二两三四五六七八九十])\s*(?:个)?(?:维度|方面)[:：]?\s*", "", raw)
    return _split_items(raw)[:8]


def _normalize_list(raw: Any, limit: int = 8) -> list[str]:
    if not isinstance(raw, list):
        return []
    out = [_short(x, 18) for x in raw if _short(x, 18)]
    return out[:limit]


def _to_graph(title: str, columns: list[str], dimensions: list[str], cells: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = [{"id": "matrix", "label": title or "对比矩阵", "shape": "rounded", "level": 0, "column": 0}]
    edges: list[dict[str, str]] = []
    for i, dim in enumerate(dimensions):
        did = f"d{i}"
        nodes.append({"id": did, "label": dim, "shape": "box", "level": 1, "column": i})
        edges.append({"from": "matrix", "to": did, "label": ""})
    for j, col in enumerate(columns):
        cid = f"c{j}"
        nodes.append({"id": cid, "label": col, "shape": "tag", "level": 2, "column": j})
        if dimensions:
            edges.append({"from": f"d{min(j, len(dimensions) - 1)}", "to": cid, "label": ""})
        else:
            edges.append({"from": "matrix", "to": cid, "label": ""})
    return {
        "diagram_subtype": "comparison_matrix",
        "layout": "TB",
        "title": title or "对比矩阵",
        "structure_summary": f"{len(columns)} 个对象 × {len(dimensions)} 个维度",
        "columns": columns,
        "dimensions": dimensions,
        "cells": cells or [],
        "nodes": nodes,
        "edges": edges,
    }


def parse_comparison(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
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
                columns = _normalize_list(data.get("columns"), 5)
                dimensions = _normalize_list(data.get("dimensions"), 8)
                if columns and dimensions:
                    return ParsedDiagram(
                        _to_graph(_short(data.get("title") or intent.title, 24), columns, dimensions, data.get("cells") or []),
                        "llm_comparison",
                    )
        except Exception:
            pass
    columns = _rule_columns(ctx.normalized_input) or ["对象 A", "对象 B"]
    dimensions = _rule_dimensions(ctx.normalized_input) or ["成本", "速度", "效果", "适用场景"]
    return ParsedDiagram(_to_graph(_short(intent.title or "对比矩阵", 24), columns, dimensions), "rules_comparison")
