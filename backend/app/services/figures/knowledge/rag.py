"""RAG 领域知识补全。"""

from __future__ import annotations

from app.services.figures.schemas.dsl import slug_id
from app.services.figures.semantic.schema import SemanticIR, SemanticObject

_RAG_OBJECTS = [
    ("用户查询", "user"),
    ("检索器", "module"),
    ("向量库", "database"),
    ("大模型", "module"),
    ("生成回答", "process"),
]


def complete(ir: SemanticIR) -> SemanticIR:
    ir.domain = "rag"
    if len(ir.objects) < 3:
        ir.objects = [
            SemanticObject(id=slug_id(name, "o"), name=name, kind=kind, importance=2)
            for name, kind in _RAG_OBJECTS
        ]
        ids = [o.id for o in ir.objects]
        ir.relations = [
            {"from": ids[i], "to": ids[i + 1], "verb": "流向", "async": False}
            for i in range(len(ids) - 1)
        ]
    if not ir.groups:
        ir.groups = [
            {"id": "g_retrieval", "label": "检索", "members": [o.id for o in ir.objects if o.kind in {"database", "module"}][:2]},
            {"id": "g_gen", "label": "生成", "members": [o.id for o in ir.objects if o.name in {"大模型", "生成回答"}]},
        ]
    return ir
