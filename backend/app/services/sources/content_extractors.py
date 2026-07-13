"""Heuristic pre-split hints before LLM segment extraction."""

from __future__ import annotations

import re
from typing import Any

_SEGMENT_KEYWORDS: dict[str, list[str]] = {
    "outline": ["目录", "大纲", "章节", "第.*章", "contents"],
    "requirement": ["写作要求", "注意事项", "禁止", "必须", "规范", "要求"],
    "bibliography": ["参考文献", "references", "bibliography", "引用文献"],
    "manuscript": ["正文", "初稿", "第一章", "第二章", "前言"],
    "chapter_draft": ["章节草稿", "章稿", "section"],
}


def heuristic_segments(text: str) -> list[dict[str, Any]]:
    """Return lightweight segment hints when LLM is unavailable."""
    if len(text.strip()) < 120:
        return []
    lowered = text.lower()
    found: list[dict[str, Any]] = []
    for seg_type, keys in _SEGMENT_KEYWORDS.items():
        hits = [k for k in keys if re.search(k, text, re.I) or k.lower() in lowered]
        if not hits:
            continue
        idx = min(text.lower().find(hits[0].lower()), len(text) - 1) if hits else 0
        excerpt = text[max(0, idx) : idx + 200].strip()
        found.append(
            {
                "segment_type": seg_type,
                "summary": f"检测到可能与「{hits[0]}」相关的片段",
                "locator": f"约第 {max(1, idx // 400 + 1)} 段",
                "confidence": 0.55,
                "suggested_usage": "请用户确认该片段的实际用途",
                "excerpt": excerpt[:200],
            }
        )
    if len(found) < 2 and len(text) > 800:
        found.append(
            {
                "segment_type": "requirement",
                "summary": "未能明确分类的正文片段，可能含写作要求或背景说明",
                "locator": "全文",
                "confidence": 0.45,
                "suggested_usage": "请用户说明是否纳入写作约束",
                "excerpt": text[:200],
            }
        )
    return found[:6]
