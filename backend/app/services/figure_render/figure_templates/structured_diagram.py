"""通用结构化示意图：nodes/edges/level 自适应绘制，适配书稿内页。"""

from __future__ import annotations

import logging
import html
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "Noto Sans CJK SC", "DejaVu Sans", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon

from app.services.figure_render.figure_structure import has_structured_graph
from app.services.figures.render.layout_utils import clamp_font_size, estimate_node_size, visual_width, wrap_text

logger = logging.getLogger(__name__)

_PALETTE = [
    {"fill": "#EFF6FF", "edge": "#2563EB", "tag_fill": "#DBEAFE", "tag_edge": "#3B82F6", "badge": "#1D4ED8"},
    {"fill": "#ECFEFF", "edge": "#0891B2", "tag_fill": "#CFFAFE", "tag_edge": "#06B6D4", "badge": "#0E7490"},
    {"fill": "#F8FAFC", "edge": "#64748B", "tag_fill": "#E2E8F0", "tag_edge": "#64748B", "badge": "#475569"},
    {"fill": "#FFF7ED", "edge": "#D97706", "tag_fill": "#FED7AA", "tag_edge": "#F59E0B", "badge": "#B45309"},
]

_CANVAS = {
    "min_w": 8.5,
    "max_w": 16.0,
    "min_h": 5.4,
    "max_h": 18.0,
    "margin_x": 1.1,
    "margin_top": 1.3,
    "margin_bottom": 0.9,
    "level_gap": 1.1,
    "col_gap": 0.95,
}

_FLOW_SUBTYPES = {"process_flow", "business_workflow", "timeline_roadmap", "timeline", "roadmap"}
_TIMELINE_SUBTYPES = {"timeline_roadmap", "timeline", "roadmap"}
_DECISION_SUBTYPES = {"decision_tree", "decision_flow"}


def _short_title(raw: str, *, fallback: str = "示意图") -> str:
    text = re.sub(r"\s+", " ", str(raw or "").strip())
    text = re.sub(r"^图\s*\d+\s*[-–—]\s*\d+\s*[:：]\s*", "", text).strip(" ：:，,。")
    if not text:
        return fallback
    first = re.split(r"[，,。；;：:\n]", text, 1)[0].strip(" ：:，,。")
    if first and visual_width(first) <= 26:
        return first
    out = ""
    for ch in (first or text):
        if visual_width(out + ch) > 26:
            break
        out += ch
    return out.strip(" ：:，,。") or fallback


def _clean_label(raw: str) -> str:
    text = re.sub(r"\s+", " ", str(raw or "").strip()).strip(" ：:，,。")
    if not text:
        return ""
    if visual_width(text) <= 44:
        return text
    out = ""
    for ch in text:
        if visual_width(out + ch) > 44:
            break
        out += ch
    return out.strip(" ：:，,。") + "…"


