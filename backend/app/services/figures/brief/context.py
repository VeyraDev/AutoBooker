"""Brief LLM 上下文拼装。"""

from __future__ import annotations

from app.services.figures.schemas.diagram import PipelineContext


def build_context(ctx: PipelineContext) -> str:
    parts: list[str] = []
    if ctx.book_type:
        parts.append(f"book_type={ctx.book_type}")
    if ctx.chapter_title:
        parts.append(f"chapter={ctx.chapter_title}")
    if ctx.style_type:
        parts.append(f"style={ctx.style_type}")
    if ctx.layout_instructions:
        parts.append("layout_preferences=" + "; ".join(ctx.layout_instructions[:8]))
    if ctx.subtype_hint:
        parts.append(f"subtype_hint={ctx.subtype_hint}")
    return "\n".join(parts) or "（无）"


def format_intent_result(understanding: dict) -> str:
    import json

    return json.dumps(understanding, ensure_ascii=False)[:4000]
