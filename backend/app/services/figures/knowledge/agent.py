"""Agent 架构领域知识补全。"""

from __future__ import annotations

from app.services.figures.schemas.dsl import slug_id
from app.services.figures.semantic.schema import SemanticIR, SemanticObject

_AGENT_OBJECTS = [
    ("感知", "process"),
    ("规划", "process"),
    ("工具调用", "module"),
    ("记忆", "database"),
    ("行动", "process"),
]


def complete(ir: SemanticIR) -> SemanticIR:
    ir.domain = "agent"
    if len(ir.objects) < 3:
        ir.objects = [
            SemanticObject(id=slug_id(name, "o"), name=name, kind=kind, importance=2)
            for name, kind in _AGENT_OBJECTS
        ]
        ids = [o.id for o in ir.objects]
        ir.relations = [
            {"from": ids[i], "to": ids[(i + 1) % len(ids)], "verb": "循环", "async": False}
            for i in range(len(ids))
        ]
    ir.layout_hints.append("radial")
    return ir
