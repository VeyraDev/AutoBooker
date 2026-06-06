"""Grammar-level structured renderers.

These renderers consume parser-native structures such as events, layers,
comparison columns, and relationship concepts. They keep generic_graph as a
fallback instead of making it the default for every diagram grammar.
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
matplotlib.rcParams["font.family"] = ["SimHei", "Microsoft YaHei", "Noto Sans CJK SC", "DejaVu Sans", "sans-serif"]
matplotlib.rcParams["axes.unicode_minus"] = False
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt

from app.services.figures.render.edge_router import orthogonal_route
from app.services.figures.render.icons import draw_icon
from app.services.figures.render.layout_utils import estimate_node_size, wrap_text
from app.services.figures.render.svg_export import try_export_matplotlib_svg
from app.services.figures.render.structured.generic_graph import generate_structured_diagram

BLUE = "#2563EB"
GREEN = "#0891B2"
PURPLE = "#64748B"
AMBER = "#D97706"
INK = "#1C2833"
MUTED = "#667085"
SOFT_BLUE = "#EFF6FF"
SOFT_CYAN = "#ECFEFF"
SOFT_SLATE = "#F8FAFC"
SOFT_AMBER = "#FFF7ED"


def _short(text: Any, limit: int = 28) -> str:
    raw = str(text or "").strip()
    clipped = raw[:limit]
    if len(raw) > limit and clipped and clipped[-1].isalnum():
        clipped = re.sub(r"[A-Za-z0-9_]+$", "", clipped).rstrip() or raw[:limit]
    return clipped.strip(" ：:，,。")


def _finish(fig, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout(pad=0.3)
    plt.savefig(output_path, bbox_inches="tight", facecolor="white")
    try_export_matplotlib_svg(fig, output_path.with_suffix(".svg"))
    plt.close(fig)
    return output_path


def _icon_mark(icon: str) -> str:
    return {
        "user": "U",
        "data": "D",
        "service": "S",
        "search": "Q",
        "output": "O",
        "decision": "?",
        "time": "T",
        "node": "",
    }.get(str(icon or "").strip().lower(), "")


def _auto_icon(label: str) -> str:
    text = str(label or "").lower()
    if re.search(r"user|用户|客户|person|human", text):
        return "user"
    if re.search(r"data|数据库|向量库|知识库|store|db|sql", text):
        return "data"
    if re.search(r"检索|搜索|retriev|search", text):
        return "search"
    if re.search(r"生成|输出|回答|result|output", text):
        return "output"
    if re.search(r"服务|api|model|模型|llm|agent", text):
        return "service"
    return "node"


def _box(ax, x: float, y: float, w: float, h: float, label: str, *, face: str, edge: str, fs: float = 9.0, bold: bool = False, icon: str = "") -> None:
    wrapped, auto_w, auto_h = estimate_node_size(label, shape="box", max_units=max(8, w * 5.1))
    w = max(w, auto_w)
    h = max(h, auto_h)
    patch = mpatches.FancyBboxPatch(
        (x - w / 2, y - h / 2),
        w,
        h,
        boxstyle="round,pad=0.035,rounding_size=0.06",
        linewidth=1.15,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(patch)
    if icon and icon not in {"node", ""}:
        draw_icon(ax, x - w / 2, y + h / 2, _auto_icon(label) if icon in {"auto", "service"} else icon, size=min(0.14, w * 0.12))
    ax.text(x, y, wrapped, ha="center", va="center", fontsize=fs, fontweight="bold" if bold else "normal", linespacing=1.15)


def _arrow(ax, x1: float, y1: float, x2: float, y2: float, *, color: str = BLUE, label: str = "", orthogonal: bool = True) -> None:
    if orthogonal and abs(x1 - x2) > 0.2 and abs(y1 - y2) > 0.2:
        points = orthogonal_route(x1, y1, x2, y2)
        for (px1, py1), (px2, py2) in zip(points, points[1:]):
            ax.plot([px1, px2], [py1, py2], color=color, linewidth=1.05)
        ax.annotate("", xy=(x2, y2), xytext=(points[-2][0], points[-2][1]), arrowprops=dict(arrowstyle="-|>", color=color, lw=1.05, shrinkA=0, shrinkB=5))
    else:
        ax.annotate("", xy=(x2, y2), xytext=(x1, y1), arrowprops=dict(arrowstyle="-|>", color=color, lw=1.05, shrinkA=5, shrinkB=5))
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.12, wrap_text(label, max_units=9, max_lines=1), ha="center", va="bottom", fontsize=7.2, color=color)


def generate_timeline_diagram(spec: dict[str, Any], output_path: Path, *, title: str = "") -> tuple[str, Path]:
    events = [e for e in (spec.get("events") or []) if isinstance(e, dict)]
    if not events:
        return generate_structured_diagram(spec, output_path, title=title)
    n = len(events)
    fig_w = max(8.8, min(15.5, n * 1.55 + 2.0))
    fig, ax = plt.subplots(figsize=(fig_w, 4.2), dpi=150)
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, 4.2)
    ax.axis("off")
    ax.set_title(wrap_text(title or spec.get("title") or "时间线", max_units=28, max_lines=2), fontsize=12, fontweight="bold", color=INK)

    y = 2.15
    left, right = 0.9, fig_w - 0.9
    ax.plot([left, right], [y, y], color=BLUE, linewidth=1.4)
    for i, event in enumerate(events):
        x = left if n == 1 else left + (right - left) * i / (n - 1)
        ax.scatter([x], [y], s=72, color=BLUE, zorder=3)
        dy = 0.82 if i % 2 == 0 else -0.82
        ax.plot([x, x], [y, y + dy * 0.55], color=BLUE, linewidth=0.9)
        ax.text(x, y + dy * 0.72, _short(event.get("time") or event.get("year"), 12), ha="center", va="center", fontsize=9, fontweight="bold", color=INK)
        ax.text(x, y + dy * 1.05, wrap_text(_short(event.get("label") or event.get("event"), 24), max_units=9, max_lines=2), ha="center", va="center", fontsize=8.2, color=INK)
    return f"timeline events={n}", _finish(fig, output_path)


def generate_taxonomy_diagram(spec: dict[str, Any], output_path: Path, *, title: str = "") -> tuple[str, Path]:
    root = _short(spec.get("root") or spec.get("title") or "核心分类", 24)
    children = [c for c in (spec.get("children") or []) if isinstance(c, dict)]
    if not children:
        return generate_structured_diagram(spec, output_path, title=title)
    cols = max(2, len(children))
    fig_w = max(8.8, min(15.5, cols * 2.15 + 1.2))
    fig_h = 5.5
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis("off")
    ax.set_title(wrap_text(title or spec.get("title") or "分类图", max_units=28, max_lines=2), fontsize=12, fontweight="bold", color=INK)

    root_x, root_y = fig_w / 2, 4.55
    _box(ax, root_x, root_y, 2.5, 0.62, root, face="#FFFFFF", edge=BLUE, bold=True)
    for i, child in enumerate(children):
        x = fig_w * (i + 1) / (len(children) + 1)
        y = 3.25
        label = _short(child.get("label"), 22)
        _arrow(ax, root_x, root_y - 0.35, x, y + 0.35, color=BLUE)
        _box(ax, x, y, 1.9, 0.58, label, face=SOFT_BLUE, edge=BLUE)
        grands = [g for g in (child.get("children") or []) if isinstance(g, dict)]
        for j, grand in enumerate(grands[:6]):
            gy = 2.18 - j * 0.48
            _arrow(ax, x, y - 0.32, x, gy + 0.18, color=GREEN)
            _box(ax, x, gy, 1.55, 0.34, _short(grand.get("label"), 18), face=SOFT_CYAN, edge=GREEN, fs=7.2)
    return f"taxonomy groups={len(children)}", _finish(fig, output_path)


def generate_comparison_diagram(spec: dict[str, Any], output_path: Path, *, title: str = "") -> tuple[str, Path]:
    columns = [_short(c, 18) for c in (spec.get("columns") or []) if _short(c, 18)]
    dimensions = [_short(d, 18) for d in (spec.get("dimensions") or []) if _short(d, 18)]
    if not columns or not dimensions:
        return generate_structured_diagram(spec, output_path, title=title)
    cell_lookup: dict[tuple[str, str], str] = {}
    for cell in spec.get("cells") or []:
        if not isinstance(cell, dict):
            continue
        dimension = _short(cell.get("dimension") or cell.get("row"), 18)
        values = cell.get("values")
        if not dimension or not isinstance(values, dict):
            continue
        for column, value in values.items():
            key = (dimension, _short(column, 18))
            cell_lookup[key] = _short(value, 34)
    cols = len(columns) + 1
    rows = len(dimensions) + 1
    fig_w = max(8.5, min(14.5, cols * 1.75 + 1.0))
    fig_h = max(4.8, min(9.5, rows * 0.55 + 1.6))
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)
    ax.set_xlim(0, cols)
    ax.set_ylim(0, rows + 0.8)
    ax.axis("off")
    ax.set_title(wrap_text(title or spec.get("title") or "对比矩阵", max_units=28, max_lines=2), fontsize=12, fontweight="bold", color=INK)

    for r in range(rows):
        for c in range(cols):
            x, y = c + 0.5, rows - r - 0.15
            face = SOFT_BLUE if r == 0 or c == 0 else "#FFFFFF"
            edge = "#D0D5DD"
            rect = mpatches.Rectangle((c, y - 0.35), 1, 0.7, facecolor=face, edgecolor=edge, linewidth=0.8)
            ax.add_patch(rect)
            if r == 0 and c == 0:
                text = "维度"
            elif r == 0:
                text = columns[c - 1]
            elif c == 0:
                text = dimensions[r - 1]
            else:
                text = cell_lookup.get((dimensions[r - 1], columns[c - 1]), "")
            if text:
                ax.text(x, y, wrap_text(text, max_units=8, max_lines=2), ha="center", va="center", fontsize=8.2, fontweight="bold" if r == 0 or c == 0 else "normal", color=INK)
    if not cell_lookup:
        ax.text(cols / 2, 0.28, "注：如需逐格内容，可在标注中补充每个对象在各维度下的取值。", ha="center", va="center", fontsize=7.6, color=MUTED)
    return f"comparison columns={len(columns)} dimensions={len(dimensions)}", _finish(fig, output_path)


def generate_architecture_diagram(spec: dict[str, Any], output_path: Path, *, title: str = "") -> tuple[str, Path]:
    layers = [l for l in (spec.get("layers") or []) if isinstance(l, dict)]
    if not layers:
        return generate_structured_diagram(spec, output_path, title=title)
    max_modules = max(len(l.get("modules") or []) for l in layers)
    fig_w = max(8.8, min(14.5, max_modules * 2.0 + 1.8))
    fig_h = max(5.0, len(layers) * 1.15 + 1.5)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis("off")
    ax.set_title(wrap_text(title or spec.get("title") or "系统架构", max_units=28, max_lines=2), fontsize=12, fontweight="bold", color=INK)

    positions: dict[str, tuple[float, float]] = {}
    layer_modules: list[list[str]] = []
    for li, layer in enumerate(layers):
        y = fig_h - 1.2 - li * 1.1
        band = mpatches.FancyBboxPatch((0.55, y - 0.46), fig_w - 1.1, 0.92, boxstyle="round,pad=0.02", facecolor=SOFT_BLUE, edgecolor="#D0D5DD", linewidth=0.8)
        ax.add_patch(band)
        ax.text(0.85, y, _short(layer.get("label"), 14), ha="left", va="center", fontsize=8.2, fontweight="bold", color=MUTED)
        modules = [_short(m, 20) for m in (layer.get("modules") or []) if _short(m, 20)]
        layer_modules.append(modules)
        for mi, module in enumerate(modules):
            x = fig_w * (mi + 1) / (len(modules) + 1)
            _box(ax, x, y, 1.65, 0.45, module, face="#FFFFFF", edge=BLUE if li == 0 else GREEN if li == len(layers) - 1 else PURPLE, fs=7.8)
            positions[module] = (x, y)
    arrows_drawn = 0
    for conn in spec.get("connections") or []:
        if not isinstance(conn, dict):
            continue
        src, dst = _short(conn.get("from"), 20), _short(conn.get("to"), 20)
        if src in positions and dst in positions:
            x1, y1 = positions[src]
            x2, y2 = positions[dst]
            _arrow(ax, x1, y1 - 0.25, x2, y2 + 0.25, color=PURPLE, label=_short(conn.get("label"), 10))
            arrows_drawn += 1
    if arrows_drawn == 0:
        for upper, lower in zip(layer_modules, layer_modules[1:]):
            if not upper or not lower:
                continue
            target = lower[0]
            for source in upper[:3]:
                x1, y1 = positions[source]
                x2, y2 = positions[target]
                _arrow(ax, x1, y1 - 0.25, x2, y2 + 0.25, color="#98A2B3")
    return f"architecture layers={len(layers)}", _finish(fig, output_path)


def generate_network_diagram(spec: dict[str, Any], output_path: Path, *, title: str = "") -> tuple[str, Path]:
    center = _short(spec.get("center") or spec.get("title") or "核心概念", 18)
    concepts = [_short(c, 18) for c in (spec.get("concepts") or []) if _short(c, 18)]
    if not concepts:
        return generate_structured_diagram(spec, output_path, title=title)
    relation_labels: dict[str, str] = {}
    for edge in spec.get("edges") or []:
        if not isinstance(edge, dict):
            continue
        label = _short(edge.get("label"), 12)
        if not label:
            continue
        target = str(edge.get("to") or edge.get("target") or "").strip()
        if target:
            relation_labels[target] = label
    fig, ax = plt.subplots(figsize=(8.5, 6.2), dpi=150)
    ax.set_xlim(0, 8.5)
    ax.set_ylim(0, 6.2)
    ax.axis("off")
    ax.set_title(wrap_text(title or spec.get("title") or "关系网络", max_units=28, max_lines=2), fontsize=12, fontweight="bold", color=INK)
    cx, cy = 4.25, 3.1
    _box(ax, cx, cy, 1.7, 0.6, center, face="#FFFFFF", edge=BLUE, bold=True)
    radius = 2.25
    for i, concept in enumerate(concepts[:10]):
        node_id = f"n{i}"
        angle = 2 * math.pi * i / min(len(concepts), 10)
        x, y = cx + math.cos(angle) * radius, cy + math.sin(angle) * radius
        _box(ax, x, y, 1.45, 0.46, concept, face=SOFT_BLUE, edge=BLUE, fs=7.8)
        _arrow(ax, cx, cy, x, y, color=BLUE, label=relation_labels.get(node_id) or relation_labels.get(concept, ""))
    return f"network concepts={len(concepts)}", _finish(fig, output_path)


def generate_infographic_diagram(spec: dict[str, Any], output_path: Path, *, title: str = "") -> tuple[str, Path]:
    blocks = [b for b in (spec.get("blocks") or []) if isinstance(b, dict)]
    if not blocks:
        return generate_structured_diagram(spec, output_path, title=title)
    cols = min(3, max(1, len(blocks)))
    rows = math.ceil(len(blocks) / cols)
    fig_w = max(8.5, cols * 2.6 + 1.0)
    fig_h = max(4.8, rows * 1.45 + 1.4)
    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis("off")
    ax.set_title(wrap_text(title or spec.get("title") or "信息图", max_units=28, max_lines=2), fontsize=12, fontweight="bold", color=INK)
    for i, block in enumerate(blocks):
        col, row = i % cols, i // cols
        x = fig_w * (col + 1) / (cols + 1)
        y = fig_h - 1.25 - row * 1.35
        _box(ax, x, y, 2.1, 0.76, _short(block.get("label"), 20), face=SOFT_BLUE, edge=BLUE, bold=True, icon=str(block.get("icon") or "node"))
        for j, item in enumerate(block.get("items") or []):
            ax.text(x, y - 0.52 - j * 0.25, "· " + _short(item, 18), ha="center", va="center", fontsize=7.4, color=INK)
    return f"infographic blocks={len(blocks)}", _finish(fig, output_path)
