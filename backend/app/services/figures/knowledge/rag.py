"""旧领域补全兼容层。

默认结构化生成不再按具体领域补节点；此模块仅保留导入兼容。
"""

from __future__ import annotations

from app.services.figures.semantic.schema import SemanticIR


def complete(ir: SemanticIR) -> tuple[SemanticIR, dict]:
    return ir, {"completed": False, "added": [], "source": "rules_generic_compat"}
