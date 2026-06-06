"""Infographic / chapter-summary parser."""

from __future__ import annotations

import re
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.schemas.diagram import DiagramIntent, ParsedDiagram, PipelineContext
from app.utils.json_llm import parse_llm_json

_PROMPT = """解析信息图/章节总结 JSON。只输出 JSON：
{
  "title": "短标题",
  "blocks": [
    {"label":"信息块短名", "items":["要点1", "要点2"]}
  ]
}
规则：
1. blocks 是信息块/核心要点，不是中心节点的子节点。
2. 根据语义抽取 4-6 个块；每块最多 2 个短要点；不要生成大段文字。
3. block.label 只写概念短名，禁止写“完整信息图”“左侧/右侧”“图标化展示”“卡片布局”等版式说明。
描述：{text}
"""


def _short(text: Any, limit: int = 20) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip()).strip(" ：:，,。\"“”")
    return raw[:limit].strip(" ：:，,。\"“”")


def _split_items(text: str) -> list[str]:
    parts = re.split(r"[、,，/]|和|与", str(text or ""))
    out: list[str] = []
    for part in parts:
        cleaned = re.sub(r"^(?:\d+|[一二两三四五六七八九十])\s*(?:个)?(?:关键)?(?:信息块|要点|概念|模块|图标)[:：]?\s*", "", part.strip())
        cleaned = re.sub(r"^(?:展示|包含|包括|分别是|为)[:：]?\s*", "", cleaned)
        item = _short(cleaned, 18)
        if item:
            out.append(item)
    return out


def _normalize_blocks(raw: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if not isinstance(raw, list):
        return out
    for item in raw[:6]:
        if isinstance(item, str):
            label = _short(item, 18)
            items: list[str] = []
        elif isinstance(item, dict):
            label = _short(item.get("label") or item.get("title") or item.get("name"), 18)
            raw_items = item.get("items") or item.get("points") or []
            items = [_short(x, 16) for x in raw_items if _short(x, 16)] if isinstance(raw_items, list) else _split_items(str(raw_items))[:2]
        else:
            continue
        if label:
            out.append({"label": label, "items": items[:2]})
    return out


def _rule_blocks(text: str) -> list[dict[str, Any]]:
    cleaned = re.sub(r"^图\s*\d+\s*[-–—]\s*\d+\s*[:：]\s*", "", text)
    m = re.search(r"(?:展示|包含[^：:。；;]*|包括[^：:。；;]*|核心要点|关键概念|信息块)[:：]\s*([^。；;]+)", cleaned)
    if not m:
        m = re.search(r"(?:包含|包括|关键概念包括)\s*([^。；;]+)", cleaned)
    raw = m.group(1) if m else cleaned
    if re.search(r"[:：]", raw):
        before, after = re.split(r"[:：]", raw, 1)
        if re.search(r"[、,，/]|和|与", after):
            raw = after
        else:
            raw = before
    raw = re.split(r"(?:，|,|；|;)?\s*(?:用|以|通过)?(?:图标|卡片|分栏|展示|呈现)", raw, 1)[0]
    return [{"label": item, "items": []} for item in _split_items(raw)[:6]]


def _to_graph(title: str, blocks: list[dict[str, Any]]) -> dict[str, Any]:
    nodes = [{"id": "summary", "label": title or "信息图", "shape": "rounded", "level": 0, "column": 0}]
    edges: list[dict[str, str]] = []
    for i, block in enumerate(blocks):
        bid = f"b{i}"
        nodes.append({"id": bid, "label": block["label"], "shape": "box", "level": 1, "column": i})
        edges.append({"from": "summary", "to": bid, "label": ""})
        for j, item in enumerate(block.get("items") or []):
            iid = f"b{i}_{j}"
            nodes.append({"id": iid, "label": item, "shape": "tag", "level": 2, "column": i, "parent": bid})
            edges.append({"from": bid, "to": iid, "label": ""})
    return {
        "diagram_subtype": "infographic",
        "layout": "TB",
        "title": title or "信息图",
        "structure_summary": f"{len(blocks)} 个信息块",
        "blocks": blocks,
        "nodes": nodes,
        "edges": edges,
    }


def parse_infographic(ctx: PipelineContext, intent: DiagramIntent) -> ParsedDiagram:
    model = (ctx.model or settings.intent_model).strip()
    if ctx.use_llm and model:
        try:
            out = LLMClient().chat_completion(
                [{"role": "user", "content": _PROMPT.format(text=ctx.normalized_input[:2500])}],
                model=model,
                max_tokens=2000,
                temperature=0.1,
            )
            data = parse_llm_json(out)
            if isinstance(data, dict):
                blocks = _normalize_blocks(data.get("blocks"))
                if blocks:
                    title = _short(data.get("title") or intent.title or "信息图", 24)
                    return ParsedDiagram(_to_graph(title, blocks), "llm_infographic")
        except Exception:
            pass
    blocks = _rule_blocks(ctx.normalized_input) or [{"label": "要点", "items": []}]
    return ParsedDiagram(_to_graph(_short(intent.title or "信息图", 24), blocks), "rules_infographic")
