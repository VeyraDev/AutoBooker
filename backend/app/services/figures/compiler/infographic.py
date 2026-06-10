"""InfographicCompiler：信息图 blocks → Native IR。"""

from __future__ import annotations

import re
from typing import Any

from app.services.figures.brief.schema import VisualBrief
from app.services.figures.compiler.base import DiagramCompiler
from app.services.figures.contracts.geometry_kinds import GEOMETRY_BLOCKS
from app.services.figures.native.base import NativeIR
from app.services.figures.native.infographic import empty_infographic_ir
from app.services.figures.schemas.diagram import DiagramIntent


def _short(text: Any, limit: int = 18) -> str:
    raw = re.sub(r"\s+", " ", str(text or "").strip()).strip(" ：:，,。\"“”")
    return raw[:limit].strip(" ：:，,。")


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
    for item in raw[:8]:
        if isinstance(item, str):
            label = _short(item, 18)
            items: list[str] = []
        elif isinstance(item, dict):
            label = _short(item.get("label") or item.get("title") or item.get("name"), 18)
            raw_items = item.get("items") or item.get("points") or []
            if isinstance(raw_items, list):
                items = [_short(x, 16) for x in raw_items if _short(x, 16)]
            else:
                items = _split_items(str(raw_items))[:2]
        else:
            continue
        if label:
            out.append({"label": label, "items": items[:2]})
    return out


def _blocks_from_content(content: dict[str, Any], fallback_text: str = "") -> list[dict[str, Any]]:
    blocks = _normalize_blocks(content.get("blocks"))
    if blocks:
        return blocks
    for key in ("sections", "key_points", "highlights", "concepts"):
        blocks = _normalize_blocks(content.get(key))
        if blocks:
            return blocks
    points = content.get("key_points") or content.get("points") or []
    if isinstance(points, list) and points and isinstance(points[0], str):
        return [{"label": _short(p, 18), "items": []} for p in points if _short(p, 18)][:6]
    text = str(content.get("summary") or fallback_text or "")
    cleaned = re.sub(r"^图\s*\d+\s*[-–—]\s*\d+\s*[:：]\s*", "", text)
    m = re.search(r"(?:展示|包含[^：:。；;]*|包括[^：:。；;]*|核心要点|关键概念|信息块)[:：]\s*([^。；;]+)", cleaned)
    if not m:
        m = re.search(r"(?:包含|包括|关键概念包括)\s*([^。；;]+)", cleaned)
    raw = m.group(1) if m else cleaned
    if re.search(r"[:：]", raw):
        before, after = re.split(r"[:：]", raw, 1)
        raw = after if re.search(r"[、,，/]|和|与", after) else before
    raw = re.split(r"(?:，|,|；|;)?\s*(?:用|以|通过)?(?:图标|卡片|分栏|展示|呈现)", raw, 1)[0]
    items = _split_items(raw)
    if items:
        return [{"label": item, "items": []} for item in items[:6]]
    return [{"label": "要点", "items": []}]


class InfographicCompiler(DiagramCompiler):
    def compile(self, brief: VisualBrief, intent: DiagramIntent) -> NativeIR:
        content = dict(brief.content_brief or {})
        ir = empty_infographic_ir()
        ir["geometry_kind"] = GEOMETRY_BLOCKS
        ir["blocks"] = _blocks_from_content(content, fallback_text=brief.title or intent.title or "")
        ir["style_notes"] = list(content.get("style_notes") or content.get("visual_notes") or [])
        vb = brief.visual_brief or {}
        if vb.get("style_intent"):
            ir["style_notes"].append(str(vb.get("style_intent")))
        return NativeIR(
            diagram_type="infographic",
            title=brief.title or intent.title or "信息图",
            structure=ir,
            meta={"geometry_kind": GEOMETRY_BLOCKS},
        ).with_geometry_kind(GEOMETRY_BLOCKS)
