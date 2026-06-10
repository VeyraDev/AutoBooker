"""Agent 架构领域知识补全（仅增量追加）。"""

from __future__ import annotations

from app.services.figures.knowledge.helpers import append_object_if_missing, link_sequential, should_use_template_completion
from app.services.figures.semantic.schema import SemanticIR

_STANDARD = [
    ("感知", "process"),
    ("规划", "process"),
    ("工具调用", "module"),
    ("记忆", "database"),
    ("行动", "process"),
]


def complete(ir: SemanticIR) -> tuple[SemanticIR, dict]:
    meta: dict = {"completed": False, "added": [], "source": "rules_agent"}
    ir.domain = "agent"

    if ir.objects and not should_use_template_completion(ir):
        ir.layout_hints.append("radial")
        return ir, meta

    added: list[str] = []
    for name, kind in _STANDARD:
        if append_object_if_missing(ir, name, kind):
            added.append(name)

    if len(ir.objects) >= 2:
        ids = [o.id for o in ir.objects]
        for i in range(len(ids)):
            nxt = ids[(i + 1) % len(ids)]
            link_sequential(ir, [ids[i], nxt], verb="循环")

    ir.layout_hints.append("radial")
    if added:
        meta = {"completed": True, "added": added, "source": "rules_agent"}
    return ir, meta
