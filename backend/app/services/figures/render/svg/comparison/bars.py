"""横向条形对比模板 SVG。"""

from __future__ import annotations

from typing import Any

from app.services.figures.design.render_context import RenderContext
from app.services.figures.render.svg.primitives import rect
from app.services.figures.render.svg.text import multiline_text

_POSITIVE = ("高", "快", "强", "优", "好", "较高", "较快", "较低")
_NEGATIVE = ("低", "慢", "弱", "劣", "差", "较高显存")


def _cell_map(spec: dict[str, Any]) -> dict[tuple[str, str], str]:
    out: dict[tuple[str, str], str] = {}
    for cell in spec.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        subj = str(cell.get("subject") or cell.get("column") or "")
        dim = str(cell.get("dimension") or cell.get("row") or "")
        val = str(cell.get("value") or cell.get("text") or "")
        if subj and dim:
            out[(dim, subj)] = val
    return out


def _bar_fill(value: str, tokens) -> str:
    v = value or ""
    if any(k in v for k in _POSITIVE):
        return "#BBF7D0"
    if any(k in v for k in _NEGATIVE):
        return "#FECACA"
    return tokens.card


def render_comparison_bars(
    spec: dict[str, Any],
    ctx: RenderContext,
    *,
    title: str = "",
) -> list[str]:
    tokens = ctx.tokens
    subjects = list(spec.get("columns") or spec.get("subjects") or [])
    dimensions = [str(d) for d in (spec.get("dimensions") or [])]
    cells = _cell_map(spec)
    if not subjects:
        subjects = ["方案A", "方案B"]
    if not dimensions:
        dimensions = ["维度1", "维度2"]

    pad = 48.0
    label_w = 110.0
    bar_max = 280.0
    row_h = 36.0
    group_gap = 28.0
    subj_gap = 8.0
    w = pad * 2 + label_w + bar_max + 80
    h = pad * 2 + len(dimensions) * (len(subjects) * (row_h + subj_gap) + group_gap) + (32 if title else 0)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}">',
        f'<rect width="100%" height="100%" fill="{tokens.background}"/>',
    ]
    if title:
        parts.append(multiline_text(w / 2, pad - 6, title, fill=tokens.text, max_width=w - 80, font_size=16, max_lines=2))

    y = pad + (28 if title else 0)
    for dim in dimensions:
        parts.append(multiline_text(pad, y + 10, str(dim), fill=tokens.text, max_width=label_w - 8, font_size=12, max_lines=2))
        y += 22
        for subj in subjects:
            val = cells.get((str(dim), str(subj)), "—")
            score = min(1.0, max(0.25, len(val) / 8.0))
            if any(k in val for k in _POSITIVE):
                score = 0.85
            elif any(k in val for k in _NEGATIVE):
                score = 0.35
            bw = bar_max * score
            fill = _bar_fill(val, tokens)
            parts.append(rect(pad + label_w, y, bw, row_h - 4, fill=fill, stroke=tokens.border, rx=4))
            parts.append(multiline_text(pad + 4, y + row_h / 2, str(subj), fill=tokens.muted, max_width=label_w - 12, font_size=10, max_lines=1))
            parts.append(multiline_text(pad + label_w + bw + 8, y + row_h / 2, val, fill=tokens.text, max_width=72, font_size=11, max_lines=1))
            y += row_h + subj_gap
        y += group_gap

    parts.append("</svg>")
    return parts
