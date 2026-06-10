"""LayoutResult + Design Spec → SVG 主路径。"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from app.services.figures.design.icons import icon_for_kind
from app.services.figures.design.render_context import RenderContext, build_render_context
from app.services.figures.design.spec import DesignSpec
from app.services.figures.design.themes.academic_clean import ACADEMIC_CLEAN
from app.services.figures.design.themes.modern_saas import MODERN_SAAS
from app.services.figures.design.typography import estimate_text_width, measure_node_size
from app.services.figures.layout.schema import EdgeRoute, LayoutResult, NodePosition
from app.services.figures.render.svg.export_png import export_png_from_svg
from app.services.figures.render.svg.markers import arrow_marker_def
from app.services.figures.render.svg.primitives import (
    database,
    diamond,
    group_container,
    icon_badge,
    label_background,
    polyline,
    queue_rail,
    rect,
    shadow_filter_def,
)
from app.services.figures.render.svg.text import multiline_text


def render_svg_diagram(
    spec: dict[str, Any],
    out_path: Path,
    *,
    title: str = "",
    layout_result: LayoutResult | dict | None = None,
    theme: str = "modern_saas",
    design_spec: DesignSpec | dict[str, Any] | None = None,
) -> tuple[str, Path]:
    ds = design_spec or spec.get("design_spec") or {"theme": theme}
    ctx = build_render_context(ds)
    tokens = ctx.tokens
    palette = MODERN_SAAS if ctx.theme != "academic_clean" else ACADEMIC_CLEAN

    if ctx.comparison_template and _is_comparison_spec(spec):
        from app.services.figures.render.svg.comparison import render_comparison_svg

        return render_comparison_svg(spec, out_path, title=title or str(spec.get("title") or ""), design_spec=ds)

    lr = _coerce_layout(layout_result, spec)
    if lr is None:
        raise ValueError("svg renderer requires layout_result or node positions")

    _adapt_node_sizes(lr, spec, ctx)
    from app.services.figures.layout.canvas import expand_canvas_for_routes

    expand_canvas_for_routes(lr)
    w = lr.canvas.get("width", 800)
    h = lr.canvas.get("height", 600)
    node_meta = {n.get("id"): n for n in (spec.get("nodes") or []) if isinstance(n, dict)}

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" viewBox="0 0 {w:.0f} {h:.0f}">',
        f'<rect width="100%" height="100%" fill="{tokens.background}"/>',
        "<defs>",
        shadow_filter_def(),
        arrow_marker_def("arrow", color=tokens.edge_stroke, size=tokens.arrow_size),
        "</defs>",
    ]
    if title:
        parts.append(multiline_text(w / 2, 22, title, fill=tokens.text, max_width=w - 80, font_size=ctx.variant.title_font_size, max_lines=2))

    parts.extend(_render_swimlane_lanes(spec, lr, ctx))
    parts.extend(_render_groups(spec, lr, ctx, palette))
    for edge in lr.edge_routes:
        parts.append(_render_edge(edge, ctx))
        if edge.label:
            lx = float((edge.meta or {}).get("label_x") or 0)
            ly = float((edge.meta or {}).get("label_y") or 0)
            if not lx and len(edge.points) >= 2:
                mid = edge.points[len(edge.points) // 2]
                lx, ly = mid[0], mid[1] - 8
            tw = min(estimate_text_width(edge.label, font_size=11), 90)
            parts.append(label_background(lx, ly, tw))
            parts.append(multiline_text(lx, ly, edge.label, fill=tokens.text, max_width=90, font_size=11))

    for nid, pos in lr.node_positions.items():
        meta = node_meta.get(nid, {})
        kind = str(meta.get("type") or meta.get("kind") or "process")
        label = str(meta.get("label") or nid)
        fill = ctx.resolve_node_fill(kind, meta, palette)
        parts.append(_render_node(pos, kind, label, fill, ctx, meta))

    if ctx.annotation_style == "notation" and spec.get("structure_summary"):
        parts.append(multiline_text(max(48, w - 220), h - 24, str(spec["structure_summary"])[:80], fill=tokens.muted, max_width=min(200, w * 0.4), font_size=10, max_lines=2))

    parts.append("</svg>")
    svg_content = "\n".join(parts)
    svg_path = out_path.with_suffix(".svg")
    png_path = out_path.with_suffix(".png")
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(svg_content, encoding="utf-8")
    export_png_from_svg(svg_path, png_path)
    return "image/svg+xml", svg_path if svg_path.is_file() else png_path


def _is_comparison_spec(spec: dict[str, Any]) -> bool:
    if spec.get("columns") or spec.get("dimensions") or spec.get("subjects"):
        return True
    st = str(spec.get("diagram_subtype") or "")
    return "comparison" in st or st in {"comparison_matrix", "swot"}


def _render_edge(edge: EdgeRoute, ctx: RenderContext) -> str:
    dashed = edge.style == "dashed" or (ctx.arrow.dashed_optional and edge.style == "optional")
    width = ctx.edge_width()
    color = ctx.tokens.edge_stroke
    if ctx.arrow.routing == "curved" and len(edge.points) >= 2:
        return _curved_edge(edge.points[0], edge.points[-1], stroke=color, width=width, dashed=dashed)
    if ctx.arrow.routing == "dataflow" and len(edge.points) >= 2:
        pts = _dataflow_points(edge.points[0], edge.points[-1])
        return polyline(pts, stroke=color, width=width, dashed=dashed, marker_end="arrow")
    return polyline(edge.points, stroke=color, width=width, dashed=dashed, marker_end="arrow")


def _curved_edge(p0: tuple[float, float], p1: tuple[float, float], *, stroke: str, width: float, dashed: bool) -> str:
    x1, y1 = p0
    x2, y2 = p1
    cx, cy = (x1 + x2) / 2, (y1 + y2) / 2 - abs(x2 - x1) * 0.15
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    return (
        f'<path d="M {x1:.1f} {y1:.1f} Q {cx:.1f} {cy:.1f} {x2:.1f} {y2:.1f}" '
        f'fill="none" stroke="{stroke}" stroke-width="{width:.1f}"{dash} marker-end="url(#arrow)"/>'
    )


def _dataflow_points(p0: tuple[float, float], p1: tuple[float, float]) -> list[tuple[float, float]]:
    x1, y1 = p0
    x2, y2 = p1
    mid_x = (x1 + x2) / 2
    return [(x1, y1), (mid_x, y1), (mid_x, y2), (x2, y2)]


def _render_node(pos: NodePosition, kind: str, label: str, fill: str, ctx: RenderContext, meta: dict) -> str:
    cx, cy = pos.x + pos.width / 2, pos.y + pos.height / 2
    parts: list[str] = []
    rx = ctx.container.rx if ctx.container.pipeline_stage else ctx.node_radius()
    shadow = ctx.variant.node_shadow

    if ctx.container.pipeline_stage:
        parts.append(rect(pos.x, pos.y, pos.width, 10, fill=ctx.tokens.primary, stroke="none", rx=rx))
        parts.append(rect(pos.x, pos.y + 8, pos.width, pos.height - 8, fill=fill, stroke=ctx.tokens.border, rx=rx, shadow=shadow))
    elif kind == "database":
        parts.append(database(cx, cy, pos.width, pos.height, fill=fill, stroke=ctx.tokens.border))
    elif kind == "queue":
        parts.append(queue_rail(pos.x, pos.y, pos.width, pos.height, fill=fill, stroke=ctx.tokens.border))
    elif kind == "decision" or meta.get("shape") == "diamond":
        parts.append(diamond(cx, cy, pos.width, pos.height, fill=fill, stroke=ctx.tokens.border, shadow=shadow))
    else:
        parts.append(rect(pos.x, pos.y, pos.width, pos.height, fill=fill, stroke=ctx.tokens.border, rx=rx, shadow=shadow))

    if ctx.variant.show_icons:
        icon = icon_for_kind(kind)
        if icon:
            parts.append(icon_badge(pos.x + 14, pos.y + 14, icon, bg=ctx.tokens.card, fg=ctx.tokens.primary))
    text_fill = ctx.resolve_text_fill(fill)
    max_lines = int((ctx.extras.get("max_label_lines") or 4))
    parts.append(
        multiline_text(
            cx,
            cy + (6 if ctx.variant.show_icons else 0),
            label,
            fill=text_fill,
            max_width=pos.width - 12,
            font_size=ctx.variant.label_font_size,
            max_lines=max_lines,
        )
    )
    return "\n".join(parts)


def _render_groups(spec: dict, lr: LayoutResult, ctx: RenderContext, palette: dict) -> list[str]:
    groups = spec.get("groups") or []
    if not groups:
        layers = spec.get("layers") or []
        groups = [{"label": layer.get("label", ""), "members": []} for layer in layers if isinstance(layer, dict)]
    out: list[str] = []
    node_meta = {n.get("id"): n for n in (spec.get("nodes") or []) if isinstance(n, dict)}
    label_to_id = {str(n.get("label")): n.get("id") for n in node_meta.values() if n.get("label")}
    stroke = ctx.tokens.border
    if ctx.container.stroke_dashed:
        stroke = ctx.tokens.muted
    for grp in groups:
        if not isinstance(grp, dict):
            continue
        members = [str(m) for m in (grp.get("members") or grp.get("nodes") or [])]
        if not members and grp.get("label"):
            for layer in spec.get("layers") or []:
                if isinstance(layer, dict) and layer.get("label") == grp.get("label"):
                    members = [label_to_id.get(str(m), str(m)) for m in (layer.get("modules") or [])]
        positions = [lr.node_positions.get(mid) for mid in members if lr.node_positions.get(mid)]
        if len(positions) < 2 and not ctx.container.header_band:
            continue
        pad = 16
        if positions:
            x0 = min(p.x for p in positions) - pad
            y0 = min(p.y for p in positions) - pad - 12
            x1 = max(p.x + p.width for p in positions) + pad
            y1 = max(p.y + p.height for p in positions) + pad
        else:
            x0, y0, x1, y1 = pad, pad, 400, 200
        out.append(group_container(x0, y0, x1 - x0, y1 - y0, str(grp.get("label") or ""), fill=ctx.tokens.card, stroke=stroke, text_fill=ctx.tokens.muted))
    return out


def _render_swimlane_lanes(spec: dict, lr: LayoutResult, ctx: RenderContext) -> list[str]:
    if ctx.component_variant != "swimlane" and "swimlane" not in (lr.meta or {}).get("solver_hints", []):
        lanes = spec.get("lanes") or (lr.meta or {}).get("lanes")
        if not lanes:
            return []
    lanes = spec.get("lanes") or (lr.meta or {}).get("lanes") or []
    if not lanes:
        return []
    out: list[str] = []
    h = float(lr.canvas.get("height") or 600)
    lane_count = max(1, len(lanes))
    lane_h = h / lane_count
    for i, lane in enumerate(lanes):
        if not isinstance(lane, dict):
            continue
        y = i * lane_h
        out.append(rect(0, y, 120, lane_h - 4, fill=ctx.tokens.card, stroke=ctx.tokens.border, rx=0))
        out.append(multiline_text(60, y + lane_h / 2, str(lane.get("label") or lane.get("id") or ""), fill=ctx.tokens.text, max_width=110, font_size=12, max_lines=2))
        if i > 0:
            out.append(f'<line x1="0" y1="{y:.1f}" x2="{lr.canvas.get("width", 800):.1f}" y2="{y:.1f}" stroke="{ctx.tokens.border}" stroke-dasharray="4 4"/>')
    return out


def _adapt_node_sizes(lr: LayoutResult, spec: dict, ctx: RenderContext) -> None:
    node_meta = {n.get("id"): n for n in (spec.get("nodes") or []) if isinstance(n, dict)}
    for nid, pos in lr.node_positions.items():
        label = str((node_meta.get(nid) or {}).get("label") or nid)
        w, h = measure_node_size(label)
        w = max(w, 80) * ctx.variant.density_pad
        cx, cy = pos.x + pos.width / 2, pos.y + pos.height / 2
        pos.width, pos.height = w, h
        pos.x, pos.y = cx - w / 2, cy - h / 2


def _coerce_layout(layout_result: LayoutResult | dict | None, spec: dict) -> LayoutResult | None:
    if isinstance(layout_result, LayoutResult):
        return layout_result
    if isinstance(layout_result, dict) and layout_result.get("node_positions"):
        npos = {}
        for nid, p in layout_result.get("node_positions", {}).items():
            if isinstance(p, dict):
                npos[nid] = NodePosition(id=nid, x=float(p["x"]), y=float(p["y"]), width=float(p.get("width", 120)), height=float(p.get("height", 48)))
        edges = []
        for e in layout_result.get("edge_routes") or []:
            if isinstance(e, dict):
                pts = [(float(x), float(y)) for x, y in e.get("points", [])]
                edges.append(EdgeRoute(
                    source=e.get("source", ""),
                    target=e.get("target", ""),
                    points=pts,
                    label=e.get("label", ""),
                    style=e.get("style", "solid"),
                    meta=dict(e.get("meta") or {}),
                ))
        return LayoutResult(
            strategy=str(layout_result.get("strategy") or "layered"),
            direction=str(layout_result.get("direction") or "TB"),
            node_positions=npos,
            edge_routes=edges,
            canvas=dict(layout_result.get("canvas") or {"width": 800, "height": 600}),
            meta=dict(layout_result.get("meta") or {}),
        )
    clf_layout = spec.get("layout_result")
    if isinstance(clf_layout, dict):
        return _coerce_layout(clf_layout, spec)
    return None
