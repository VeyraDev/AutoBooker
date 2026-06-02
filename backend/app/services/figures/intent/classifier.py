"""Diagram Intent LLM 分类（仅 family + subtype，不抽结构）。"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.intent.taxonomy import FAMILY_DEFAULT_SUBTYPE
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

_INTENT_PROMPT = """你是图书配图类型识别模块。只判断图形族与细分类，不要输出 nodes/edges/prompt。
只输出 JSON：
{{
  "diagram_family": "architecture|decision|workflow|matrix|knowledge|timeline|organization|illustration|data",
  "diagram_subtype": "transformer|rag|decision_tree|swot|attention_matrix|process_flow|chart|infographic|...",
  "confidence": 0.0,
  "title": "图题建议"
}}

示例：
- Transformer 编码器解码器 → architecture / transformer
- 决策树三分支 → decision / decision_tree
- RAG 检索生成 → architecture / rag
- SWOT 分析 → matrix / swot
- 场景插画 → illustration / scene_illustration

书型：{book_type} / 风格：{style_type}
章节：{chapter_title}
用户补充：{user_hint}
描述：
{normalized_input}
"""


def classify_diagram_intent(ctx: PipelineContext) -> DiagramIntent | None:
    model = (ctx.model or settings.intent_model).strip()
    if not model or not ctx.normalized_input.strip():
        return None
    prompt = _INTENT_PROMPT.format(
        book_type=ctx.book_type or "nonfiction",
        style_type=ctx.style_type or "general",
        chapter_title=ctx.chapter_title or "（无）",
        user_hint=ctx.user_hint or "（无）",
        normalized_input=ctx.normalized_input[:2500],
    )
    try:
        client = LLMClient()
        out = client.chat_completion(
            [
                {"role": "system", "content": "只输出合法 JSON。"},
                {"role": "user", "content": prompt},
            ],
            model=model,
            max_tokens=512,
            temperature=0.1,
        )
        data = parse_llm_json(out)
        return _sanitize_intent(data)
    except Exception as e:
        logger.warning("diagram intent LLM failed: %s", e)
        return None


def _sanitize_intent(data: dict[str, Any]) -> DiagramIntent | None:
    family = str(data.get("diagram_family") or "").strip().lower()
    subtype = str(data.get("diagram_subtype") or "").strip().lower()
    if not family:
        return None
    if not subtype:
        subtype = FAMILY_DEFAULT_SUBTYPE.get(family, "concept_illustration")
    try:
        conf = float(data.get("confidence", 0.7))
    except (TypeError, ValueError):
        conf = 0.7
    title = str(data.get("title") or "").strip()
    return DiagramIntent(family, subtype, max(0.0, min(1.0, conf)), "llm", title)
