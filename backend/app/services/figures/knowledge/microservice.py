"""微服务/架构领域知识补全。"""

from __future__ import annotations

from app.services.figures.schemas.dsl import slug_id
from app.services.figures.semantic.schema import SemanticIR, SemanticObject

_LAYER_TEMPLATES = [
    ("入口层", ["gateway"]),
    ("服务层", ["service"]),
    ("基础设施层", ["queue", "database"]),
]


def complete(ir: SemanticIR) -> SemanticIR:
    if not ir.domain:
        ir.domain = "microservice"
    _ensure_gateway(ir)
    _ensure_groups(ir)
    return ir


def _ensure_gateway(ir: SemanticIR) -> None:
    names = {o.name for o in ir.objects}
    if not any("网关" in n or o.kind == "gateway" for n, o in zip(names, ir.objects)):
        if any(o.kind == "service" for o in ir.objects):
            ir.objects.insert(
                0,
                SemanticObject(id=slug_id("API网关", "o"), name="API网关", kind="gateway", importance=3),
            )


def _ensure_groups(ir: SemanticIR) -> None:
    if ir.groups:
        return
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
