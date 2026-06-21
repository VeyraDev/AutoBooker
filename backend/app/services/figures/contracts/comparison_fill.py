"""对比图 cells 补全与版式推断。"""

from __future__ import annotations

import re
from typing import Any


def infer_comparison_format(text: str, visual_brief: dict[str, Any] | None = None) -> str:
    vb = visual_brief or {}
    explicit = str(vb.get("comparison_format") or vb.get("layout_intent") or "").lower()
    if explicit in {"side_by_side", "two_column", "pros_cons", "cards"}:
        return "pros_cons" if explicit == "side_by_side" else explicit
    if explicit in {"bar", "bar_horizontal", "horizontal_bar"}:
        return "bar_horizontal"
    if explicit in {"radar", "spider"}:
        return "radar"
    if explicit in {"matrix", "table"}:
        return "matrix"
    t = (text or "").lower()
    if any(k in t for k in ("雷达图", "radar", "蜘蛛图")):
        return "radar"
    if any(k in t for k in ("条形", "横向", "bar chart", "柱状对比")):
        return "bar_horizontal"
    if any(k in t for k in ("两列", "并排", "左右对比", "卡片")):
        return "pros_cons"
    if any(k in t for k in ("表格", "矩阵", "逐格")):
        return "matrix"
    return ""


def fill_comparison_cells(content: dict[str, Any], *, source_text: str = "") -> dict[str, Any]:
    out = dict(content or {})
    subjects = [str(s).strip() for s in (out.get("subjects") or out.get("columns") or []) if str(s).strip()]
    dims_raw = out.get("dimensions") or []
    dimensions: list[str] = []
    dim_values: dict[str, dict[str, str]] = {}

    for d in dims_raw:
        if isinstance(d, dict):
            name = str(d.get("name") or d.get("label") or "").strip()
            if name:
                dimensions.append(name)
            vals = d.get("values") or d.get("ratings") or {}
            if isinstance(vals, dict) and name:
                dim_values[name] = {str(k): str(v) for k, v in vals.items()}
        elif d:
            dimensions.append(str(d).strip())

    if not subjects:
        subjects = _extract_subjects_from_text(source_text)
    if not dimensions:
        dimensions = _extract_dimensions_from_text(source_text)

    cells = list(out.get("cells") or [])
    cell_map = {(str(c.get("subject") or c.get("column")), str(c.get("dimension") or c.get("row"))): c for c in cells if isinstance(c, dict)}

    for subj in subjects:
        for dim in dimensions:
            key = (subj, dim)
            if key in cell_map and str(cell_map[key].get("value") or cell_map[key].get("text") or "").strip():
                continue
            val = (dim_values.get(dim) or {}).get(subj, "")
            if not val:
                val = _infer_cell_value(subj, dim, source_text)
            if not val:
                val = "—"
            cells.append({"subject": subj, "dimension": dim, "value": val})

    out["subjects"] = subjects
    out["dimensions"] = dimensions
    out["cells"] = cells
    return out


def _extract_subjects_from_text(text: str) -> list[str]:
    t = text or ""
    vs = re.findall(r"([\u4e00-\u9fffA-Za-z0-9+]+)\s*(?:与|和|vs\.?|VS)\s*([\u4e00-\u9fffA-Za-z0-9+]+)", t)
    if vs:
        return [vs[0][0], vs[0][1]]
    quoted = re.findall(r"[《\"]([^《》\"]{2,24})[》\"]", t)
    tokens = re.findall(r"\b[A-Za-z][A-Za-z0-9+._-]{1,24}\b", t)
    cn_terms = re.findall(r"[\u4e00-\u9fff]{2,8}", t)
    m = [*quoted, *tokens, *cn_terms]
    stop = {"比较", "对比", "方案", "维度", "区别", "差异", "优缺点", "优劣势"}
    return [x for x in list(dict.fromkeys(m)) if x not in stop][:6] or ["方案A", "方案B"]


def _extract_dimensions_from_text(text: str) -> list[str]:
    found = re.findall(r"(显存需求|训练速度|效果上限|适用场景|吞吐量|延迟|易用性|社区活跃度|成本|速度|效果)", text)
    return list(dict.fromkeys(found))[:8] or ["维度1", "维度2"]


def _infer_cell_value(subject: str, dimension: str, text: str) -> str:
    """从正文中粗略匹配「对象+维度」描述；否则给出可读的默认对比项。"""
    if text:
        pattern = rf"{re.escape(subject)}[^。；;]{{0,40}}{re.escape(dimension)}[^。；;]{{0,20}}([高低中快慢强弱优略较好差]+)"
        m = re.search(pattern, text)
        if m:
            return m.group(1)[:16]
    return _default_cell_value(subject, dimension)


def _default_cell_value(subject: str, dimension: str) -> str:
    dim = dimension.lower()
    subj = subject
    if "显存" in dim or "内存" in dim:
        return "待补充"
    if "速度" in dim or "延迟" in dim:
        return "较快"
    if "效果" in dim or "上限" in dim:
        return "较好"
    if "易用" in dim:
        return "中等"
    return "见说明"
