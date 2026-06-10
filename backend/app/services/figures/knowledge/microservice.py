"""微服务/架构领域知识补全。"""

from __future__ import annotations

from app.services.figures.knowledge.helpers import append_object_if_missing
from app.services.figures.schemas.dsl import slug_id
from app.services.figures.semantic.schema import SemanticIR, SemanticObject


def complete(ir: SemanticIR) -> tuple[SemanticIR, dict]:
    meta: dict = {"completed": False, "added": [], "source": "rules_microservice"}
    if not ir.domain:
        ir.domain = "microservice"

    added: list[str] = []
    if not any("网关" in o.name or o.kind == "gateway" for o in ir.objects):
        if any(o.kind == "service" for o in ir.objects):
            oid = append_object_if_missing(ir, "API网关", "gateway", importance=3)
            if oid:
                added.append("API网关")

    if not ir.groups:
        buckets: dict[str, list[str]] = {"入口层": [], "服务层": [], "基础设施层": []}
        for obj in ir.objects:
            if obj.kind == "gateway":
                buckets["入口层"].append(obj.id)
            elif obj.kind in {"queue", "database", "cache"}:
                buckets["基础设施层"].append(obj.id)
            else:
                buckets["服务层"].append(obj.id)
        for label, members in buckets.items():
            if members:
                ir.groups.append({"id": slug_id(label, "g"), "label": label, "members": members})

    if added:
        meta = {"completed": True, "added": added, "source": "rules_microservice"}
    return ir, meta
