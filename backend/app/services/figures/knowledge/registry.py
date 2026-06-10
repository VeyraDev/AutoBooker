"""知识补全 — 仅 LLM 增量补全，无领域模板规则。"""

from __future__ import annotations

from app.services.figures.knowledge.llm_completer import llm_complete_knowledge
from app.services.figures.schemas.diagram import PipelineContext
from app.services.figures.semantic.schema import SemanticIR


def complete_knowledge(
    ir: SemanticIR,
    *,
    domain: str = "",
    ctx: PipelineContext | None = None,
) -> tuple[SemanticIR, dict]:
    meta: dict = {"completed": False, "added": [], "source": "none"}
    dom = (domain or ir.domain or "general").lower()

    if ctx and (ir.unknowns or len(ir.objects) < 3):
        ir, llm_meta = llm_complete_knowledge(ir, domain=dom, ctx=ctx)
        if llm_meta.get("completed"):
            meta["completed"] = True
            meta["added"] = list(llm_meta.get("added") or [])
            meta["source"] = llm_meta.get("source") or "llm_knowledge"

    return ir, meta
