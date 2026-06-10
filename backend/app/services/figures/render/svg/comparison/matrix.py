"""Comparison matrix 模板 SVG。"""

from __future__ import annotations

import html
from typing import Any

from app.services.figures.contracts.visual_directives import visual_directive_ids
from app.services.figures.design.render_context import RenderContext
from app.services.figures.render.svg.text import multiline_text

_SUBJECT_COLORS = [
    ("#2563EB", "#DBEAFE"),
    ("#0F766E", "#CCFBF1"),
    ("#7C3AED", "#EDE9FE"),
    ("#B45309", "#FEF3C7"),
    ("#BE123C", "#FFE4E6"),
    ("#334155", "#F1F5F9"),
]


def render_comparison_matrix(
    spec: dict[str, Any],
    ctx: RenderContext,
    *,
    title: str = "",
) -> list[str]:
    tokens = ctx.tokens
    subjects = list(spec.get("columns") or spec.get("subjects") or [])
    dimensions = list(spec.get("dimensions") or [])
    cells = spec.get("cells") or []
    directives = set(_directive_ids(spec, ctx))
    color_encoding = bool({"encoding.color_scale", "comparison.axis"} & directives)

    if not subjects:
        subjects = [str(n.get("label") or n.get("id")) for n in (spec.get("nodes") or [])[:4] if isinstance(n, dict)]
    subjects = [str(s.get("name") if isinstance(s, dict) else s) for s in subjects]
    if not dimensions:
        dimensions = ["维度1", "维度2", "维度3"]
    dimensions = [str(d.get("name") if isinstance(d, dict) else d) for d in dimensions]

    col_w = 140.0
    row_h = 44.0
    header_h = 48.0
    label_w = 120.0
    pad = 48.0
    w = pad * 2 + label_w + col_w * max(1, len(subjects))
    h = pad * 2 + header_h + row_h * max(1, len(dimensions)) + (32 if title else 0)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}">',
        f'<rect width="100%" height="100%" fill="{tokens.background}"/>',
        f'<g class="comparison-directives {" ".join(html.escape(d) for d in sorted(directives))}"/>',
    ]
    if title:
        parts.append(multiline_text(w / 2, pad - 8, title, fill=tokens.text, max_width=w - 80, font_size=16, max_lines=2))

    ox, oy = pad + label_w, pad + (32 if title else 0)
    for j, subj in enumerate(subjects):
        cx = ox + j * col_w + col_w / 2
        header_fill = _SUBJECT_COLORS[j % len(_SUBJECT_COLORS)][0] if color_encoding else tokens.primary
        parts.append(
            _class_rect(
                ox + j * col_w,
                oy,
                col_w - 4,
                header_h,
                fill=header_fill,
                stroke=tokens.border,
                rx=6,
                cls="subject-header comparison-axis-cell distinct-color-block" if color_encoding else "subject-header",
                attrs=f'data-subject="{html.escape(str(subj))}"',
            )
        )
        parts.append(multiline_text(cx, oy + header_h / 2, str(subj), fill="#FFFFFF", max_width=col_w - 12, font_size=12, max_lines=2))

    cell_map: dict[tuple[str, str], str] = {}
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        subj = str(cell.get("subject") or cell.get("column") or "")
        dim = str(cell.get("dimension") or cell.get("row") or "")
        val = str(cell.get("value") or cell.get("text") or "—")
        if subj and dim:
            cell_map[(str(dim), str(subj))] = val

    for i, dim in enumerate(dimensions):
        y = oy + header_h + i * row_h
        parts.append(
            _class_rect(
                pad,
                y,
                label_w - 8,
                row_h - 4,
                fill=tokens.card,
                stroke=tokens.border,
                rx=4,
                cls="dimension-label comparison-axis-cell",
                attrs=f'data-dimension="{html.escape(str(dim))}"',
            )
        )
        parts.append(multiline_text(pad + label_w / 2 - 4, y + row_h / 2 - 2, str(dim), fill=tokens.text, max_width=label_w - 16, font_size=11, max_lines=2))
        for j, subj in enumerate(subjects):
            val = cell_map.get((str(dim), str(subj)), "—")
            cx = ox + j * col_w + col_w / 2
            fill, cls = _cell_fill(val, j, tokens.card, color_encoding=color_encoding)
            parts.append(
                _class_rect(
                    ox + j * col_w,
                    y,
                    col_w - 4,
                    row_h - 4,
                    fill=fill,
                    stroke=tokens.border,
                    rx=4,
                    cls=f"comparison-value-cell comparison-axis-cell {cls}",
                    attrs=f'data-subject="{html.escape(str(subj))}" data-dimension="{html.escape(str(dim))}"',
                )
            )
            parts.append(multiline_text(cx, y + row_h / 2 - 2, val, fill=tokens.text, max_width=col_w - 12, font_size=11, max_lines=2))

    parts.append("</svg>")
    return parts


def _directive_ids(spec: dict[str, Any], ctx: RenderContext) -> list[str]:
    direct = [str(x) for x in (spec.get("directive_ids") or []) if str(x)]
    if direct:
        return direct
    if spec.get("visual_directives"):
        return visual_directive_ids(spec.get("visual_directives") or [])
    return [str(x) for x in (ctx.extras.get("directive_ids") or []) if str(x)]


def _class_rect(
    x: float,
    y: float,
    w: float,
    h: float,
    *,
    fill: str,
    stroke: str,
    rx: int,
    cls: str,
    attrs: str = "",
) -> str:
    attr = f" {attrs}" if attrs else ""
    return (
        f'<rect class="{html.escape(cls)}"{attr} x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" '
        f'height="{h:.1f}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'
    )


def _cell_fill(val: str, subject_index: int, default_fill: str, *, color_encoding: bool) -> tuple[str, str]:
    if any(k in val for k in ("高", "快", "优", "好", "强")):
        return "#BBF7D0" if color_encoding else "#DCFCE7", "advantage-color-ramp positive-cell"
    if any(k in val for k in ("低", "慢", "差", "弱", "劣")):
        return "#FECACA" if color_encoding else "#FEE2E2", "advantage-color-ramp negative-cell"
    if color_encoding:
        return _SUBJECT_COLORS[subject_index % len(_SUBJECT_COLORS)][1], "distinct-color-block neutral-cell"
    return default_fill, "neutral-cell"
