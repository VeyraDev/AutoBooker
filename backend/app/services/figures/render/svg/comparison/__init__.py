"""Comparison 四模板分派。"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from app.services.figures.contracts.visual_directives import visual_directive_ids
from app.services.figures.design.render_context import RenderContext, build_render_context
from app.services.figures.render.svg.comparison.bars import render_comparison_bars
from app.services.figures.render.svg.comparison.cards import render_comparison_cards
from app.services.figures.render.svg.comparison.matrix import render_comparison_matrix
from app.services.figures.render.svg.comparison.pros_cons import render_comparison_pros_cons
from app.services.figures.render.svg.comparison.scoreboard import render_comparison_scoreboard
from app.services.figures.render.svg.export_png import export_png_from_svg
from app.services.figures.render.svg.primitives import rect
from app.services.figures.render.svg.text import multiline_text


def render_comparison_svg(
    spec: dict[str, Any],
    out_path: Path,
    *,
    title: str = "",
    design_spec: dict[str, Any] | None = None,
) -> tuple[str, Path]:
    ctx = build_render_context(design_spec or spec.get("design_spec"))
    grammar = str(spec.get("matrix_visual_grammar") or "")
    if grammar == "swot":
        parts = _render_swot_quadrants(spec, ctx, title=title or str(spec.get("title") or ""))
    elif grammar == "attention_heatmap":
        parts = _render_attention_heatmap(spec, ctx, title=title or str(spec.get("title") or ""))
    else:
        parts = _render_standard_comparison(spec, ctx, title=title or str(spec.get("title") or ""))
    svg_content = "\n".join(parts)
    svg_path = out_path.with_suffix(".svg")
    png_path = out_path.with_suffix(".png")
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(svg_content, encoding="utf-8")
    export_png_from_svg(svg_path, png_path)
    return "image/svg+xml", svg_path if svg_path.is_file() else png_path


def _render_standard_comparison(spec: dict[str, Any], ctx: RenderContext, *, title: str = "") -> list[str]:
    template = ctx.comparison_template or "matrix"
    renderers = {
        "matrix": render_comparison_matrix,
        "cards": render_comparison_cards,
        "pros_cons": render_comparison_pros_cons,
        "scoreboard": render_comparison_scoreboard,
        "bar_horizontal": render_comparison_bars,
        "radar": render_comparison_scoreboard,
    }
    fn = renderers.get(template, render_comparison_matrix)
    parts = fn(spec, ctx, title=title)
    if parts:
        directives = _directive_ids(spec, ctx)
        escaped_directives = html.escape(",".join(directives))
        semantics = html.escape(",".join(str(x) for x in (spec.get("mandatory_semantics") or [])))
        parts[0] = parts[0].replace(
            "<svg ",
            f'<svg data-grammar="comparison_matrix" data-visual-directives="{escaped_directives}" data-mandatory-semantics="{semantics}" ',
            1,
        )
    return parts


def _directive_ids(spec: dict[str, Any], ctx: RenderContext) -> list[str]:
    direct = [str(x) for x in (spec.get("directive_ids") or []) if str(x)]
    if direct:
        return direct
    if spec.get("visual_directives"):
        return visual_directive_ids(spec.get("visual_directives") or [])
    return [str(x) for x in (ctx.extras.get("directive_ids") or []) if str(x)]


def _render_swot_quadrants(spec: dict[str, Any], ctx: RenderContext, *, title: str = "") -> list[str]:
    tokens = ctx.tokens
    native = spec.get("native_passthrough") if isinstance(spec.get("native_passthrough"), dict) else {}
    cells = [c for c in (spec.get("cells") or []) if isinstance(c, dict)]
    cell_by_subject = {str(c.get("subject") or c.get("column") or "").lower(): str(c.get("value") or c.get("text") or "") for c in cells}
    quadrants = [
        ("strengths", "Strengths", "#DCFCE7"),
        ("weaknesses", "Weaknesses", "#FEE2E2"),
        ("opportunities", "Opportunities", "#DBEAFE"),
        ("threats", "Threats", "#FEF3C7"),
    ]
    pad = 52.0
    gap = 18.0
    q_w = 300.0
    q_h = 214.0
    width = pad * 2 + q_w * 2 + gap
    height = pad * 2 + q_h * 2 + gap + (34 if title else 0)
    y0 = pad + (34 if title else 0)
    semantics = html.escape(",".join(str(x) for x in (spec.get("mandatory_semantics") or [])))
    parts = [
        f'<svg data-grammar="swot" data-mandatory-semantics="{semantics}" xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">',
        f'<rect width="100%" height="100%" fill="{tokens.background}"/>',
        f'<g class="mandatory-semantics" data-items="{semantics}"/>',
    ]
    if title:
        parts.append(multiline_text(width / 2, pad - 8, title, fill=tokens.text, max_width=width - 96, font_size=16, max_lines=2))
    for i, (key, label, fill) in enumerate(quadrants):
        x = pad + (i % 2) * (q_w + gap)
        y = y0 + (i // 2) * (q_h + gap)
        items = _swot_items(native, key, cell_by_subject)
        parts.append(f'<g class="swot-quadrant {html.escape(key)}" data-quadrant="{html.escape(key)}">')
        parts.append(rect(x, y, q_w, q_h, fill=fill, stroke=tokens.border, rx=10))
        parts.append(multiline_text(x + q_w / 2, y + 26, label, fill=tokens.text, max_width=q_w - 28, font_size=14, max_lines=1))
        bullet_y = y + 62
        for item in items[:5]:
            parts.append(multiline_text(x + 24, bullet_y, f"- {item}", fill=tokens.text, max_width=q_w - 44, font_size=12, max_lines=2))
            bullet_y += 30
        parts.append("</g>")
    parts.append('<g class="four-quadrants strengths weaknesses opportunities threats"/>')
    parts.append("</svg>")
    return parts


def _swot_items(native: dict[str, Any], key: str, cell_by_subject: dict[str, str]) -> list[str]:
    raw = native.get(key)
    if isinstance(raw, str):
        items = _split_items(raw)
    else:
        items = [str(x).strip() for x in (raw or []) if str(x).strip()]
    if items:
        return items
    aliases = {
        "strengths": ("strengths", "strength", "s"),
        "weaknesses": ("weaknesses", "weakness", "w"),
        "opportunities": ("opportunities", "opportunity", "o"),
        "threats": ("threats", "threat", "t"),
    }
    for alias in aliases.get(key, (key,)):
        value = cell_by_subject.get(alias)
        if value:
            return _split_items(value)
    return [key.replace("_", " ").title()]


def _split_items(value: str) -> list[str]:
    text = str(value or "")
    for sep in (";", "|", "/", "\n"):
        text = text.replace(sep, "\n")
    return [part.strip(" -\t") for part in text.splitlines() if part.strip(" -\t")]


def _render_attention_heatmap(spec: dict[str, Any], ctx: RenderContext, *, title: str = "") -> list[str]:
    tokens = ctx.tokens
    subjects = [str(x) for x in (spec.get("subjects") or spec.get("columns") or []) if str(x).strip()]
    dimensions = [str(x) for x in (spec.get("dimensions") or []) if str(x).strip()]
    if not subjects:
        subjects = [f"T{i + 1}" for i in range(6)]
    if not dimensions:
        dimensions = list(subjects)
    subjects = subjects[:16]
    dimensions = dimensions[:16]
    cell = 38.0 if max(len(subjects), len(dimensions)) > 10 else 46.0
    label_w = 120.0
    top_h = 94.0 + (28 if title else 0)
    pad = 46.0
    width = pad * 2 + label_w + cell * len(subjects) + 88
    height = pad + top_h + cell * len(dimensions) + 34
    semantics = html.escape(",".join(str(x) for x in (spec.get("mandatory_semantics") or [])))
    weights = _attention_weights(spec.get("cells") or [])
    parts = [
        f'<svg data-grammar="attention_heatmap" data-mandatory-semantics="{semantics}" xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">',
        f'<rect width="100%" height="100%" fill="{tokens.background}"/>',
        f'<g class="mandatory-semantics" data-items="{semantics}"/>',
    ]
    if title:
        parts.append(multiline_text(width / 2, pad - 8, title, fill=tokens.text, max_width=width - 96, font_size=16, max_lines=2))
    ox = pad + label_w
    oy = pad + top_h
    for j, label in enumerate(subjects):
        x = ox + j * cell + cell / 2
        parts.append(multiline_text(x, oy - 22, label, fill=tokens.text, max_width=cell * 1.8, font_size=10, max_lines=2))
    for i, label in enumerate(dimensions):
        y = oy + i * cell + cell / 2
        parts.append(multiline_text(pad + label_w - 10, y, label, fill=tokens.text, max_width=label_w - 18, font_size=10, max_lines=2))
        for j, subj in enumerate(subjects):
            val = weights.get((label, subj), 0.0)
            fill = _heat_color(val)
            cls = "heat-cell diagonal-emphasis" if i == j else "heat-cell"
            parts.append(
                f'<rect class="{cls}" data-row="{html.escape(label)}" data-column="{html.escape(subj)}" data-weight="{val:.3f}" '
                f'x="{ox + j * cell:.1f}" y="{oy + i * cell:.1f}" width="{cell - 3:.1f}" height="{cell - 3:.1f}" '
                f'rx="5" fill="{fill}" stroke="{tokens.border}" stroke-width="{1.6 if i == j else 0.8}"/>'
            )
    legend_x = ox + cell * len(subjects) + 28
    parts.append('<g class="heat-scale">')
    for k, val in enumerate((0.0, 0.25, 0.5, 0.75, 1.0)):
        y = oy + k * 28
        parts.append(rect(legend_x, y, 24, 20, fill=_heat_color(val), stroke=tokens.border, rx=4))
        parts.append(multiline_text(legend_x + 54, y + 10, f"{val:.2f}", fill=tokens.text, max_width=46, font_size=10, max_lines=1))
    parts.append("</g>")
    parts.append('<g class="row-tokens column-tokens cell-weights"/>')
    parts.append("</svg>")
    return parts


def _attention_weights(cells: list[Any]) -> dict[tuple[str, str], float]:
    out: dict[tuple[str, str], float] = {}
    for cell in cells:
        if not isinstance(cell, dict):
            continue
        row = str(cell.get("row") or cell.get("dimension") or "")
        col = str(cell.get("column") or cell.get("subject") or "")
        if not row or not col:
            continue
        try:
            value = float(cell.get("value") or 0.0)
        except (TypeError, ValueError):
            value = 0.0
        out[(row, col)] = max(0.0, min(1.0, value))
    return out


def _heat_color(value: float) -> str:
    stops = [
        (239, 246, 255),
        (191, 219, 254),
        (96, 165, 250),
        (37, 99, 235),
        (30, 64, 175),
    ]
    idx = max(0, min(3, int(value * 4)))
    frac = max(0.0, min(1.0, value * 4 - idx))
    a = stops[idx]
    b = stops[idx + 1]
    rgb = tuple(round(a[i] + (b[i] - a[i]) * frac) for i in range(3))
    return f"#{rgb[0]:02X}{rgb[1]:02X}{rgb[2]:02X}"
