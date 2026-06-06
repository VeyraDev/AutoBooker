"""决策流程图渲染。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.figures.render.structured.generic_graph import generate_structured_diagram


def generate_decision_flow_diagram(spec: dict[str, Any], output_path: Path, *, title: str = "") -> tuple[str, Path]:
    """决策流程复用 structured diagram，强制 TB + decision 形状。"""
    patched = dict(spec)
    patched["layout"] = "TB"
    for node in patched.get("nodes") or []:
        if isinstance(node, dict):
            label = str(node.get("label") or "")
            if any(k in label for k in ("是否", "判断", "达标")):
                node["type"] = "decision"
                node["shape"] = "diamond"
    return generate_structured_diagram(patched, output_path, title=title)
