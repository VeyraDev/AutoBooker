"""配图 DOT / 语义轻量校验。"""

from __future__ import annotations

import re
from typing import Any


def validate_dot_structure(dot: str, *, image_type: str = "process_flow") -> list[str]:
    errors: list[str] = []
    d = (dot or "").strip()
    if not d:
        return ["DOT 为空"]
    if not re.search(r"(?is)(?:di)?graph\s+\w*\s*\{", d):
        errors.append("缺少 digraph/graph 声明")
    node_ids = re.findall(r"\b(\w+)\s*\[", d)
    if len(node_ids) > 15:
        errors.append(f"节点数过多 ({len(node_ids)} > 15)")
    if image_type == "decision_tree":
        diamonds = len(re.findall(r"shape\s*=\s*diamond", d, re.I))
        if diamonds != 1:
            errors.append(f"决策树应有 1 个菱形节点，当前 {diamonds}")
    return errors


def validate_semantic_keywords(description: str, render_spec: str) -> list[str]:
    """检查描述中的关键实体是否出现在 DOT/spec 中。"""
    warnings: list[str] = []
    keywords: list[str] = []
    for m in re.finditer(r"[A-Za-z][A-Za-z0-9+_.-]{1,20}", description):
        kw = m.group(0)
        if kw.lower() not in ("the", "and", "for", "with", "n", "x"):
            keywords.append(kw)
    for cn in re.findall(r"[\u4e00-\u9fff]{2,8}", description):
        if cn not in ("架构", "编码器", "解码器", "注意力", "矩阵", "窗口", "完整", "滑动"):
            keywords.append(cn)
    spec_lower = (render_spec or "").casefold()
    for kw in keywords[:8]:
        if kw.casefold() not in spec_lower and kw not in (render_spec or ""):
            warnings.append(f"可能缺少关键实体: {kw}")
    return warnings


def validate_rendered_png(path: "Path") -> list[str]:
    """轻量渲染质检：文件存在且尺寸合理。"""
    from pathlib import Path as P

    p = P(path)
    warnings: list[str] = []
    if not p.is_file():
        return ["PNG 文件未生成"]
    if p.stat().st_size < 800:
        warnings.append("图片文件过小，可能渲染失败")
    return warnings


def merge_validation_report(dot: str, description: str, image_type: str) -> dict[str, Any]:
    structural = validate_dot_structure(dot, image_type=image_type)
    semantic = validate_semantic_keywords(description, dot)
    return {"ok": not structural, "structural_errors": structural, "semantic_warnings": semantic}
