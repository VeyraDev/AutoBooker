"""Semantic Native IR 抽取（V2 遗留，主路径已迁移至 brief/compiler）。"""

from __future__ import annotations

import logging
import warnings
from typing import Any

from app.config import settings
from app.llm.client import LLMClient
from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.prompts import format_prompt
from app.services.figures.schemas.diagram import DiagramIntent, PipelineContext
from app.services.figures.semantic.critic import run_semantic_critic
from app.services.figures.semantic.normalizer import is_usable_semantic_ir, normalize_semantic_ir
from app.services.figures.semantic.repair import repair_semantic_ir
from app.services.figures.semantic.schema import SemanticIR
from app.utils.json_llm import parse_llm_json

logger = logging.getLogger(__name__)

MAX_REPAIR_ATTEMPTS = 2


def extract_semantic_ir(
    ctx: PipelineContext,
    intent: DiagramIntent,
    *,
    understanding: dict[str, Any] | None = None,
) -> tuple[SemanticIR | None, str]:
    """Intent Understanding → Semantic Native IR → Critic → Repair（已废弃，仅供测试/兼容）。"""
    warnings.warn(
        "extract_semantic_ir is deprecated; use brief.visual + compiler.registry",
        DeprecationWarning,
        stacklevel=2,
    )
    ir = _call_semantic_ir_llm(ctx, intent, understanding=understanding)
    source = "semantic_native_llm"

    if not ir:
        ir = _minimal_semantic_ir(intent, ctx, understanding)
        source = "semantic_minimal_fallback"

    subtype = canonical_subtype(intent.diagram_subtype)
    ir, _ = normalize_semantic_ir(ir, subtype=subtype, text=ctx.normalized_input)
    critic_meta: list[dict[str, Any]] = []

    for attempt in range(MAX_REPAIR_ATTEMPTS + 1):
        critic = run_semantic_critic(
            ir,
            ctx.normalized_input,
            ctx=ctx,
            diagram_type=intent.diagram_type or "",
            diagram_subtype=subtype,
        )
        critic_meta.append(critic)
        if critic.get("passed") and is_usable_semantic_ir(ir, subtype=intent.diagram_subtype):
            ctx.pipeline_trace.append({
                "step": "semantic_critic",
                "passed": True,
                "attempt": attempt,
                "source": source,
            })
            return ir, source

        if attempt >= MAX_REPAIR_ATTEMPTS:
            break

        repaired = repair_semantic_ir(ctx, intent, ir, critic.get("issues") or [], understanding=understanding)
        if repaired:
            ir, _ = normalize_semantic_ir(repaired, subtype=subtype, text=ctx.normalized_input)
            source = "semantic_native_repaired"
        else:
            break

    ctx.pipeline_trace.append({
        "step": "semantic_critic",
        "passed": False,
        "issues": critic_meta[-1].get("issues") if critic_meta else [],
        "source": source,
    })

    minimal = _minimal_semantic_ir(intent, ctx, understanding)
    minimal, _ = normalize_semantic_ir(minimal, subtype=subtype, text=ctx.normalized_input)
    from app.services.figures.semantic.flow_semantic import repair_process_flow_native

    repaired_native = repair_process_flow_native(minimal.native_structure or {}, ctx.normalized_input)
    if repaired_native.get("nodes"):
        minimal = SemanticIR(
            diagram_type=minimal.diagram_type,
            title=minimal.title,
            domain=minimal.domain,
            native_structure=repaired_native,
            visual_intent=minimal.visual_intent,
        )
    if is_usable_semantic_ir(minimal, subtype=intent.diagram_subtype):
        return minimal, "semantic_rule_fallback"

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
    diagram_subtype = canonical_subtype(intent.diagram_subtype)
    layout_lines = "\n".join(f"- {x}" for x in (ctx.layout_instructions or [])) or "（无）"
    try:
        prompt = format_prompt(
            "semantic_ir",
            book_type=ctx.book_type or "nonfiction",
            diagram_type=diagram_type,
            diagram_subtype=diagram_subtype,
            text=ctx.normalized_input[:3500],
            layout_instructions=layout_lines,
        )
    except OSError:
        return None
    try:
        out = LLMClient().chat_completion(
            [{"role": "system", "content": "只输出合法 JSON。"}, {"role": "user", "content": prompt}],
            model=model,
            max_tokens=2400,
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


def _minimal_semantic_ir(
    intent: DiagramIntent,
    ctx: PipelineContext,
    understanding: dict[str, Any] | None,
) -> SemanticIR:
    """最后兜底：按 intent subtype 构造最小 native_structure（非 objects 扁平）。"""
    from app.services.figures.intent.taxonomy import canonical_subtype, subtype_to_diagram_type

    subtype = canonical_subtype(intent.diagram_subtype)
    title = intent.title or ctx.normalized_input[:24] or "示意图"
    from app.services.figures.semantic.native_bridge import expected_native_type

    ntype = expected_native_type(subtype)
    native: dict[str, Any] = {"type": ntype, "title": title}
    if ntype == "concept":
        native["concepts"] = [title]
        native["relations"] = []
    elif ntype == "infographic":
        native["blocks"] = [{"label": title[:12], "items": []}]
    elif ntype == "process_flow":
        from app.services.figures.semantic.flow_semantic import infer_any_flow_from_text

        inferred = infer_any_flow_from_text(ctx.normalized_input)
        if inferred:
            native = inferred

    return SemanticIR(
        diagram_type=intent.diagram_type or subtype_to_diagram_type(subtype),
        title=title,
        domain=str((understanding or {}).get("domain") or "general"),
        native_structure=native,
        visual_intent={"goal": (understanding or {}).get("goal") or ""},
    )
