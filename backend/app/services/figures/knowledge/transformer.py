"""Transformer/微调领域知识补全。"""

from __future__ import annotations

from app.services.figures.semantic.schema import SemanticIR

_FINETUNE_HINTS = ["数据准备", "模型选择", "训练", "评估", "是否达标"]


def complete(ir: SemanticIR) -> SemanticIR:
    ir.domain = "transformer"
    names = [o.name for o in ir.objects]
    if "微调" in ir.title or any(h in names for h in _FINETUNE_HINTS):
        ir.layout_hints.append("TB_Decision")
    return ir
