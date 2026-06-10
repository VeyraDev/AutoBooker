"""RAG 领域知识补全（仅增量追加）。"""

from __future__ import annotations

from app.services.figures.knowledge.helpers import (
    append_object_if_missing,
    has_object_named,
    link_sequential,
    should_use_template_completion,
)
from app.services.figures.semantic.schema import SemanticIR

_STANDARD = [
    ("用户查询", "user"),
    ("检索器", "module"),
    ("向量库", "database"),
    ("大模型", "module"),
]


def complete(ir: SemanticIR) -> tuple[SemanticIR, dict]:
    meta: dict = {"completed": False, "added": [], "source": "rules_rag"}
    ir.domain = "rag"

    if not ir.objects and not should_use_template_completion(ir):
        return ir, meta

    added: list[str] = []
    new_ids: list[str] = []
    for name, kind in _STANDARD:
        oid = append_object_if_missing(ir, name, kind)
        if oid:
            added.append(name)
            new_ids.append(oid)

    if added and len(ir.objects) >= 2:
        all_ids = [o.id for o in ir.objects]
        link_sequential(ir, all_ids)

    if not ir.groups and has_object_named(ir, "检索", "向量", "大模型"):
        retrieval = [
            o.id for o in ir.objects
            if (o.kind in {"database", "module"} and ("检索" in o.name or "向量" in o.name))
        ]
        gen = [o.id for o in ir.objects if "大模型" in o.name or o.name == "生成回答"]
        if retrieval:
            ir.groups.append({"id": "g_retrieval", "label": "检索", "members": retrieval[:2]})
        if gen:
            ir.groups.append({"id": "g_gen", "label": "生成", "members": gen})

    if added:
        meta = {"completed": True, "added": added, "source": "rules_rag"}
    return ir, meta
