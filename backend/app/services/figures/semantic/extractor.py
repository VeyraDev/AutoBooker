"""Semantic IR 抽取（LLM 主路径 + 旧 semantic_plan fallback）。"""

from __future__ import annotations

import logging
import re
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.parse.semantic_plan import call_semantic_plan
from app.services.figures.prompts import format_prompt
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext
from app.services.figures.semantic.normalizer import is_usable_semantic_ir, normalize_semantic_ir
from app.services.figures.semantic.schema import SemanticEvent, SemanticIR, SemanticObject, SemanticReference
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

_TYPE_MAP = {
    "service": "service",
    "api": "gateway",
    "gateway": "gateway",
    "user": "user",
    "data": "database",
    "database": "database",
    "process": "process",
    "decision": "decision",
    "external": "external",
    "group": "module",
    "queue": "queue",
    "module": "module",
}


def extract_semantic_ir(
    ctx: PipelineContext,
    intent: DiagramIntent,
    *,
    understanding: dict[str, Any] | None = None,
) -> tuple[SemanticIR | None, str]:
    """返回 (SemanticIR, source)。"""
    ir = _call_semantic_ir_llm(ctx, intent, understanding=understanding)
    if ir and is_usable_semantic_ir(ir):
        ir, _ = normalize_semantic_ir(ir)
        return ir, "semantic_ir_llm"

    legacy = call_semantic_plan(ctx, intent)
    if legacy:
        ir = _legacy_to_semantic_ir(legacy, intent)
        ir, _ = normalize_semantic_ir(ir)
        if is_usable_semantic_ir(ir):
            return ir, "semantic_plan_fallback"
    return None, "failed"


def _call_semantic_ir_llm(
    ctx: PipelineContext,
    intent: DiagramIntent,
    *,
    understanding: dict[str, Any] | None = None,
) -> SemanticIR | None:
    model = (ctx.model or settings.intent_model).strip()
    if not ctx.use_llm or not model or not ctx.normalized_input.strip():
        return None
    diagram_type = intent.diagram_type or "flowchart"
    if understanding:
        domain = str(understanding.get("domain") or "")
        if domain:
            diagram_type = diagram_type or "flowchart"
    layout_lines = "\n".join(f"- {x}" for x in (ctx.layout_instructions or [])) or "（无）"
    try:
        prompt = format_prompt(
            "semantic_ir",
            book_type=ctx.book_type or "nonfiction",
            diagram_type=diagram_type,
            text=ctx.normalized_input[:3500],
            layout_instructions=layout_lines,
        )
    except OSError:
        return None
    try:
        out = LLMClient().chat_completion(
            [{"role": "system", "content": "只输出合法 JSON。"}, {"role": "user", "content": prompt}],
            model=model,
            max_tokens=2000,
            temperature=0.0,
        )
        data = parse_llm_json(out)
    except Exception as e:
        logger.warning("semantic_ir LLM failed: %s", e)
        return None
    if not isinstance(data, dict):
        return None
    if understanding and not data.get("domain"):
        data["domain"] = understanding.get("domain") or ""
    return SemanticIR.from_dict(data)


def _legacy_to_semantic_ir(data: dict[str, Any], intent: DiagramIntent) -> SemanticIR:
    objects: list[SemanticObject] = []
    for ent in data.get("entities") or []:
        if not isinstance(ent, dict):
            continue
        objects.append(
            SemanticObject(
                id=str(ent.get("id") or ""),
                name=str(ent.get("name") or ""),
                kind=_TYPE_MAP.get(str(ent.get("type") or "process"), "process"),
                importance=2,
            )
        )
    events: list[SemanticEvent] = []
    for rel in data.get("relations") or []:
        if not isinstance(rel, dict):
            continue
        if rel.get("async"):
            src = str(rel.get("from") or "")
            tgt = str(rel.get("to") or "")
            name_by_id = {o.id: o.name for o in objects}
            events.append(
                SemanticEvent(
                    type="async_notification",
                    sender=name_by_id.get(src, src),
                    receiver=name_by_id.get(tgt, tgt),
                    label=str(rel.get("label") or "异步"),
                    async_flag=True,
                    edge_style="dashed",
                )
            )
    refs: list[SemanticReference] = []
    unknowns: list[str] = []
    for note in data.get("notes") or []:
        note_s = str(note)
        ref = _parse_ordinal_reference(note_s, objects)
        if ref:
            refs.append(ref)
        elif "前" in note_s and "个" in note_s:
            unknowns.append(note_s)
    return SemanticIR(
        diagram_type=str(data.get("diagram_type") or intent.diagram_type or "flowchart"),
        title=str(data.get("title") or intent.title or ""),
        domain="",
        objects=objects,
        events=events,
        relations=[dict(r) for r in (data.get("relations") or []) if isinstance(r, dict)],
        references=refs,
        groups=[dict(g) for g in (data.get("groups") or []) if isinstance(g, dict)],
        unknowns=[str(n) for n in (data.get("notes") or [])] + unknowns,
    )


_ORDINAL_RE = re.compile(r"(.+?)(?:连接|连到|连向)?前([一二三四五六七八九十\d]+)个")
_CN_NUM = {"一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9, "十": 10}


def _parse_ordinal_reference(note: str, objects: list[SemanticObject]) -> SemanticReference | None:
    m = _ORDINAL_RE.search(note)
    if not m:
        return None
    source = m.group(1).strip()
    count_raw = m.group(2)
    count = int(count_raw) if count_raw.isdigit() else _CN_NUM.get(count_raw, 3)
    if not source:
        for obj in objects:
            if obj.kind == "gateway":
                source = obj.name
                break
        if not source and objects:
            source = objects[0].name
    if not source:
        return None
    return SemanticReference(
        type="ordinal_selection",
        source=source,
        target_set="services",
        range_start=1,
        range_end=count,
        action="connect",
    )
