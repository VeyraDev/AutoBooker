"""Comparison cards 模板 SVG。"""

from __future__ import annotations

from typing import Any

from app.services.figures.design.render_context import RenderContext
from app.services.figures.render.svg.primitives import rect, shadow_filter_def
from app.services.figures.render.svg.text import multiline_text


def render_comparison_cards(
    spec: dict[str, Any],
    ctx: RenderContext,
    *,
    title: str = "",
) -> list[str]:
    tokens = ctx.tokens
    subjects = list(spec.get("columns") or spec.get("subjects") or [])
    dimensions = list(spec.get("dimensions") or [])
    if not subjects:
        subjects = [str(n.get("label") or "") for n in (spec.get("nodes") or [])[:6] if isinstance(n, dict) and n.get("label")]

    gap = float(ctx.variant.extras.get("card_gap") or 24)
    cols = min(int(ctx.variant.extras.get("card_columns") or 2), max(1, len(subjects)))
    card_w = 220.0
    card_h = 80.0 + min(4, len(dimensions)) * 22.0
    pad = 48.0
    rows = (len(subjects) + cols - 1) // cols
    w = pad * 2 + cols * card_w + (cols - 1) * gap
    h = pad * 2 + rows * card_h + (rows - 1) * gap + (36 if title else 0)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}">',
        f'<rect width="100%" height="100%" fill="{tokens.background}"/>',
        "<defs>", shadow_filter_def(), "</defs>",
    ]
    if title:
        parts.append(multiline_text(w / 2, pad - 6, title, fill=tokens.text, max_width=w - 80, font_size=16, max_lines=2))

    y0 = pad + (28 if title else 0)
    for i, subj in enumerate(subjects):
        col = i % cols
        row = i // cols
        x = pad + col * (card_w + gap)
        y = y0 + row * (card_h + gap)
        parts.append(rect(x, y, card_w, card_h, fill=tokens.card, stroke=tokens.border, rx=ctx.variant.node_radius, shadow=True))
        parts.append(rect(x, y, card_w, 32, fill=tokens.primary, stroke="none", rx=ctx.variant.node_radius))
        parts.append(multiline_text(x + card_w / 2, y + 16, str(subj), fill="#FFFFFF", max_width=card_w - 16, font_size=13, max_lines=1))
        cell_map: dict[tuple[str, str], str] = {}
        for cell in spec.get("cells") or []:
            if not isinstance(cell, dict):
                continue
            sj = str(cell.get("subject") or cell.get("column") or "")
            dm = str(cell.get("dimension") or cell.get("row") or "")
            val = str(cell.get("value") or cell.get("text") or "")
            if sj and dm:
                cell_map[(dm, sj)] = val
        bullet_y = y + 48
        for d in dimensions[:5]:
            dim_label = str(d.get("name") if isinstance(d, dict) else d)
            val = cell_map.get((dim_label, str(subj)), "")
            line = f"• {dim_label}：{val}" if val else f"• {dim_label}"
            parts.append(multiline_text(x + 14, bullet_y, line, fill=tokens.muted, max_width=card_w - 28, font_size=11, max_lines=2))
            bullet_y += 22

    parts.append("</svg>")
    return parts
