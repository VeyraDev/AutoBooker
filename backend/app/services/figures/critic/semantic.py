"""可选 LLM Critic：描述与节点标签对齐（warning 级）。"""

from __future__ import annotations

import logging
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.prompts import format_prompt
from app.services.figures.schemas.diagram import PipelineContext
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)


def run_semantic_llm_critic(
    ctx: PipelineContext,
    *,
    semantic_ir: dict[str, Any] | None,
    node_labels: list[str],
) -> dict[str, Any]:
    warnings: list[str] = []
    missing: list[str] = []
    mislabeled: list[str] = []

    model = (ctx.model or settings.intent_model).strip()
    if not ctx.use_llm or not model or not node_labels:
        return {"warnings": warnings, "missing": missing, "mislabeled": mislabeled}

    try:
        prompt = format_prompt(
            "critic_semantic",
            text=ctx.normalized_input[:2000],
            semantic_summary=str((semantic_ir or {}).get("title") or "")[:200],
            node_labels="、".join(node_labels[:24]),
        )
    except OSError:
        return {"warnings": warnings, "missing": missing, "mislabeled": mislabeled}

    try:
        out = LLMClient().chat_completion(
            [{"role": "system", "content": "只输出合法 JSON。"}, {"role": "user", "content": prompt}],
            model=model,
            max_tokens=600,
            temperature=0.0,
        )
        data = parse_llm_json(out)
    except Exception as exc:
        logger.warning("semantic critic LLM failed: %s", exc)
        return {"warnings": warnings, "missing": missing, "mislabeled": mislabeled}

    if isinstance(data, dict):
        missing = [str(x) for x in (data.get("missing") or [])[:8]]
        mislabeled = [str(x) for x in (data.get("mislabeled") or [])[:8]]
        if missing or mislabeled:
            warnings.append("semantic_llm_critic")

    return {"warnings": warnings, "missing": missing, "mislabeled": mislabeled}
