"""Illustration Brief LLM。"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.brief.context import build_context, format_intent_result
from app.services.figures.prompts import format_prompt
from app.services.figures.schemas.diagram import PipelineContext
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)


def extract_illustration_brief(ctx: PipelineContext, understanding: dict[str, Any]) -> dict[str, Any]:
    model = (ctx.model or settings.intent_model).strip()
    if not ctx.use_llm or not model:
        return {"illustration_status": "ready", "illustration_brief": {"scene": ctx.normalized_input[:80]}}
    try:
        prompt = format_prompt(
            "illustration_brief",
            text=ctx.normalized_input[:3500],
            intent_result=format_intent_result(understanding),
            context=build_context(ctx),
        )
        out = LLMClient().chat_completion(
            [{"role": "system", "content": "只输出合法 JSON。"}, {"role": "user", "content": prompt}],
            model=model,
            max_tokens=1600,
            temperature=0.0,
        )
        data = parse_llm_json(out)
        return data if isinstance(data, dict) else {}
    except Exception as e:
        logger.warning("illustration brief failed: %s", e)
        return {"illustration_status": "ready", "illustration_brief": {"scene": ctx.normalized_input[:80]}}


def plan_image_prompt(illustration_brief: dict[str, Any], *, model: str) -> dict[str, Any]:
    try:
        prompt = format_prompt(
            "image_prompt_planner",
            illustration_brief=json.dumps(illustration_brief, ensure_ascii=False)[:4000],
        )
        out = LLMClient().chat_completion(
            [{"role": "system", "content": "只输出合法 JSON。"}, {"role": "user", "content": prompt}],
            model=model,
            max_tokens=1200,
            temperature=0.2,
        )
        data = parse_llm_json(out)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {"prompt": str(illustration_brief.get("scene") or ""), "negative_prompt": ""}
