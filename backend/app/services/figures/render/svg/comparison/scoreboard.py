"""Comparison scoreboard 排名模板 SVG。"""

from __future__ import annotations

from typing import Any

from app.services.figures.design.render_context import RenderContext
from app.services.figures.render.svg.primitives import rect
from app.services.figures.render.svg.text import multiline_text


def render_comparison_scoreboard(
    spec: dict[str, Any],
    ctx: RenderContext,
    *,
    title: str = "",
) -> list[str]:
    tokens = ctx.tokens
    subjects = list(spec.get("columns") or spec.get("subjects") or [])
    scores = spec.get("scores") or spec.get("rankings") or []
    score_map: dict[str, float] = {}
    for item in scores:
        if isinstance(item, dict):
            score_map[str(item.get("subject") or item.get("name") or "")] = float(item.get("score") or item.get("value") or 0)
    if not subjects:
        subjects = list(score_map.keys()) or ["候选 A", "候选 B", "候选 C"]
    if not score_map:
        score_map = {str(s): max(0.3, 1.0 - i * 0.15) for i, s in enumerate(subjects)}

    ranked = sorted(subjects, key=lambda s: score_map.get(str(s), 0), reverse=True)
    pad = 48.0
    row_h = 52.0
    bar_w = 360.0
    w = pad * 2 + bar_w + 120
    h = pad * 2 + row_h * len(ranked) + (32 if title else 0)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}">',
        f'<rect width="100%" height="100%" fill="{tokens.background}"/>',
    ]
    if title:
        parts.append(multiline_text(w / 2, pad - 6, title, fill=tokens.text, max_width=w - 80, font_size=16, max_lines=2))

    y0 = pad + (28 if title else 0)
    for rank, subj in enumerate(ranked, start=1):
        y = y0 + (rank - 1) * row_h
        score = score_map.get(str(subj), 0.5)
        parts.append(multiline_text(pad, y + row_h / 2, f"#{rank}", fill=tokens.primary, max_width=40, font_size=14, max_lines=1))
        parts.append(multiline_text(pad + 36, y + row_h / 2, str(subj), fill=tokens.text, max_width=100, font_size=13, max_lines=1))
        bx = pad + 130
        parts.append(rect(bx, y + 14, bar_w, 24, fill=tokens.card, stroke=tokens.border, rx=4))
        parts.append(rect(bx, y + 14, bar_w * min(1.0, score), 24, fill=tokens.primary, stroke="none", rx=4))
        parts.append(multiline_text(bx + bar_w + 12, y + row_h / 2, f"{score:.0%}" if score <= 1 else f"{score:.1f}", fill=tokens.muted, max_width=60, font_size=12, max_lines=1))

    parts.append("</svg>")
    return parts
