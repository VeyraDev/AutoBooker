"""Semantic Native IR 修复（LLM，基于 critic 报告）。"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.prompts import format_prompt
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext
from app.services.figures.semantic.schema import SemanticIR
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)


def repair_semantic_ir(
    ctx: PipelineContext,
    intent: DiagramIntent,
    ir: SemanticIR,
    issues: list[str],
    *,
    understanding: dict[str, Any] | None = None,
) -> SemanticIR | None:
    model = (ctx.model or settings.intent_model).strip()
    if not ctx.use_llm or not model or not issues:
        return None
    try:
        prompt = format_prompt(
            "semantic_repair",
            diagram_type=intent.diagram_type or ir.diagram_type,
            diagram_subtype=canonical_subtype(intent.diagram_subtype),
            text=ctx.normalized_input[:3500],
            issues="\n".join(f"- {x}" for x in issues[:12]),
            semantic_json=json.dumps(ir.to_dict(), ensure_ascii=False)[:4000],
        )
    except OSError:
        return None
    try:
        out = LLMClient().chat_completion(
            [{"role": "system", "content": "只输出合法 JSON。"}, {"role": "user", "content": prompt}],
            model=model,
            max_tokens=2400,
            temperature=0.1,
        )
        data = parse_llm_json(out)
    except Exception as e:
        logger.warning("semantic repair LLM failed: %s", e)
        return None
    if not isinstance(data, dict):
        return None
    if understanding and not data.get("domain"):
        data["domain"] = understanding.get("domain") or ir.domain
    return SemanticIR.from_dict(data)
