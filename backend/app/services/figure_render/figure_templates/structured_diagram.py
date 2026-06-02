"""通用结构化示意图：按理解层输出的 nodes/edges/level 自适应绘制，层数不固定。"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "DejaVu Sans", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Polygon

from app.services.figure_render.figure_structure import has_structured_graph

logger = logging.getLogger(__name__)

_PALETTE = [
    {"fill": "#E8F8F5", "edge": "#1E8449", "tag_fill": "#D5F5E3", "tag_edge": "#27AE60"},
    {"fill": "#EBF5FB", "edge": "#2E86C1", "tag_fill": "#D6EAF8", "tag_edge": "#3498DB"},
    {"fill": "#F4ECF7", "edge": "#7D3C98", "tag_fill": "#E8DAEF", "tag_edge": "#9B59B6"},
    {"fill": "#FEF9E7", "edge": "#B7950B", "tag_fill": "#FCF3CF", "tag_edge": "#F1C40F"},
]


def _normalize_spec(spec: dict[str, Any]) -> dict[str, Any]:
    nodes_in = spec.get("nodes") or []
    edges_in = spec.get("edges") or []
    nodes: list[dict[str, Any]] = []
    id_map: dict[str, str] = {}

    for i, raw in enumerate(nodes_in):
        if not isinstance(raw, dict):
            continue
        nid = str(raw.get("id") or f"n{i}").strip()
        label = str(raw.get("label") or "").strip()
        if not label:
            continue
        shape = str(raw.get("shape") or "rounded").lower()
        try:
            level = int(raw.get("level", 0))
        except (TypeError, ValueError):
            level = 0
        column = raw.get("column")
        parent = str(raw.get("parent") or "").strip() or None
        nodes.append({
            "id": nid,
            "label": label[:40],
            "shape": shape,
            "level": level,
            "column": int(column) if column is not None else None,
            "parent": parent,
        })
        id_map[nid] = nid

    edges: list[dict[str, str]] = []
    for e in edges_in:
        if not isinstance(e, dict):
            continue
        src = str(e.get("from") or "").strip()
        dst = str(e.get("to") or "").strip()
        if src in id_map and dst in id_map:
            edges.append({"from": src, "to": dst, "label": str(e.get("label") or "").strip()})

    if not nodes:
        return {"layout": "TB", "nodes": [], "edges": []}

    by_id = {n["id"]: n for n in nodes}
    for n in nodes:
        if n["column"] is None and n.get("parent") and n["parent"] in by_id:
            n["column"] = by_id[n["parent"]].get("column")

    levels: dict[int, list[dict[str, Any]]] = {}
    for n in nodes:
        levels.setdefault(n["level"], []).append(n)

    for lv, group in levels.items():
        unset = [n for n in group if n["column"] is None]
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

    if nodes[0]["level"] != 0:
        min_lv = min(n["level"] for n in nodes)
        for n in nodes:
            n["level"] -= min_lv

    return {
        "layout": str(spec.get("layout") or "TB").upper(),
        "title": str(spec.get("title") or "").strip(),
        "structure_summary": str(spec.get("structure_summary") or "").strip(),
        "nodes": nodes,
        "edges": edges,
    }


def _node_size(shape: str) -> tuple[float, float]:
    if shape == "tag":
        return 1.05, 0.30
    if shape == "diamond":
        return 2.6, 0.90
    return 2.5, 0.68


def _draw_node(ax, x: float, y: float, node: dict[str, Any], palette: dict[str, str]) -> dict[str, float]:
    shape = node["shape"]
    label = node["label"]
    w, h = _node_size(shape)

    if shape == "diamond":
        poly = Polygon(
            [(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)],
            closed=True,
            facecolor="#FDFEFE",
            edgecolor=palette["edge"],
            linewidth=1.5,
        )
        ax.add_patch(poly)
        ax.text(x, y, label, ha="center", va="center", fontsize=9.5, fontweight="bold")
    elif shape == "tag":
        box = FancyBboxPatch(
            (x - w / 2, y - h / 2),
            w,
            h,
            boxstyle="round,pad=0.02,rounding_size=0.05",
            facecolor=palette["tag_fill"],
            edgecolor=palette["tag_edge"],
            linewidth=0.9,
        )
        ax.add_patch(box)
        ax.text(x, y, label, ha="center", va="center", fontsize=7.5)
    else:
        box = FancyBboxPatch(
            (x - w / 2, y - h / 2),
            w,
            h,
            boxstyle="round,pad=0.03,rounding_size=0.06",
            facecolor=palette["fill"] if shape != "rounded" else "#FFFFFF",
            edgecolor=palette["edge"],
            linewidth=1.3,
        )
        ax.add_patch(box)
        fw = "bold" if shape == "rounded" and label.startswith("选择") else "normal"
        ax.text(x, y, label, ha="center", va="center", fontsize=9, fontweight=fw)

    return {"x": x, "y": y, "w": w, "h": h, "top": y + h / 2, "bottom": y - h / 2}


def _layout_positions(spec: dict[str, Any]) -> tuple[dict[str, dict[str, float]], float, float]:
    nodes = spec["nodes"]
    layout = spec["layout"]
    levels: dict[int, list[dict[str, Any]]] = {}
    for n in nodes:
        levels.setdefault(n["level"], []).append(n)

    max_level = max(levels)
    max_cols = max((max(n["column"] for n in g) + 1 for g in levels.values()), default=1)

    fig_w = max(8.5, max_cols * 3.4 + 1.0)
    level_count = max_level + 1
    fig_h = max(5.5, 1.8 + level_count * 1.55)

    positions: dict[str, dict[str, float]] = {}

    if layout == "LR":
        for lv, group in levels.items():
            group.sort(key=lambda n: n["column"])
            cols = max(n["column"] for n in group) + 1
            for n in group:
                x = 1.2 + lv * (fig_w - 2.4) / max(max_level, 1)
                if cols == 1:
                    y = fig_h / 2
                else:
                    y = fig_h - 1.2 - n["column"] * ((fig_h - 2.0) / max(cols - 1, 1))
                positions[n["id"]] = {"x": x, "y": y}
    else:
        for lv, group in levels.items():
            group.sort(key=lambda n: n["column"])
            cols = max(n["column"] for n in group) + 1
            y = fig_h - 1.0 - lv * ((fig_h - 2.0) / max(level_count - 1, 1))
            for n in group:
                if cols == 1:
                    x = fig_w / 2
                else:
                    x = 0.6 + (n["column"] + 0.5) * ((fig_w - 1.2) / cols)
                if n["shape"] == "tag":
                    siblings = [g for g in group if g["shape"] == "tag" and g["column"] == n["column"]]
                    idx = siblings.index(n) if n in siblings else 0
                    y_tag = y - 0.35 - idx * 0.38
                    positions[n["id"]] = {"x": x, "y": y_tag}
                else:
                    positions[n["id"]] = {"x": x, "y": y}

    return positions, fig_w, fig_h


def render_structured_diagram(spec: dict[str, Any], output_path: Path, *, title: str = "") -> Path:
    norm = _normalize_spec(spec)
    nodes = norm["nodes"]
    edges = norm["edges"]
    if not nodes:
        raise ValueError("structured diagram 缺少 nodes")

    positions, fig_w, fig_h = _layout_positions(norm)
    fig_title = title or norm.get("title") or "示意图"

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis("off")
    ax.set_title(fig_title, fontsize=13, pad=10, fontweight="bold", color="#1C2833")

    drawn: dict[str, dict[str, float]] = {}
    node_by_id = {n["id"]: n for n in nodes}

    for n in nodes:
        pos = positions[n["id"]]
        col = n.get("column") or 0
        palette = _PALETTE[col % len(_PALETTE)]
        drawn[n["id"]] = _draw_node(ax, pos["x"], pos["y"], n, palette)

    for e in edges:
        src = drawn.get(e["from"])
        dst = drawn.get(e["to"])
        if not src or not dst:
            continue
        src_node = node_by_id[e["from"]]
        dst_node = node_by_id[e["to"]]
        col = dst_node.get("column") or 0
        color = _PALETTE[col % len(_PALETTE)]["edge"]

        if norm["layout"] == "LR":
            x1, y1 = src["x"] + src["w"] / 2, src["y"]
            x2, y2 = dst["x"] - dst["w"] / 2, dst["y"]
        elif src_node["level"] < dst_node["level"]:
            x1, y1 = src["x"], src["bottom"] - 0.02
            x2, y2 = dst["x"], dst["top"] + 0.02
        else:
            x1, y1 = src["x"], src["top"] + 0.02
            x2, y2 = dst["x"], dst["bottom"] - 0.02

        ax.annotate(
            "",
            xy=(x2, y2),
            xytext=(x1, y1),
            arrowprops=dict(arrowstyle="-|>", color=color, lw=1.3, shrinkA=2, shrinkB=2),
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(output_path, bbox_inches="tight", facecolor="white")
    svg_path = output_path.with_suffix(".svg")
    try:
        plt.savefig(svg_path, format="svg", bbox_inches="tight", facecolor="white")
    except Exception:
        pass
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
