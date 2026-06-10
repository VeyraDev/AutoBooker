"""流程图规则（grammar 路径兼容层）→ 控制流语义模块。"""

from __future__ import annotations

from typing import Any

from app.services.figures.semantic.flow_semantic import (
    coerce_process_flow_native,
    infer_process_flow_from_text,
    flow_semantic_critic as process_flow_structure_issues,
    needs_process_flow_repair,
    repair_process_flow_native,
)


def build_default_flow_edges(stages: list[dict[str, Any]], feedback: list[dict[str, Any]] | None = None) -> list[dict[str, str]]:
    """Grammar parser stages 格式 → 边列表（兼容旧 pipeline）。"""
    if len(stages) >= 5 and stages[0].get("kind") == "parallel" and stages[1].get("kind") == "parallel":
        edges: list[dict[str, str]] = [
            {"from": stages[0]["id"], "to": stages[2]["id"], "label": ""},
            {"from": stages[1]["id"], "to": stages[2]["id"], "label": ""},
            {"from": stages[2]["id"], "to": stages[3]["id"], "label": ""},
            {"from": stages[3]["id"], "to": stages[4]["id"], "label": ""},
            {"from": stages[4]["id"], "to": stages[0]["id"], "label": "不达标"},
        ]
    else:
        edges = [
            {"from": stages[i]["id"], "to": stages[i + 1]["id"], "label": ""}
            for i in range(max(0, len(stages) - 1))
        ]
    for edge in feedback or []:
        if isinstance(edge, dict) and edge not in edges:
            edges.append({
                "from": str(edge.get("from") or ""),
                "to": str(edge.get("to") or ""),
                "label": str(edge.get("label") or ""),
            })
    return edges


# 保留旧名供 import
infer_parallel_flow_from_text = infer_process_flow_from_text
