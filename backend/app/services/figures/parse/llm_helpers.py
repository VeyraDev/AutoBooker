"""Grammar parser 共用 LLM 调用与重试辅助。"""

from __future__ import annotations

from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.schemas.diagram import PipelineContext
from app.utils.json_llm import parse_llm_json

_CRITIQUE_SUFFIX = """

【上次输出不合格，请修正】
问题：{critique}
要求：严格按层级嵌套输出 JSON；label 只写实体名，禁止结构词；禁止把所有子节点挂到同一父节点。
"""


def llm_model_for_ctx(ctx: PipelineContext) -> str:
    return (ctx.model or settings.intent_model).strip()


def llm_available(ctx: PipelineContext) -> bool:
    return bool(ctx.use_llm and llm_model_for_ctx(ctx))


def substitute_prompt_text(template: str, ctx: PipelineContext, *, limit: int = 2500) -> str:
    """用 replace 注入描述，避免 JSON 花括号触发 str.format KeyError。"""
    return template.replace("{text}", (ctx.normalized_input or "")[:limit])


def build_prompt(base_prompt: str, ctx: PipelineContext) -> str:
    critique = str(getattr(ctx, "parser_critique", "") or "").strip()
    if critique:
        return base_prompt + _CRITIQUE_SUFFIX.format(critique=critique)
    return base_prompt


def call_llm_json(
    ctx: PipelineContext,
    prompt: str,
    *,
    max_tokens: int = 2200,
    temperature: float = 0.1,
    text_limit: int = 2500,
) -> dict[str, Any] | None:
    model = llm_model_for_ctx(ctx)
    if not llm_available(ctx):
        return None
    try:
        content = build_prompt(substitute_prompt_text(prompt, ctx, limit=text_limit), ctx)
        out = LLMClient().chat_completion(
            [{"role": "user", "content": content}],
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
        )
        data = parse_llm_json(out)
    except Exception:
        return None
    return data if isinstance(data, dict) else None
