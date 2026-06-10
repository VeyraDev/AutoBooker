"""Comparison pros/cons 双栏模板 SVG。"""

from __future__ import annotations

from typing import Any

from app.services.figures.design.render_context import RenderContext
from app.services.figures.render.svg.primitives import rect
from app.services.figures.render.svg.text import multiline_text


def render_comparison_pros_cons(
    spec: dict[str, Any],
    ctx: RenderContext,
    *,
    title: str = "",
) -> list[str]:
    tokens = ctx.tokens
    subjects = list(spec.get("columns") or spec.get("subjects") or [])
    left = str(subjects[0]) if subjects else "方案 A"
    right = str(subjects[1]) if len(subjects) > 1 else "方案 B"
    pros = list(spec.get("pros") or spec.get("left_points") or [])
    cons = list(spec.get("cons") or spec.get("right_points") or [])
    dimensions = list(spec.get("dimensions") or [])
    cell_map: dict[tuple[str, str], str] = {}
    for cell in spec.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        subj = str(cell.get("subject") or cell.get("column") or "")
        dim = str(cell.get("dimension") or cell.get("row") or "")
        val = str(cell.get("value") or cell.get("text") or "")
        if subj and dim and val:
            cell_map[(dim, subj)] = val
    if not pros and dimensions:
        pros = [f"{d}：{cell_map.get((str(d), left), '较优')}" for d in dimensions[:6]]
    if not cons and dimensions:
        cons = [f"{d}：{cell_map.get((str(d), right), '待权衡')}" for d in dimensions[:6]]
    if not pros:
        pros = ["优势项 1", "优势项 2", "优势项 3"]
    if not cons:
        cons = ["劣势项 1", "劣势项 2", "劣势项 3"]

    pro_fill = str(ctx.variant.extras.get("pro_color") or "#DCFCE7")
    con_fill = str(ctx.variant.extras.get("con_color") or "#FEE2E2")
    pad = 48.0
    col_w = 280.0
    gap = 40.0
    w = pad * 2 + col_w * 2 + gap
    h = pad * 2 + 320 + (32 if title else 0)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}">',
        f'<rect width="100%" height="100%" fill="{tokens.background}"/>',
    ]
    if title:
        parts.append(multiline_text(w / 2, pad - 6, title, fill=tokens.text, max_width=w - 80, font_size=16, max_lines=2))

    y0 = pad + (28 if title else 0)
    for side, label, items, fill, x in [
        ("left", left, pros, pro_fill, pad),
        ("right", right, cons, con_fill, pad + col_w + gap),
    ]:
        parts.append(rect(x, y0, col_w, 280, fill=fill, stroke=tokens.border, rx=10))
        parts.append(multiline_text(x + col_w / 2, y0 + 24, label, fill=tokens.text, max_width=col_w - 20, font_size=14, max_lines=2))
        iy = y0 + 52
        for item in items[:8]:
            parts.append(multiline_text(x + 16, iy, f"• {item}", fill=tokens.text, max_width=col_w - 32, font_size=12, max_lines=2))
            iy += 28

    parts.append("</svg>")
    return parts