def _has_branching_topology(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> bool:
    if not edges:
        return False
    out_deg: dict[str, int] = {}
    in_deg: dict[str, int] = {}
    for e in edges:
        out_deg[e["from"]] = out_deg.get(e["from"], 0) + 1
        in_deg[e["to"]] = in_deg.get(e["to"], 0) + 1
    if any(c > 1 for c in out_deg.values()) or any(c > 1 for c in in_deg.values()):
        return True
    levels = {n["id"]: int(n.get("level") or 0) for n in nodes}
    for e in edges:
        if levels.get(e["to"], 0) < levels.get(e["from"], 0):
            return True
    by_level: dict[int, int] = {}
    for n in nodes:
        lv = int(n.get("level") or 0)
        by_level[lv] = by_level.get(lv, 0) + 1
    return any(c > 1 for c in by_level.values())


def _normalize_shape(shape: str, subtype: str = "") -> str:
    s = (shape or "box").strip().lower()
    if s in {"rect", "rectangle"}:
        return "box"
    if s in {"round", "rounded_box"}:
        return "rounded"
    if s not in {"diamond", "box", "rounded", "tag"}:
        return "box"
    return s


def _normalize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    nodes_in = spec.get("nodes") or []
    edges_in = spec.get("edges") or []
    subtype = str(spec.get("diagram_subtype") or spec.get("subtype") or "").strip().lower()
    nodes: list[dict[str, Any]] = []
    id_map: dict[str, str] = {}
    warnings: list[str] = []
    quality_flags: list[str] = []

    for i, raw in enumerate(nodes_in):
        if not isinstance(raw, dict):
            continue
        nid = str(raw.get("id") or f"n{i}").strip()
        label = _clean_label(str(raw.get("label") or ""))
        if not nid or not label:
            continue
        shape = _normalize_shape(str(raw.get("shape") or "rounded"))
        try:
            level = int(raw.get("level", 0))
        except (TypeError, ValueError):
            level = 0
        column = raw.get("column")
        parent = str(raw.get("parent") or "").strip() or None
        wrapped, width, height = estimate_node_size(
            label,
            shape=shape,
            max_units=12 if shape == "tag" else 15,
            max_lines=3 if shape == "tag" else 4,
        )
        nodes.append({
            "id": nid,
            "label": label,
            "wrapped_label": wrapped,
            "shape": shape,
            "icon": str(raw.get("icon") or "").strip(),
            "level": max(0, level),
            "column": int(column) if column is not None else None,
            "parent": parent,
            "w": width,
            "h": height,
        })
        id_map[nid] = nid

    edges: list[dict[str, str]] = []
    for e in edges_in:
        if not isinstance(e, dict):
            continue
        src = str(e.get("from") or e.get("source") or "").strip()
        dst = str(e.get("to") or e.get("target") or "").strip()
        if src in id_map and dst in id_map:
            edge = {
                "from": src,
                "to": dst,
                "label": _short_title(str(e.get("label") or ""), fallback=""),
                "routing": str(e.get("routing") or "").strip(),
                "style": str(e.get("style") or "solid").strip(),
            }
            if edge not in edges:
                edges.append(edge)

    if not nodes:
        return {"layout": "TB", "nodes": [], "edges": []}

    # Parent column inheritance first; it prevents tags from piling up at column 0.
    by_id = {n["id"]: n for n in nodes}
    for n in nodes:
        if n["column"] is None and n.get("parent") and n["parent"] in by_id:
            n["column"] = by_id[n["parent"]].get("column")

    levels: dict[int, list[dict[str, Any]]] = {}
    for n in nodes:
        levels.setdefault(n["level"], []).append(n)

    for group in levels.values():
        preset_cols = {n["column"] for n in group if n["column"] is not None}
        next_col = 0
        for n in group:
            if n["column"] is not None:
                continue
            while next_col in preset_cols:
                next_col += 1
            n["column"] = next_col
            preset_cols.add(next_col)
            next_col += 1

    min_lv = min(n["level"] for n in nodes)
    if min_lv:
        for n in nodes:
            n["level"] -= min_lv

    layout = str(spec.get("layout") or "TB").strip().upper()
    if layout == "LAYERED":
        layout = "LR"
    elif layout not in {"TB", "LR"}:
        layout = "TB"
    if not spec.get("layout"):
        if subtype in _TIMELINE_SUBTYPES and len(nodes) <= 7:
            layout = "LR"
        elif subtype in _FLOW_SUBTYPES and len(nodes) <= 5:
            layout = "LR"
        elif subtype in _FLOW_SUBTYPES:
            layout = "TB"

    branching = _has_branching_topology(nodes, edges)
    existing_edges = {(e["from"], e["to"]) for e in edges}
    if subtype in _FLOW_SUBTYPES and not branching:
        ordered = sorted(nodes, key=lambda n: (int(n.get("level") or 0), int(n.get("column") or 0), n["id"]))
        for left, right in zip(ordered, ordered[1:]):
            key = (left["id"], right["id"])
            if key not in existing_edges:
                edges.append({"from": key[0], "to": key[1], "label": ""})
                existing_edges.add(key)
        if len(edges) < len(nodes) - 1:
            quality_flags.append("edge_gap")
            warnings.append("流程图连线不足，已按顺序补齐")
    elif subtype in _DECISION_SUBTYPES and not branching:
        by_id = {n["id"]: n for n in nodes}
        root = min(nodes, key=lambda n: (int(n.get("level") or 0), int(n.get("column") or 0)))["id"]
        for n in nodes:
            if n["id"] == root or any(e["to"] == n["id"] for e in edges):
                continue
            parent = str(n.get("parent") or "").strip()
            src = parent if parent in by_id else root
            key = (src, n["id"])
            if key not in existing_edges:
                edges.append({"from": key[0], "to": key[1], "label": ""})
                existing_edges.add(key)
        if len(edges) < len(nodes) - 1:
            quality_flags.append("decision_edge_gap")
            warnings.append("决策树分支连线不足，已尽量补齐")
    if len(nodes) > 18:
        quality_flags.append("complex_graph")
        warnings.append("节点过多，建议拆成多张图或泳道图")

    return {
        "layout": layout,
        "title": _short_title(str(spec.get("title") or "").strip(), fallback="示意图"),
        "structure_summary": str(spec.get("structure_summary") or "").strip(),
        "diagram_subtype": subtype,
        "nodes": nodes,
        "edges": edges,
        "render_warnings": list(spec.get("render_warnings") or []) + warnings,
        "quality_flags": list(spec.get("quality_flags") or []) + quality_flags,
    }


def _infer_edge_routing(edge: dict[str, Any], layout: str, src_node: dict[str, Any], dst_node: dict[str, Any]) -> str:
    routing = str(edge.get("routing") or "").strip().upper()
    if routing in {"LR", "TB", "SIDE", "CURVED"}:
        return "side" if routing == "SIDE" else routing.lower()
    layout = (layout or "TB").upper()
    if layout == "LR":
        return "lr"
    if int(src_node.get("level") or 0) != int(dst_node.get("level") or 0):
        return "tb"
    if int(src_node.get("column") or 0) != int(dst_node.get("column") or 0):
        return "side"
    return "tb"


def _pick_connection_points(
    src: dict[str, float],
    dst: dict[str, float],
    *,
    routing: str,
) -> tuple[float, float, float, float]:
    routing = (routing or "tb").lower()
    if routing == "lr":
        return (
            src["x"] + src["w"] / 2 + 0.04,
            src["y"],
            dst["x"] - dst["w"] / 2 - 0.04,
            dst["y"],
        )
    if routing == "tb":
        return (
            src["x"],
            src["bottom"] - 0.05,
            dst["x"],
            dst["top"] + 0.05,
        )
    if routing == "side":
        if src["x"] <= dst["x"]:
            return (
                src["x"] + src["w"] / 2 + 0.04,
                src["y"],
                dst["x"] - dst["w"] / 2 - 0.04,
                dst["y"],
            )
        return (
            src["x"] - src["w"] / 2 - 0.04,
            src["y"],
            dst["x"] + dst["w"] / 2 + 0.04,
            dst["y"],
        )
    if routing == "curved":
        return (
            src["x"] + src["w"] / 2 + 0.04,
            src["y"],
            dst["x"] + dst["w"] / 2 + 0.04,
            dst["y"],
        )
    return (
        src["x"],
        src["bottom"] - 0.05,
        dst["x"],
        dst["top"] + 0.05,
    )


def _level_groups(nodes: list[dict[str, Any]]) -> dict[int, list[dict[str, Any]]]:
    levels: dict[int, list[dict[str, Any]]] = {}
    for n in nodes:
        levels.setdefault(int(n["level"]), []).append(n)
    for group in levels.values():
        group.sort(key=lambda x: (int(x.get("column") or 0), x["id"]))
    return levels


def _column_widths(nodes: list[dict[str, Any]]) -> dict[int, float]:
    out: dict[int, float] = {}
    for n in nodes:
        col = int(n.get("column") or 0)
        out[col] = max(out.get(col, 0.0), float(n.get("w") or 2.4))
    return out


def _layout_positions(spec: dict[str, Any]) -> tuple[dict[str, dict[str, float]], float, float]:
    nodes = spec["nodes"]
    levels = _level_groups(nodes)
    max_level = max(levels)
    positions: dict[str, dict[str, float]] = {}

    if spec["layout"] == "LR":
        level_widths = {lv: max(float(n.get("w") or 2.4) for n in group) for lv, group in levels.items()}
        col_count = max((int(n.get("column") or 0) for n in nodes), default=0) + 1
        fig_w = _CANVAS["margin_x"] * 2 + sum(level_widths.values()) + max_level * 1.05
        fig_h = _CANVAS["margin_bottom"] + _CANVAS["margin_top"] + max(_CANVAS["min_h"] - 1.7, col_count * 1.12)
        fig_w = min(_CANVAS["max_w"], max(_CANVAS["min_w"], fig_w))
        fig_h = min(_CANVAS["max_h"], max(_CANVAS["min_h"], fig_h))

        x = _CANVAS["margin_x"] + level_widths.get(0, 2.4) / 2
        level_x: dict[int, float] = {}
        for lv in range(max_level + 1):
            if lv > 0:
                x += level_widths.get(lv - 1, 2.4) / 2 + 1.05 + level_widths.get(lv, 2.4) / 2
            level_x[lv] = x
        for lv, group in levels.items():
            max_col = max((int(n.get("column") or 0) for n in group), default=0)
            for n in group:
                col = int(n.get("column") or 0)
                y = fig_h / 2 if max_col == 0 else fig_h - _CANVAS["margin_top"] - col * ((fig_h - _CANVAS["margin_top"] - _CANVAS["margin_bottom"]) / max(max_col, 1))
                positions[n["id"]] = {"x": level_x[lv], "y": y}
        return positions, fig_w, fig_h

    # Top-to-bottom layout: compute true row heights so wrapped labels and tags do not overlap.
    col_widths = _column_widths(nodes)
    cols = list(range(max(col_widths.keys(), default=0) + 1))
    fig_w = _CANVAS["margin_x"] * 2 + sum(col_widths.get(c, 2.4) for c in cols) + _CANVAS["col_gap"] * max(len(cols) - 1, 0)
    level_heights: dict[int, float] = {}
    for lv, group in levels.items():
        by_col: dict[int, list[dict[str, Any]]] = {}
        for n in group:
            by_col.setdefault(int(n.get("column") or 0), []).append(n)
        max_h = 0.0
        for col_nodes in by_col.values():
            tags = [n for n in col_nodes if n["shape"] == "tag"]
            regular = [n for n in col_nodes if n["shape"] != "tag"]
            if tags and not regular:
                stack_h = sum(float(n.get("h") or 0.34) for n in tags) + 0.16 * max(len(tags) - 1, 0)
                max_h = max(max_h, stack_h)
            else:
                max_h = max(max_h, *(float(n.get("h") or 0.72) for n in col_nodes))
        level_heights[lv] = max(max_h, 0.58)

    fig_h = _CANVAS["margin_top"] + _CANVAS["margin_bottom"] + sum(level_heights.values()) + _CANVAS["level_gap"] * max(len(level_heights) - 1, 0)
    fig_w = min(_CANVAS["max_w"], max(_CANVAS["min_w"], fig_w))
    fig_h = min(_CANVAS["max_h"], max(_CANVAS["min_h"], fig_h))

    # Recompute evenly if canvas is clamped, maintaining at least no identical coordinates.
    usable_w = fig_w - _CANVAS["margin_x"] * 2
    col_step = usable_w / max(len(cols), 1)
    col_x = {c: _CANVAS["margin_x"] + col_step * (i + 0.5) for i, c in enumerate(cols)}

    y_cursor = fig_h - _CANVAS["margin_top"]
    for lv in range(max_level + 1):
        group = levels.get(lv, [])
        row_h = level_heights.get(lv, 0.72)
        row_center = y_cursor - row_h / 2
        by_col: dict[int, list[dict[str, Any]]] = {}
        for n in group:
            by_col.setdefault(int(n.get("column") or 0), []).append(n)
        for col, col_nodes in by_col.items():
            tags = [n for n in col_nodes if n["shape"] == "tag"]
            regular = [n for n in col_nodes if n["shape"] != "tag"]
            for n in regular:
                positions[n["id"]] = {"x": col_x.get(col, fig_w / 2), "y": row_center}
            if tags and not regular:
                stack_h = sum(float(n.get("h") or 0.34) for n in tags) + 0.16 * max(len(tags) - 1, 0)
                y = row_center + stack_h / 2
                for n in tags:
                    h = float(n.get("h") or 0.34)
                    positions[n["id"]] = {"x": col_x.get(col, fig_w / 2), "y": y - h / 2}
                    y -= h + 0.16
            else:
                # If a model puts tags on the same level as regular boxes, stack them just below the box.
                start_y = row_center - max((float(n.get("h") or 0.72) for n in regular), default=0.72) / 2 - 0.28
                for idx, n in enumerate(tags):
                    positions[n["id"]] = {"x": col_x.get(col, fig_w / 2), "y": start_y - idx * (float(n.get("h") or 0.34) + 0.14)}
        y_cursor -= row_h + _CANVAS["level_gap"]

    return positions, fig_w, fig_h


def _icon_mark(icon: str) -> str:
    marks = {
        "user": "U",
        "data": "D",
        "service": "S",
        "search": "Q",
        "output": "O",
        "decision": "?",
        "time": "T",
        "node": "",
    }
    return marks.get(str(icon or "").strip().lower(), "")


def _draw_badge(ax, x: float, y: float, node: dict[str, Any], palette: dict[str, str]) -> None:
    # Letter badges such as U/S were too cryptic in book diagrams. Keep icon
    # hints in the data for future real icon rendering, but do not draw letters.
    return


def _draw_node(ax, x: float, y: float, node: dict[str, Any], palette: dict[str, str]) -> dict[str, float]:
    shape = node["shape"]
    label = node.get("wrapped_label") or node["label"]
    w, h = float(node.get("w") or 2.4), float(node.get("h") or 0.72)
    fs = clamp_font_size(str(node.get("label") or ""), base=9.0 if shape != "tag" else 7.6, min_size=6.8)

    if shape == "diamond":
        poly = Polygon(
            [(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)],
            closed=True,
            facecolor="#FFFFFF",
            edgecolor=palette["edge"],
            linewidth=1.35,
        )
        ax.add_patch(poly)
        ax.text(x, y, label, ha="center", va="center", fontsize=fs, fontweight="bold", linespacing=1.22)
        _draw_badge(ax, x, y, node, palette)
    elif shape == "tag":
        box = FancyBboxPatch(
            (x - w / 2, y - h / 2),
            w,
            h,
            boxstyle="round,pad=0.025,rounding_size=0.05",
            facecolor=palette["tag_fill"],
            edgecolor=palette["tag_edge"],
            linewidth=0.9,
        )
        ax.add_patch(box)
        ax.text(x, y, label, ha="center", va="center", fontsize=fs, linespacing=1.1)
        _draw_badge(ax, x, y, node, palette)
    else:
        box = FancyBboxPatch(
            (x - w / 2, y - h / 2),
            w,
            h,
            boxstyle="round,pad=0.035,rounding_size=0.06",
            facecolor=palette["fill"] if shape != "rounded" else "#FFFFFF",
            edgecolor=palette["edge"],
            linewidth=1.25,
        )
        ax.add_patch(box)
        fw = "bold" if shape == "rounded" and str(node.get("label") or "").startswith("选择") else "normal"
        ax.text(x, y, label, ha="center", va="center", fontsize=fs, fontweight=fw, linespacing=1.22)
        _draw_badge(ax, x, y, node, palette)

    return {"x": x, "y": y, "w": w, "h": h, "top": y + h / 2, "bottom": y - h / 2}


def _svg_xy(x: float, y: float, fig_h: float, scale: float) -> tuple[float, float]:
    return x * scale, (fig_h - y) * scale


def _svg_text(label: str, x: float, y: float, *, size: float, weight: str = "400", color: str = "#1C2833") -> str:
    lines = [line for line in str(label or "").splitlines() if line.strip()] or [""]
    line_h = size * 1.22
    start = y - line_h * (len(lines) - 1) / 2
    spans = []
    for i, line in enumerate(lines):
        spans.append(
            f'<tspan x="{x:.1f}" y="{start + i * line_h:.1f}">{html.escape(line)}</tspan>'
        )
    return (
        f'<text text-anchor="middle" dominant-baseline="middle" '
        f'font-family="Microsoft YaHei, Noto Sans CJK SC, Arial, sans-serif" '
        f'font-size="{size:.1f}" font-weight="{weight}" fill="{color}">{"".join(spans)}</text>'
    )


def _render_svg_file(
    norm: dict[str, Any],
    positions: dict[str, dict[str, float]],
    fig_w: float,
    fig_h: float,
    svg_path: Path,
    *,
    title: str = "",
) -> bool:
    scale = 96.0
    width, height = fig_w * scale, fig_h * scale
    nodes = norm["nodes"]
    node_by_id = {n["id"]: n for n in nodes}
    drawn: dict[str, dict[str, float]] = {}
    for n in nodes:
        pos = positions[n["id"]]
        drawn[n["id"]] = {
            "x": pos["x"],
            "y": pos["y"],
            "w": float(n.get("w") or 2.4),
            "h": float(n.get("h") or 0.72),
            "top": pos["y"] + float(n.get("h") or 0.72) / 2,
            "bottom": pos["y"] - float(n.get("h") or 0.72) / 2,
        }

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" viewBox="0 0 {width:.0f} {height:.0f}">',
        "<defs>",
        '<marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto" markerUnits="strokeWidth">',
        '<path d="M0,0 L8,4 L0,8 z" fill="context-stroke"/>',
        "</marker>",
        '<filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%">',
        '<feDropShadow dx="0" dy="2" stdDeviation="2" flood-color="#0F172A" flood-opacity="0.10"/>',
        "</filter>",
        "</defs>",
        '<rect width="100%" height="100%" fill="#FFFFFF"/>',
    ]
    if title and title != "示意图":
        tx, ty = width / 2, 28
        parts.append(_svg_text(wrap_text(title, max_units=24, max_lines=2), tx, ty, size=17, weight="700"))

    for e in norm["edges"]:
        src = drawn.get(e["from"])
        dst = drawn.get(e["to"])
        if not src or not dst:
            continue
        src_node = node_by_id[e["from"]]
        dst_node = node_by_id[e["to"]]
        col = int(dst_node.get("column") or 0)
        color = _PALETTE[col % len(_PALETTE)]["edge"]
        routing = _infer_edge_routing(e, norm["layout"], src_node, dst_node)
        x1, y1, x2, y2 = _pick_connection_points(src, dst, routing=routing)
        sx1, sy1 = _svg_xy(x1, y1, fig_h, scale)
        sx2, sy2 = _svg_xy(x2, y2, fig_h, scale)
        parts.append(
            f'<line x1="{sx1:.1f}" y1="{sy1:.1f}" x2="{sx2:.1f}" y2="{sy2:.1f}" '
            f'stroke="{color}" stroke-width="2.0" stroke-linecap="round" marker-end="url(#arrow)" opacity="0.9"/>'
        )

    for n in nodes:
        pos = positions[n["id"]]
        x, y = _svg_xy(pos["x"], pos["y"], fig_h, scale)
        w, h = float(n.get("w") or 2.4) * scale, float(n.get("h") or 0.72) * scale
        col = int(n.get("column") or 0)
        palette = _PALETTE[col % len(_PALETTE)]
        shape = n.get("shape") or "box"
        label = n.get("wrapped_label") or n.get("label") or ""
        fs = 11.5 if shape != "tag" else 9.6
        if shape == "diamond":
            points = [
                (x, y - h / 2),
                (x + w / 2, y),
                (x, y + h / 2),
                (x - w / 2, y),
            ]
            pts = " ".join(f"{px:.1f},{py:.1f}" for px, py in points)
            parts.append(f'<polygon points="{pts}" fill="#FFFFFF" stroke="{palette["edge"]}" stroke-width="2" filter="url(#softShadow)"/>')
            weight = "700"
        else:
            fill = palette["tag_fill"] if shape == "tag" else ("#FFFFFF" if shape == "rounded" else palette["fill"])
            edge = palette["tag_edge"] if shape == "tag" else palette["edge"]
            radius = 9 if shape != "tag" else 6
            parts.append(
                f'<rect x="{x - w / 2:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" height="{h:.1f}" '
                f'rx="{radius}" fill="{fill}" stroke="{edge}" stroke-width="1.8" filter="url(#softShadow)"/>'
            )
            weight = "600" if shape == "rounded" else "500"
        mark = _icon_mark(str(n.get("icon") or ""))
        if mark:
            bx = x - w / 2 + 22
            by = y - h / 2 + 18
            parts.append(f'<circle cx="{bx:.1f}" cy="{by:.1f}" r="11" fill="{palette.get("badge", palette["edge"])}" stroke="#FFFFFF" stroke-width="1.2"/>')
            parts.append(_svg_text(mark, bx, by + 0.5, size=7.2, weight="700", color="#FFFFFF"))
        parts.append(_svg_text(label, x, y + 1, size=fs, weight=weight))

    parts.append("</svg>")
    try:
        svg_path.parent.mkdir(parents=True, exist_ok=True)
        svg_path.write_text("\n".join(parts), encoding="utf-8")
        return svg_path.is_file()
    except Exception:
        logger.exception("failed to write structured diagram svg")
        return False


