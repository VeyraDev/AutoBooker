"""LLM 增量知识补全（knowledge_completion.txt）。"""

from __future__ import annotations

import json
import logging
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.prompts import format_prompt
from app.services.figures.schemas.diagram import PipelineContext
from app.services.figures.semantic.normalizer import normalize_semantic_ir
from app.services.figures.semantic.schema import SemanticIR, SemanticObject
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)


def llm_complete_knowledge(
    ir: SemanticIR,
    *,
    domain: str,
    ctx: PipelineContext | None = None,
) -> tuple[SemanticIR, dict[str, Any]]:
    """对 unknowns 与稀疏 IR 做 LLM 增量补全。"""
    meta: dict[str, Any] = {"completed": False, "added": [], "source": "none"}
    model = (ctx.model if ctx else "") or settings.intent_model
    if not model or not (ctx and ctx.use_llm):
        return ir, meta
    if not ir.unknowns and len(ir.objects) >= 3:
        return ir, meta

    try:
        prompt = format_prompt(
            "knowledge_completion",
            domain=domain or ir.domain or "general",
            semantic_ir_json=json.dumps(ir.to_dict(), ensure_ascii=False)[:3000],
        )
    except OSError:
        return ir, meta

    try:
        out = LLMClient().chat_completion(
            [{"role": "system", "content": "只输出合法 JSON。"}, {"role": "user", "content": prompt}],
            model=model.strip(),
            max_tokens=1200,
            temperature=0.0,
        )
        data = parse_llm_json(out)
    except Exception as exc:
        logger.warning("knowledge_completion LLM failed: %s", exc)
        return ir, meta

    if not isinstance(data, dict):
        return ir, meta

    added: list[str] = []
    existing_ids = set(ir.object_ids())
    existing_names = {o.name for o in ir.objects}

    for raw in data.get("objects") or []:
        if not isinstance(raw, dict):
            continue
        name = str(raw.get("name") or "").strip()
        if not name or name in existing_names:
            continue
        ir.objects.append(
            SemanticObject(
                id=str(raw.get("id") or f"o{len(ir.objects) + 1}"),
                name=name[:16],
                kind=str(raw.get("kind") or "process"),
                importance=int(raw.get("importance") or 2),
            )
        )
        added.append(name)
        existing_names.add(name)

    for rel in data.get("relations") or []:
        if isinstance(rel, dict) and rel.get("from") and rel.get("to"):
            ir.relations.append(dict(rel))

    for evt in data.get("events") or []:
        if isinstance(evt, dict):
            from app.services.figures.semantic.schema import SemanticEvent

            ir.events.append(SemanticEvent.from_dict(evt))

    for grp in data.get("groups") or []:
        if isinstance(grp, dict):
            ir.groups.append(dict(grp))

    if added:
        ir, _ = normalize_semantic_ir(ir)
        meta = {"completed": True, "added": added, "source": "llm"}
    return ir, meta
