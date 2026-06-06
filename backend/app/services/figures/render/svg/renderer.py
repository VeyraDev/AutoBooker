"""LayoutResult + DesignTokens → SVG 主路径。"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.services.figures.design.icons import icon_for_kind
from app.services.figures.design.tokens import DesignTokens, tokens_for_theme
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
) -> tuple[str, Path]:
    tokens = tokens_for_theme(theme)
    lr = _coerce_layout(layout_result, spec)
    if lr is None:
        raise ValueError("svg renderer requires layout_result or node positions")

    _adapt_node_sizes(lr, spec)
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
        parts.append(multiline_text(w / 2, 22, title, fill=tokens.text, max_width=w - 80, font_size=16, max_lines=2))

    parts.extend(_render_groups(spec, lr, tokens))
    for edge in lr.edge_routes:
        dashed = edge.style == "dashed"
        parts.append(polyline(edge.points, stroke=tokens.edge_stroke, width=tokens.edge_width, dashed=dashed, marker_end="arrow"))
        if edge.label and len(edge.points) >= 2:
            mid = edge.points[len(edge.points) // 2]
            tw = min(estimate_text_width(edge.label, font_size=11), 90)
            parts.append(label_background(mid[0], mid[1] - 8, tw))
            parts.append(multiline_text(mid[0], mid[1] - 8, edge.label, fill=tokens.text, max_width=90, font_size=11))

    for nid, pos in lr.node_positions.items():
        meta = node_meta.get(nid, {})
        kind = str(meta.get("type") or "process")
        label = str(meta.get("label") or nid)
        fill = _fill_for_kind(kind, tokens, meta)
        cx, cy = pos.x + pos.width / 2, pos.y + pos.height / 2
        parts.append(_render_node(pos, kind, label, fill, tokens, meta))

    parts.append("</svg>")
    svg_content = "\n".join(parts)
    svg_path = out_path.with_suffix(".svg")
    png_path = out_path.with_suffix(".png")
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(svg_content, encoding="utf-8")
    export_png_from_svg(svg_path, png_path)
    return "image/svg+xml", svg_path if svg_path.is_file() else png_path


def _render_node(pos: NodePosition, kind: str, label: str, fill: str, tokens: DesignTokens, meta: dict) -> str:
    cx, cy = pos.x + pos.width / 2, pos.y + pos.height / 2
    parts: list[str] = []
    if kind == "database":
        parts.append(database(cx, cy, pos.width, pos.height, fill=fill, stroke=tokens.border))
    elif kind == "queue":
        parts.append(queue_rail(pos.x, pos.y, pos.width, pos.height, fill=fill, stroke=tokens.border))
    elif kind == "decision" or meta.get("shape") == "diamond":
        parts.append(diamond(cx, cy, pos.width, pos.height, fill=fill, stroke=tokens.border, shadow=True))
    else:
        parts.append(rect(pos.x, pos.y, pos.width, pos.height, fill=fill, stroke=tokens.border, rx=tokens.node_radius, shadow=True))
    icon = icon_for_kind(kind)
    if icon:
        parts.append(icon_badge(pos.x + 14, pos.y + 14, icon, bg=tokens.card, fg=tokens.primary))
    parts.append(multiline_text(cx, cy + (6 if icon else 0), label, fill=tokens.text, max_width=pos.width - 12, font_size=tokens.font_size))
    return "\n".join(parts)


def _render_groups(spec: dict, lr: LayoutResult, tokens: DesignTokens) -> list[str]:
    groups = spec.get("groups") or []
    if not groups:
        layers = spec.get("layers") or []
        groups = [{"label": layer.get("label", ""), "members": []} for layer in layers if isinstance(layer, dict)]
    out: list[str] = []
    node_meta = {n.get("id"): n for n in (spec.get("nodes") or []) if isinstance(n, dict)}
    label_to_id = {str(n.get("label")): n.get("id") for n in node_meta.values() if n.get("label")}
    for grp in groups:
        if not isinstance(grp, dict):
            continue
        members = [str(m) for m in (grp.get("members") or grp.get("nodes") or [])]
        if not members and grp.get("label"):
            for layer in spec.get("layers") or []:
                if isinstance(layer, dict) and layer.get("label") == grp.get("label"):
                    members = [label_to_id.get(str(m), str(m)) for m in (layer.get("modules") or [])]
        positions = [lr.node_positions.get(mid) for mid in members if lr.node_positions.get(mid)]
        if len(positions) < 2:
            continue
        pad = 16
        x0 = min(p.x for p in positions) - pad
        y0 = min(p.y for p in positions) - pad - 12
        x1 = max(p.x + p.width for p in positions) + pad
        y1 = max(p.y + p.height for p in positions) + pad
        out.append(group_container(x0, y0, x1 - x0, y1 - y0, str(grp.get("label") or ""), fill=tokens.card, stroke=tokens.border, text_fill=tokens.muted if hasattr(tokens, "muted") else tokens.text))
    return out


def _adapt_node_sizes(lr: LayoutResult, spec: dict) -> None:
    node_meta = {n.get("id"): n for n in (spec.get("nodes") or []) if isinstance(n, dict)}
    for nid, pos in lr.node_positions.items():
        label = str((node_meta.get(nid) or {}).get("label") or nid)
        w, h = measure_node_size(label)
        cx, cy = pos.x + pos.width / 2, pos.y + pos.height / 2
        pos.width, pos.height = w, h
        pos.x, pos.y = cx - w / 2, cy - h / 2


def _fill_for_kind(kind: str, tokens: DesignTokens, meta: dict) -> str:
    if meta.get("color"):
        return str(meta["color"])
    if kind == "decision":
        return tokens.decision_fill
    if kind == "gateway":
        return tokens.gateway_fill
    if kind in {"database", "queue"}:
        return tokens.card
    return tokens.node_fill


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
                edges.append(EdgeRoute(source=e.get("source", ""), target=e.get("target", ""), points=pts, label=e.get("label", ""), style=e.get("style", "solid")))
        return LayoutResult(
            strategy=str(layout_result.get("strategy") or "layered"),
            direction=str(layout_result.get("direction") or "TB"),
            node_positions=npos,
            edge_routes=edges,
            canvas=dict(layout_result.get("canvas") or {"width": 800, "height": 600}),
        )
    clf_layout = spec.get("layout_result")
    if isinstance(clf_layout, dict):
        return _coerce_layout(clf_layout, spec)
    return None
