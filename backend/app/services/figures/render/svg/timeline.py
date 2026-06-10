"""时间轴专用 SVG 渲染。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.figures.contracts.field_registry import pick_str
from app.services.figures.contracts.visual_directives import visual_directive_ids
from app.services.figures.design.render_context import RenderContext, build_render_context
from app.services.figures.design.spec import DesignSpec
from app.services.figures.render.svg.export_png import export_png_from_svg
from app.services.figures.render.svg.primitives import rect
from app.services.figures.render.svg.text import multiline_text


def render_timeline_svg(
    spec: dict[str, Any],
    out_path: Path,
    *,
    title: str = "",
    design_spec: DesignSpec | dict[str, Any] | None = None,
) -> tuple[str, Path]:
    ctx = build_render_context(design_spec or spec.get("design_spec"))
    tokens = ctx.tokens
    events = list(spec.get("events") or (spec.get("extensions") or {}).get("events") or [])
    events = [e for e in events if isinstance(e, dict)]
    directives = _directive_ids(spec, ctx)
    directive_attr = ",".join(directives)
    n = max(1, len(events))
    fig_w = max(640.0, min(1200.0, n * 140.0 + 120.0))
    fig_h = 320.0
    axis_y = fig_h * 0.55
    pad = 56.0

    parts = [
        f'<svg data-grammar="timeline" data-visual-directives="{directive_attr}" xmlns="http://www.w3.org/2000/svg" width="{fig_w:.0f}" height="{fig_h:.0f}" viewBox="0 0 {fig_w:.0f} {fig_h:.0f}">',
        f'<rect width="100%" height="100%" fill="{tokens.background}"/>',
        f'<g class="timeline-directives {" ".join(directives)}"/>',
    ]
    if title or spec.get("title"):
        parts.append(multiline_text(fig_w / 2, 28, title or str(spec.get("title")), fill=tokens.text, max_width=fig_w - 80, font_size=16, max_lines=2))

    left, right = pad, fig_w - pad
    parts.append(
        f'<line x1="{left:.1f}" y1="{axis_y:.1f}" x2="{right:.1f}" y2="{axis_y:.1f}" '
        f'stroke="{tokens.primary}" stroke-width="2"/>'
    )

    for i, event in enumerate(events):
        x = left if n == 1 else left + (right - left) * i / (n - 1)
        time_val = pick_str(event, "time")
        label = pick_str(event, "label")
        dy = -72.0 if i % 2 == 0 else 72.0
        dot_r = 8.0
        parts.append(f'<circle cx="{x:.1f}" cy="{axis_y:.1f}" r="{dot_r}" fill="{tokens.primary}"/>')
        parts.append(f'<line x1="{x:.1f}" y1="{axis_y:.1f}" x2="{x:.1f}" y2="{axis_y + dy * 0.5:.1f}" stroke="{tokens.border}" stroke-width="1"/>')
        card_y = axis_y + dy - (24 if dy < 0 else 0)
        label_class = "alternating-timeline-labels" if dy < 0 else "alternating-timeline-labels lower-label"
        parts.append(f'<g class="timeline-event {label_class}" data-time="{time_val}">')
        parts.append(rect(x - 56, card_y, 112, 48, fill=tokens.card, stroke=tokens.border, rx=8))
        text_fill = ctx.resolve_text_fill(tokens.card)
        parts.append(multiline_text(x, card_y + 14, time_val, fill=tokens.primary, max_width=100, font_size=11, max_lines=1))
        parts.append(multiline_text(x, card_y + 32, label, fill=text_fill, max_width=100, font_size=11, max_lines=2))
        parts.append("</g>")

    parts.append("</svg>")
    svg_content = "\n".join(parts)
    svg_path = out_path.with_suffix(".svg")
    png_path = out_path.with_suffix(".png")
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(svg_content, encoding="utf-8")
    export_png_from_svg(svg_path, png_path)
    return "image/svg+xml", svg_path if svg_path.is_file() else png_path


def _directive_ids(spec: dict[str, Any], ctx: RenderContext) -> list[str]:
    direct = [str(x) for x in (spec.get("directive_ids") or []) if str(x)]
    if direct:
        return direct
    if spec.get("visual_directives"):
        return visual_directive_ids(spec.get("visual_directives") or [])
    return [str(x) for x in (ctx.extras.get("directive_ids") or []) if str(x)]
