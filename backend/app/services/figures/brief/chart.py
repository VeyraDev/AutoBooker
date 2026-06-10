"""Chart Brief LLM。"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.brief.context import build_context, format_intent_result
from app.services.figures.prompts import format_prompt
from app.services.figures.schemas.diagram import PipelineContext
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)


def extract_chart_brief(ctx: PipelineContext, understanding: dict[str, Any]) -> dict[str, Any]:
    model = (ctx.model or settings.intent_model).strip()
    if not ctx.use_llm or not model:
        return {"chart_status": "need_data", "reason": "no_llm"}
    try:
        prompt = format_prompt(
            "chart_brief",
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
        return data if isinstance(data, dict) else {"chart_status": "need_data"}
    except Exception as e:
        logger.warning("chart brief failed: %s", e)
        return {"chart_status": "need_data", "reason": str(e)}
