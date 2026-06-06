"""按 domain 注册知识补全器。"""

from __future__ import annotations

from typing import Callable

from app.services.figures.knowledge import agent as agent_knowledge
from app.services.figures.knowledge import microservice as microservice_knowledge
from app.services.figures.knowledge import rag as rag_knowledge
from app.services.figures.knowledge import transformer as transformer_knowledge
from app.services.figures.semantic.schema import SemanticIR

_COMPLETERS: dict[str, Callable[[SemanticIR], SemanticIR]] = {
    "rag": rag_knowledge.complete,
    "microservice": microservice_knowledge.complete,
    "transformer": transformer_knowledge.complete,
    "agent": agent_knowledge.complete,
    "etl": microservice_knowledge.complete,
}


def complete_knowledge(ir: SemanticIR, *, domain: str = "") -> SemanticIR:
    dom = (domain or ir.domain or "general").lower()
    fn = _COMPLETERS.get(dom)
    if fn:
        return fn(ir)
    if dom == "general" and _looks_microservice(ir):
        return microservice_knowledge.complete(ir)
    return ir


def _looks_microservice(ir: SemanticIR) -> bool:
    kinds = {o.kind for o in ir.objects}
    names = " ".join(o.name for o in ir.objects)
    return "service" in kinds or "gateway" in kinds or "微服务" in names or "网关" in names