def render_structured_diagram(spec: dict[str, Any], output_path: Path, *, title: str = "") -> Path:
    norm = _normalize_spec(spec)
    nodes = norm["nodes"]
    edges = norm["edges"]
    if not nodes:
        raise ValueError("structured diagram 缺少 nodes")

    positions, fig_w, fig_h = _layout_positions(norm)
    fig_title = _short_title(title or norm.get("title") or "", fallback="示意图")
    _render_svg_file(norm, positions, fig_w, fig_h, output_path.with_suffix(".svg"), title=fig_title)

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis("off")
    if fig_title and fig_title != "示意图":
        ax.set_title(
            wrap_text(fig_title, max_units=24, max_lines=2),
            fontsize=12,
            pad=9,
            fontweight="bold",
            color="#1C2833",
        )

    drawn: dict[str, dict[str, float]] = {}
    node_by_id = {n["id"]: n for n in nodes}

    # Draw edges first so arrow lines stay behind boxes.
    for n in nodes:
        pos = positions[n["id"]]
        drawn[n["id"]] = {"x": pos["x"], "y": pos["y"], "w": float(n.get("w") or 2.4), "h": float(n.get("h") or 0.72)}
        drawn[n["id"]]["top"] = drawn[n["id"]]["y"] + drawn[n["id"]]["h"] / 2
        drawn[n["id"]]["bottom"] = drawn[n["id"]]["y"] - drawn[n["id"]]["h"] / 2

    for e in edges:
        src = drawn.get(e["from"])
        dst = drawn.get(e["to"])
        if not src or not dst:
            continue
        src_node = node_by_id[e["from"]]
        dst_node = node_by_id[e["to"]]
        col = int(dst_node.get("column") or 0)
        color = _PALETTE[col % len(_PALETTE)]["edge"]

        routing = _infer_edge_routing(e, norm["layout"], src_node, dst_node)
        x1, y1, x2, y2 = _pick_connection_points(src, dst, routing=routing)

        ax.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            arrowprops=dict(arrowstyle="-|>", color=color, lw=1.1, shrinkA=3, shrinkB=3, alpha=0.92),
            zorder=1,
        )

    for n in nodes:
        pos = positions[n["id"]]
        col = int(n.get("column") or 0)
        palette = _PALETTE[col % len(_PALETTE)]
        _draw_node(ax, pos["x"], pos["y"], n, palette)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout(pad=0.25)
    plt.savefig(output_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return output_path


def generate_structured_diagram(
    render_spec: dict[str, Any],
    output_path: Path,
    *,
    title: str = "",
) -> tuple[str, Path]:
    if not has_structured_graph(render_spec):
        raise ValueError("render_spec 不含有效 nodes/edges")
    norm = _normalize_spec(render_spec)
    png = render_structured_diagram(norm, output_path, title=title)
    summary = norm.get("structure_summary") or f"structured nodes={len(norm['nodes'])} edges={len(norm['edges'])}"
    return summary, png
