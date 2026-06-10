"""Dedicated SVG renderers for graph visual grammars."""

from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any

from app.services.figures.contracts.graph_visual_grammar import (
    GRAPH_GRAMMAR_ARCHITECTURE,
    GRAPH_GRAMMAR_DECISION_TREE,
    GRAPH_GRAMMAR_MECHANISM,
    GRAPH_GRAMMAR_NETWORK,
    GRAPH_GRAMMAR_PROCESS_FLOW,
    GRAPH_GRAMMAR_RADIAL_CONCEPT,
    mandatory_semantics_for_grammar,
)
from app.services.figures.contracts.visual_directives import visual_directive_ids
from app.services.figures.design.render_context import RenderContext, build_render_context
from app.services.figures.render.svg.export_png import export_png_from_svg
from app.services.figures.render.svg.markers import arrow_marker_def
from app.services.figures.render.svg.primitives import (
    database,
    diamond,
    label_background,
    queue_rail,
    rect,
    shadow_filter_def,
)
from app.services.figures.render.svg.text import multiline_text

_PALETTE = {
    "blue": "#DBEAFE",
    "blue_dark": "#2563EB",
    "teal": "#CCFBF1",
    "teal_dark": "#0F766E",
    "amber": "#FEF3C7",
    "amber_dark": "#B45309",
    "green": "#DCFCE7",
    "green_dark": "#15803D",
    "red": "#FEE2E2",
    "red_dark": "#B91C1C",
    "purple": "#EDE9FE",
    "purple_dark": "#6D28D9",
    "slate": "#F8FAFC",
    "slate_dark": "#334155",
}


def render_graph_grammar_svg(
    spec: dict[str, Any],
    out_path: Path,
    *,
    title: str = "",
    design_spec: dict[str, Any] | None = None,
) -> tuple[str, Path]:
    grammar = str(spec.get("graph_visual_grammar") or "")
    if grammar == GRAPH_GRAMMAR_PROCESS_FLOW:
        parts = _render_flow(spec, title=title, design_spec=design_spec)
    elif grammar == GRAPH_GRAMMAR_ARCHITECTURE:
        parts = _render_architecture(spec, title=title, design_spec=design_spec)
    elif grammar == GRAPH_GRAMMAR_MECHANISM:
        parts = _render_mechanism(spec, title=title, design_spec=design_spec)
    elif grammar == GRAPH_GRAMMAR_RADIAL_CONCEPT:
        parts = _render_radial_concept(spec, title=title, design_spec=design_spec)
    elif grammar == GRAPH_GRAMMAR_NETWORK:
        parts = _render_network(spec, title=title, design_spec=design_spec)
    elif grammar == GRAPH_GRAMMAR_DECISION_TREE:
        parts = _render_decision_tree(spec, title=title, design_spec=design_spec)
    else:
        raise ValueError(f"unsupported graph visual grammar: {grammar}")
    return _write_svg(parts, out_path)


def _ctx(spec: dict[str, Any], design_spec: dict[str, Any] | None) -> RenderContext:
    return build_render_context(design_spec or spec.get("design_spec"))


def _nodes(spec: dict[str, Any]) -> list[dict[str, Any]]:
    out = [n for n in (spec.get("nodes") or []) if isinstance(n, dict)]
    return out or [{"id": "n0", "label": spec.get("title") or "示意图", "kind": "process"}]


def _edges(spec: dict[str, Any]) -> list[dict[str, Any]]:
    return [e for e in (spec.get("edges") or []) if isinstance(e, dict)]


def _nid(node: dict[str, Any]) -> str:
    return str(node.get("id") or node.get("label") or "")


def _label(node: dict[str, Any]) -> str:
    return str(node.get("label") or node.get("name") or _nid(node) or "")


def _kind(node: dict[str, Any]) -> str:
    return str(node.get("kind") or node.get("type") or node.get("shape") or "process").lower()


def _title(spec: dict[str, Any], title: str) -> str:
    return title or str(spec.get("title") or "")


def _write_svg(parts: list[str], out_path: Path) -> tuple[str, Path]:
    svg_path = out_path.with_suffix(".svg")
    png_path = out_path.with_suffix(".png")
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text("\n".join(parts), encoding="utf-8")
    export_png_from_svg(svg_path, png_path)
    return "image/svg+xml", svg_path if svg_path.is_file() else png_path


def _svg_open(width: float, height: float, ctx: RenderContext, grammar: str, title: str, spec: dict[str, Any]) -> list[str]:
    semantics = spec.get("mandatory_semantics") or mandatory_semantics_for_grammar(grammar)
    escaped_semantics = html.escape(",".join(str(x) for x in semantics))
    directives = _directive_ids(spec)
    escaped_directives = html.escape(",".join(directives))
    parts = [
        (
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width:.0f}" height="{height:.0f}" '
            f'viewBox="0 0 {width:.0f} {height:.0f}" data-grammar="{grammar}" '
            f'data-mandatory-semantics="{escaped_semantics}" data-visual-directives="{escaped_directives}">'
        ),
        f'<rect width="100%" height="100%" fill="{ctx.tokens.background}"/>',
        "<defs>",
        shadow_filter_def(),
        arrow_marker_def("arrow", color=ctx.tokens.edge_stroke, size=ctx.tokens.arrow_size),
        arrow_marker_def("arrow-primary", color=ctx.tokens.primary, size=ctx.tokens.arrow_size),
        arrow_marker_def("arrow-forward", color=_PALETTE["blue_dark"], size=ctx.tokens.arrow_size),
        arrow_marker_def("arrow-reverse", color=_PALETTE["amber_dark"], size=ctx.tokens.arrow_size),
        "</defs>",
        f'<g class="mandatory-semantics" data-items="{escaped_semantics}"/>',
        f'<g class="visual-directives" data-items="{escaped_directives}"/>',
    ]
    if title:
        parts.append(
            multiline_text(width / 2, 28, title, fill=ctx.tokens.text, max_width=width - 96, font_size=17, max_lines=2)
        )
    return parts


def _directive_ids(spec: dict[str, Any]) -> list[str]:
    direct = [str(x) for x in (spec.get("directive_ids") or []) if str(x)]
    if direct:
        return direct
    return visual_directive_ids(spec.get("visual_directives") or [])


def _group(label: str, body: list[str], *, cls: str, attrs: str = "") -> str:
    data = f' data-label="{html.escape(label)}"' if label else ""
    attr_text = f" {attrs}" if attrs else ""
    return f'<g class="{cls}"{data}{attr_text}>\n' + "\n".join(body) + "\n</g>"


def _card(
    x: float,
    y: float,
    w: float,
    h: float,
    label: str,
    ctx: RenderContext,
    *,
    fill: str,
    stroke: str = "",
    cls: str = "semantic-card",
    font_size: int = 12,
    max_lines: int = 3,
) -> str:
    stroke = stroke or ctx.tokens.border
    body = [
        rect(x, y, w, h, fill=fill, stroke=stroke, rx=ctx.node_radius(), shadow=ctx.variant.node_shadow),
        multiline_text(x + w / 2, y + h / 2, label, fill=ctx.resolve_text_fill(fill), max_width=w - 18, font_size=font_size, max_lines=max_lines),
    ]
    return _group(label, body, cls=cls)


def _pill(x: float, y: float, w: float, h: float, label: str, ctx: RenderContext, *, cls: str, fill: str) -> str:
    body = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{h/2:.1f}" fill="{fill}" stroke="{ctx.tokens.border}" stroke-width="1.5" filter="url(#shadow)"/>',
        multiline_text(x + w / 2, y + h / 2, label, fill=ctx.resolve_text_fill(fill), max_width=w - 18, font_size=12, max_lines=2),
    ]
    return _group(label, body, cls=cls)


def _diamond_node(cx: float, cy: float, w: float, h: float, label: str, ctx: RenderContext, *, cls: str) -> str:
    body = [
        diamond(cx, cy, w, h, fill=ctx.tokens.decision_fill, stroke=_PALETTE["amber_dark"], shadow=True),
        multiline_text(cx, cy, label, fill=ctx.tokens.text, max_width=w * 0.62, font_size=12, max_lines=3),
    ]
    return _group(label, body, cls=cls)


def _edge_path(points: list[tuple[float, float]], ctx: RenderContext, *, cls: str, label: str = "", dashed: bool = False, primary: bool = False) -> str:
    if len(points) < 2:
        return ""
    stroke = ctx.tokens.primary if primary else ctx.tokens.edge_stroke
    marker = "arrow-primary" if primary else "arrow"
    dash = ' stroke-dasharray="6 4"' if dashed else ""
    path = " ".join(("M" if i == 0 else "L") + f" {x:.1f} {y:.1f}" for i, (x, y) in enumerate(points))
    body = [
        f'<path class="{cls}-path" d="{path}" fill="none" stroke="{stroke}" stroke-width="{ctx.edge_width():.1f}"{dash} marker-end="url(#{marker})"/>'
    ]
    if label:
        mx = sum(x for x, _ in points) / len(points)
        my = sum(y for _, y in points) / len(points)
        body.append(label_background(mx, my, min(120, max(36, len(label) * 10))))
        body.append(
            multiline_text(mx, my, label, fill=ctx.tokens.text, max_width=110, font_size=11, max_lines=1)
        )
    return _group(label, body, cls=cls)


def _node_fill(kind: str, index: int = 0) -> str:
    if "decision" in kind:
        return _PALETTE["amber"]
    if "database" in kind or "store" in kind or "data" in kind:
        return _PALETTE["purple"]
    if "queue" in kind or "bus" in kind:
        return _PALETTE["teal"]
    colors = [_PALETTE["blue"], _PALETTE["teal"], _PALETTE["green"], _PALETTE["purple"], _PALETTE["amber"]]
    return colors[index % len(colors)]


def _render_flow(spec: dict[str, Any], *, title: str, design_spec: dict[str, Any] | None) -> list[str]:
    ctx = _ctx(spec, design_spec)
    nodes = _nodes(spec)
    edges = _edges(spec)
    width = 980.0
    top = 76.0
    gap = 96.0
    node_w, node_h = 176.0, 58.0
    height = max(520.0, top + (len(nodes) + 2) * gap + 72.0)
    cx = width / 2
    positions: dict[str, tuple[float, float]] = {}
    parts = _svg_open(width, height, ctx, GRAPH_GRAMMAR_PROCESS_FLOW, _title(spec, title), spec)
    parts.append('<g class="flow-backbone">')
    parts.append(f'<line class="main-spine" x1="{cx:.1f}" y1="{top + 20:.1f}" x2="{cx:.1f}" y2="{height - 118:.1f}" stroke="{ctx.tokens.primary}" stroke-width="2.5" stroke-linecap="round"/>')

    parts.append(_pill(cx - 76, top, 152, 44, "开始", ctx, cls="start-end-node start-node", fill=_PALETTE["green"]))
    prev_bottom = top + 44
    for i, node in enumerate(nodes):
        y = top + (i + 1) * gap
        positions[_nid(node)] = (cx, y + node_h / 2)
        kind = _kind(node)
        parts.append(_edge_path([(cx, prev_bottom), (cx, y)], ctx, cls="main-spine", primary=True))
        if "decision" in kind or node.get("shape") == "diamond":
            parts.append(_diamond_node(cx, y + node_h / 2, 156, 74, _label(node), ctx, cls="decision-diamond flow-node"))
        elif "start" in kind or "end" in kind:
            parts.append(_pill(cx - node_w / 2, y, node_w, 48, _label(node), ctx, cls="start-end-node flow-node", fill=_PALETTE["green"]))
        else:
            parts.append(_card(cx - node_w / 2, y, node_w, node_h, _label(node), ctx, fill=_node_fill(kind, i), cls="flow-step-node flow-node"))
        prev_bottom = y + node_h
    parts.append(_edge_path([(cx, prev_bottom), (cx, height - 136)], ctx, cls="main-spine", primary=True))
    parts.append(_pill(cx - 76, height - 136, 152, 44, "结束", ctx, cls="start-end-node end-node", fill=_PALETTE["green"]))
    parts.append("</g>")

    node_order = {_nid(node): i for i, node in enumerate(nodes)}
    side_y = top + gap * 1.2
    for i, edge in enumerate(edges):
        src = str(edge.get("source") or edge.get("from") or "")
        tgt = str(edge.get("target") or edge.get("to") or "")
        label = str(edge.get("label") or "")
        if src not in positions or tgt not in positions:
            continue
        si, ti = node_order.get(src, 0), node_order.get(tgt, 0)
        if ti == si + 1 and not label:
            continue
        sx, sy = positions[src]
        tx, ty = positions[tgt]
        if ti < si:
            lane_x = 170.0 + (i % 2) * 42
            parts.append(
                _edge_path(
                    [(sx - 78, sy), (lane_x, sy), (lane_x, ty), (tx - 78, ty)],
                    ctx,
                    cls="loop-optional-parallel loop-edge",
                    label=label or "回路",
                    dashed=True,
                )
            )
        else:
            lane_x = 800.0 - (i % 2) * 42
            cls = "branch-label branch-edge"
            if label:
                cls += " yes-no-path" if label in {"是", "否", "Y", "N", "yes", "no"} else ""
            parts.append(_edge_path([(sx + 78, sy), (lane_x, sy), (lane_x, ty), (tx + 78, ty)], ctx, cls=cls, label=label or "分支", dashed=bool(label)))
    legend = [
        rect(48, side_y, 154, 72, fill="#FFFFFF", stroke=ctx.tokens.border, rx=8),
        multiline_text(125, side_y + 18, "分支/循环/并行", fill=ctx.tokens.muted, max_width=130, font_size=11, max_lines=1),
        f'<line x1="76" y1="{side_y + 42:.1f}" x2="174" y2="{side_y + 42:.1f}" stroke="{ctx.tokens.edge_stroke}" stroke-width="1.5" stroke-dasharray="6 4" marker-end="url(#arrow)"/>',
    ]
    parts.append(_group("loop_optional_parallel", legend, cls="loop-optional-parallel parallel-semantics branch-label"))
    parts.append("</svg>")
    return parts


def _render_architecture(spec: dict[str, Any], *, title: str, design_spec: dict[str, Any] | None) -> list[str]:
    ctx = _ctx(spec, design_spec)
    nodes = _nodes(spec)
    edges = _edges(spec)
    if "layout.columns" in _directive_ids(spec):
        return _render_architecture_dual_column(spec, ctx, nodes, edges, title=title)
    groups = [g for g in (spec.get("groups") or []) if isinstance(g, dict)]
    if not groups:
        labels = ["入口层", "服务层", "数据与基础设施层"]
        groups = [{"label": label, "members": []} for label in labels]
    width = 1120.0
    band_h = 150.0
    top = 72.0
    height = top + max(3, len(groups)) * band_h + 72.0
    parts = _svg_open(width, height, ctx, GRAPH_GRAMMAR_ARCHITECTURE, _title(spec, title), spec)
    assigned: set[str] = set()
    group_members: list[tuple[str, list[dict[str, Any]]]] = []
    by_id = {_nid(n): n for n in nodes}
    for gi, group in enumerate(groups):
        member_ids = [str(x) for x in (group.get("members") or group.get("nodes") or [])]
        members = [by_id[mid] for mid in member_ids if mid in by_id]
        for mid in member_ids:
            assigned.add(mid)
        group_members.append((str(group.get("label") or f"区域{gi + 1}"), members))
    leftovers = [n for n in nodes if _nid(n) not in assigned]
    if leftovers:
        for i, node in enumerate(leftovers):
            group_members[i % len(group_members)][1].append(node)

    positions: dict[str, tuple[float, float]] = {}
    colors = [_PALETTE["blue"], _PALETTE["teal"], _PALETTE["slate"], _PALETTE["purple"]]
    for gi, (label, members) in enumerate(group_members):
        y = top + gi * band_h
        fill = colors[gi % len(colors)]
        body = [
            rect(56, y, width - 112, band_h - 22, fill=fill, stroke=ctx.tokens.border, rx=14),
            f'<text class="layer-title" x="78" y="{y + 28:.1f}" fill="{ctx.tokens.text}" font-size="13" font-weight="bold">{html.escape(label)}</text>',
        ]
        parts.append(_group(label, body, cls="architecture-zone layer-group"))
        count = max(1, len(members))
        card_w = min(170.0, (width - 240) / count - 16)
        for mi, node in enumerate(members):
            x = 122 + mi * ((width - 244) / count)
            cy = y + band_h / 2 + 18
            kind = _kind(node)
            positions[_nid(node)] = (x + card_w / 2, cy)
            if "database" in kind or "store" in kind or "vector" in _label(node).lower() or "库" in _label(node):
                body = [
                    database(x + card_w / 2, cy, card_w, 64, fill=_PALETTE["purple"], stroke=ctx.tokens.border),
                    multiline_text(x + card_w / 2, cy + 6, _label(node), fill=ctx.tokens.text, max_width=card_w - 18, font_size=12, max_lines=2),
                ]
                parts.append(_group(_label(node), body, cls="data-store-shape architecture-component"))
            elif "queue" in kind or "bus" in kind or "消息" in _label(node) or "队列" in _label(node):
                body = [
                    queue_rail(x, cy - 30, card_w, 60, fill=_PALETTE["teal"], stroke=ctx.tokens.border),
                    multiline_text(x + card_w / 2, cy, _label(node), fill=ctx.tokens.text, max_width=card_w - 18, font_size=12, max_lines=2),
                ]
                parts.append(_group(_label(node), body, cls="queue-shape architecture-component"))
            else:
                parts.append(_card(x, cy - 32, card_w, 64, _label(node), ctx, fill="#FFFFFF", cls="component-card architecture-component"))
    for edge in edges:
        src = str(edge.get("source") or edge.get("from") or "")
        tgt = str(edge.get("target") or edge.get("to") or "")
        if src not in positions or tgt not in positions:
            continue
        sx, sy = positions[src]
        tx, ty = positions[tgt]
        mid_y = (sy + ty) / 2
        parts.append(
            _edge_path(
                [(sx, sy + 34), (sx, mid_y), (tx, mid_y), (tx, ty - 34)],
                ctx,
                cls="orthogonal-cross-layer-edge architecture-edge",
                label=str(edge.get("label") or ""),
            )
        )
    parts.append("</svg>")
    return parts


def _render_architecture_dual_column(
    spec: dict[str, Any],
    ctx: RenderContext,
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    *,
    title: str,
) -> list[str]:
    width, height = 1120.0, 680.0
    parts = _svg_open(width, height, ctx, GRAPH_GRAMMAR_ARCHITECTURE, _title(spec, title), spec)
    left, right, shared = _partition_architecture_nodes(nodes)
    zones = [
        ("左侧处理链路", "left-column-zone", 58.0, 94.0, 424.0, 430.0, _PALETTE["blue"]),
        ("右侧查询链路", "right-column-zone", 638.0, 94.0, 424.0, 430.0, _PALETTE["teal"]),
        ("共享资源", "shared-resource-zone", 390.0, 548.0, 340.0, 86.0, _PALETTE["purple"]),
    ]
    for label, cls, x, y, w, h, fill in zones:
        body = [
            rect(x, y, w, h, fill=fill, stroke=ctx.tokens.border, rx=16),
            f'<text class="layer-title" x="{x + 18:.1f}" y="{y + 30:.1f}" fill="{ctx.tokens.text}" font-size="13" font-weight="bold">{html.escape(label)}</text>',
        ]
        parts.append(_group(label, body, cls=f"architecture-zone layer-group {cls}"))

    positions: dict[str, tuple[float, float]] = {}
    for bucket, items, x0, y0 in (
        ("left", left, 106.0, 154.0),
        ("right", right, 686.0, 154.0),
    ):
        for i, node in enumerate(items[:8]):
            row = i % 4
            col = i // 4
            x = x0 + col * 188.0
            y = y0 + row * 78.0
            positions[_nid(node)] = (x + 150.0 / 2, y + 58.0 / 2)
            parts.append(
                _card(
                    x,
                    y,
                    150.0,
                    58.0,
                    _label(node),
                    ctx,
                    fill="#FFFFFF",
                    cls=f"component-card architecture-component {bucket}-column-component",
                    font_size=11,
                )
            )
    if not shared and nodes:
        shared = [nodes[-1]]
    for i, node in enumerate(shared[:2]):
        x = 430.0 + i * 148.0
        y = 566.0
        positions[_nid(node)] = (x + 120.0 / 2, y + 52.0 / 2)
        kind = _kind(node)
        body = [
            database(x + 60.0, y + 26.0, 120.0, 52.0, fill=_PALETTE["purple"], stroke=ctx.tokens.border)
            if "database" in kind or "data" in kind or "库" in _label(node) or "向量" in _label(node)
            else rect(x, y, 120.0, 52.0, fill=_PALETTE["purple"], stroke=ctx.tokens.border, rx=8),
            multiline_text(x + 60.0, y + 30.0, _label(node), fill=ctx.tokens.text, max_width=104, font_size=11, max_lines=2),
        ]
        parts.append(_group(_label(node), body, cls="shared-resource-node data-store-shape architecture-component"))

    shared_ids = {_nid(n) for n in shared}
    for edge in edges:
        src = str(edge.get("source") or edge.get("from") or "")
        tgt = str(edge.get("target") or edge.get("to") or "")
        if src not in positions or tgt not in positions:
            continue
        sx, sy = positions[src]
        tx, ty = positions[tgt]
        via_y = max(sy, ty) + 28 if (src in shared_ids or tgt in shared_ids) else (sy + ty) / 2
        parts.append(
            _edge_path(
                [(sx, sy), (sx, via_y), (tx, via_y), (tx, ty)],
                ctx,
                cls="orthogonal-cross-layer-edge architecture-edge two-column-shared-route",
                label=str(edge.get("label") or ""),
                dashed=src in shared_ids or tgt in shared_ids,
            )
        )
    parts.append('<g class="two-column-shared-node shared-center-node no-unrelated-crossing"/>')
    parts.append("</svg>")
    return parts


def _partition_architecture_nodes(nodes: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    left: list[dict[str, Any]] = []
    right: list[dict[str, Any]] = []
    shared: list[dict[str, Any]] = []
    for node in nodes:
        label = _label(node)
        low = label.lower()
        if any(k in label for k in ("共享", "向量", "数据库", "数据湖", "缓存")) or any(k in low for k in ("vector", "db", "postgres", "redis")):
            shared.append(node)
        elif any(k in label for k in ("文档", "预处理", "解析", "分块", "嵌入", "导入")):
            left.append(node)
        elif any(k in label for k in ("查询", "检索", "重排序", "生成", "用户", "LLM")) or any(k in low for k in ("query", "rerank", "llm")):
            right.append(node)
        elif len(left) <= len(right):
            left.append(node)
        else:
            right.append(node)
    return left, right, shared


def _render_mechanism(spec: dict[str, Any], *, title: str, design_spec: dict[str, Any] | None) -> list[str]:
    ctx = _ctx(spec, design_spec)
    nodes = _nodes(spec)
    edges = _edges(spec)
    directive_ids = set(_directive_ids(spec))
    width, height = 1100.0, 620.0
    parts = _svg_open(width, height, ctx, GRAPH_GRAMMAR_MECHANISM, _title(spec, title), spec)
    stages = [
        ("输入", "input", 72.0, 170.0, _PALETTE["blue"]),
        ("操作 / 转换", "operation", 312.0, 476.0, _PALETTE["purple"]),
        ("状态 / 输出", "output", 788.0, 240.0, _PALETTE["green"]),
    ]
    for label, cls, x, w, fill in stages:
        body = [
            rect(x, 86, w, 382, fill=fill, stroke=ctx.tokens.border, rx=16),
            f'<text class="stage-title" x="{x + 18:.1f}" y="116" fill="{ctx.tokens.text}" font-size="13" font-weight="bold">{label}</text>',
        ]
        parts.append(_group(label, body, cls=f"stage-band {cls}-stage"))

    buckets = {"input": [], "operation": [], "output": []}
    for i, node in enumerate(nodes):
        text = _label(node)
        kind = _kind(node)
        lowered = text.lower()
        if any(k in lowered or k in text for k in ("input", "输入", "query", "prompt", "数据")):
            buckets["input"].append(node)
        elif any(k in lowered or k in text for k in ("output", "输出", "结果", "概率", "response")):
            buckets["output"].append(node)
        elif "state" in kind or "状态" in text:
            buckets["output"].append(node)
        else:
            buckets["operation"].append(node)
    if not buckets["input"] and nodes:
        buckets["input"].append(nodes[0])
    if not buckets["output"] and len(nodes) > 1:
        buckets["output"].append(nodes[-1])
    buckets["operation"] = [n for n in nodes if n not in buckets["input"] and n not in buckets["output"]] or buckets["operation"]

    positions: dict[str, tuple[float, float]] = {}
    for bucket, x, w in (("input", 98.0, 118.0), ("operation", 350.0, 130.0), ("output", 824.0, 142.0)):
        items = buckets[bucket]
        for i, node in enumerate(items[:8]):
            col = i % (3 if bucket == "operation" else 1)
            row = i // (3 if bucket == "operation" else 1)
            nx = x + col * 142
            ny = 148 + row * 88
            positions[_nid(node)] = (nx + w / 2, ny + 30)
            cls = f"{bucket}-role mechanism-node"
            kind = _kind(node)
            fill = _node_fill(kind, i)
            if bucket == "operation":
                parts.append(_card(nx, ny, w, 60, _label(node), ctx, fill=fill, cls=f"operation-node tensor-operation-shape {cls}", font_size=11))
            elif bucket == "input":
                parts.append(_pill(nx, ny, w, 52, _label(node), ctx, cls=f"input-node tensor-operation-shape {cls}", fill=fill))
            else:
                parts.append(_card(nx, ny, w, 60, _label(node), ctx, fill=fill, cls=f"output-state-node tensor-operation-shape {cls}", font_size=11))

    for edge in edges:
        src = str(edge.get("source") or edge.get("from") or "")
        tgt = str(edge.get("target") or edge.get("to") or "")
        if src in positions and tgt in positions:
            sx, sy = positions[src]
            tx, ty = positions[tgt]
            dashed = str(edge.get("style") or "") == "dashed" or "反馈" in str(edge.get("label") or "")
            cls = "feedback-lane feedback-edge" if dashed or ty < sy else "transformation-arrow mechanism-edge"
            parts.append(_edge_path([(sx, sy), ((sx + tx) / 2, sy), ((sx + tx) / 2, ty), (tx, ty)], ctx, cls=cls, label=str(edge.get("label") or ""), dashed=dashed, primary=not dashed))
    if "edge.bidirectional" in directive_ids:
        parts.append(_group("forward_reverse", [
            f'<path class="forward-arrow bidirectional-color-arrows" d="M 150 574 C 380 600, 720 600, 950 574" fill="none" stroke="{_PALETTE["blue_dark"]}" stroke-width="2.4" marker-end="url(#arrow-forward)"/>',
            f'<path class="reverse-arrow bidirectional-color-arrows" d="M 950 590 C 720 612, 380 612, 150 590" fill="none" stroke="{_PALETTE["amber_dark"]}" stroke-width="2.4" marker-end="url(#arrow-reverse)"/>',
            multiline_text(260, 568, "前向", fill=_PALETTE["blue_dark"], max_width=80, font_size=11, max_lines=1),
            multiline_text(840, 596, "反向", fill=_PALETTE["amber_dark"], max_width=80, font_size=11, max_lines=1),
        ], cls="bidirectional-color-arrows forward-reverse-lanes"))
    if {"semantic.qkv", "notation.matrix", "layout.encoder_decoder", "layout.stack"} & directive_ids:
        parts.append(
            f'<g class="mechanism-directive-markers {" ".join(html.escape(d) for d in sorted(directive_ids))}" '
            f'data-qkv="{str("semantic.qkv" in directive_ids).lower()}" '
            f'data-matrix="{str("notation.matrix" in directive_ids).lower()}" '
            f'data-encoder-decoder="{str("layout.encoder_decoder" in directive_ids).lower()}" '
            f'data-stacked="{str("layout.stack" in directive_ids).lower()}"/>'
        )
    parts.append(_group("feedback", [
        rect(72, 500, width - 144, 52, fill="#FFFFFF", stroke=ctx.tokens.border, rx=12),
        f'<path class="feedback-lane-path" d="M 160 526 C 360 582, 710 582, 920 526" fill="none" stroke="{_PALETTE["amber_dark"]}" stroke-width="1.5" stroke-dasharray="7 5" marker-end="url(#arrow)"/>',
        multiline_text(width / 2, 526, "反馈 / 校正通道", fill=ctx.tokens.muted, max_width=180, font_size=11, max_lines=1),
    ], cls="feedback-lane"))
    parts.append("</svg>")
    return parts


def _render_radial_concept(spec: dict[str, Any], *, title: str, design_spec: dict[str, Any] | None) -> list[str]:
    ctx = _ctx(spec, design_spec)
    nodes = _nodes(spec)
    edges = _edges(spec)
    width, height = 920.0, 700.0
    cx, cy = width / 2, height / 2 + 20
    parts = _svg_open(width, height, ctx, GRAPH_GRAMMAR_RADIAL_CONCEPT, _title(spec, title), spec)
    center = nodes[0]
    satellites = nodes[1:] or nodes[:1]
    radius = min(250.0, 120 + len(satellites) * 16)
    parts.append(f'<circle class="radial-ring" cx="{cx:.1f}" cy="{cy:.1f}" r="{radius:.1f}" fill="none" stroke="{ctx.tokens.border}" stroke-width="1" stroke-dasharray="5 5"/>')
    positions: dict[str, tuple[float, float]] = {_nid(center): (cx, cy)}
    for i, node in enumerate(satellites):
        angle = -math.pi / 2 + 2 * math.pi * i / max(1, len(satellites))
        x = cx + math.cos(angle) * radius
        y = cy + math.sin(angle) * radius
        positions[_nid(node)] = (x, y)
        parts.append(_edge_path([(cx, cy), (x, y)], ctx, cls="radial-link relationship-label", label=_edge_label(edges, _nid(center), _nid(node)), primary=True))
        parts.append(_card(x - 70, y - 32, 140, 64, _label(node), ctx, fill=_node_fill(_kind(node), i), cls="satellite-node radial-satellite", font_size=11))
    parts.append(_card(cx - 92, cy - 44, 184, 88, _label(center), ctx, fill=_PALETTE["blue"], stroke=ctx.tokens.primary, cls="center-node radial-center", font_size=14))
    for edge in edges:
        src = str(edge.get("source") or edge.get("from") or "")
        tgt = str(edge.get("target") or edge.get("to") or "")
        if src == _nid(center) or tgt == _nid(center) or src not in positions or tgt not in positions:
            continue
        sx, sy = positions[src]
        tx, ty = positions[tgt]
        parts.append(_edge_path([(sx, sy), ((sx + tx) / 2, (sy + ty) / 2 - 36), (tx, ty)], ctx, cls="radial-link cross-link relationship-label", label=str(edge.get("label") or ""), dashed=True))
    parts.append('<g class="non-linear-layout radial-layout"/>')
    parts.append("</svg>")
    return parts


def _render_network(spec: dict[str, Any], *, title: str, design_spec: dict[str, Any] | None) -> list[str]:
    ctx = _ctx(spec, design_spec)
    nodes = _nodes(spec)
    edges = _edges(spec)
    width, height = 1040.0, 720.0
    parts = _svg_open(width, height, ctx, GRAPH_GRAMMAR_NETWORK, _title(spec, title), spec)
    degree = { _nid(n): 0 for n in nodes }
    for edge in edges:
        src = str(edge.get("source") or edge.get("from") or "")
        tgt = str(edge.get("target") or edge.get("to") or "")
        degree[src] = degree.get(src, 0) + 1
        degree[tgt] = degree.get(tgt, 0) + 1
    hub = max(nodes, key=lambda n: degree.get(_nid(n), 0))
    rest = [n for n in nodes if n is not hub]
    groups: dict[str, list[dict[str, Any]]] = {}
    for node in rest:
        groups.setdefault(str(node.get("group") or _kind(node) or "concept"), []).append(node)
    positions = {_nid(hub): (width / 2, height / 2)}
    group_items = list(groups.items()) or [("concept", rest)]
    cluster_radius = 248.0
    for gi, (group, members) in enumerate(group_items):
        angle = -math.pi / 2 + 2 * math.pi * gi / max(1, len(group_items))
        gx = width / 2 + math.cos(angle) * cluster_radius
        gy = height / 2 + math.sin(angle) * cluster_radius
        parts.append(_group(group, [
            f'<circle class="typed-cluster-bg" cx="{gx:.1f}" cy="{gy:.1f}" r="112" fill="{[_PALETTE["blue"], _PALETTE["teal"], _PALETTE["purple"], _PALETTE["green"]][gi % 4]}" opacity="0.28" stroke="{ctx.tokens.border}" stroke-width="1"/>',
            multiline_text(gx, gy - 90, group, fill=ctx.tokens.muted, max_width=150, font_size=11, max_lines=1),
        ], cls="typed-cluster"))
        for mi, node in enumerate(members):
            local = -math.pi / 2 + 2 * math.pi * mi / max(1, len(members))
            x = gx + math.cos(local) * 58
            y = gy + math.sin(local) * 58
            positions[_nid(node)] = (x, y)
    for edge in edges:
        src = str(edge.get("source") or edge.get("from") or "")
        tgt = str(edge.get("target") or edge.get("to") or "")
        if src in positions and tgt in positions:
            sx, sy = positions[src]
            tx, ty = positions[tgt]
            cx = (sx + tx) / 2 + (ty - sy) * 0.08
            cy = (sy + ty) / 2 - (tx - sx) * 0.08
            parts.append(_edge_path([(sx, sy), (cx, cy), (tx, ty)], ctx, cls="relationship-edge-label network-edge", label=str(edge.get("label") or ""), dashed=str(edge.get("style") or "") == "dashed"))
    for i, node in enumerate(rest):
        x, y = positions[_nid(node)]
        kind = _kind(node)
        parts.append(_card(x - 62, y - 28, 124, 56, _label(node), ctx, fill=_node_fill(kind, i), cls=f"network-node node-type-{html.escape(kind)} node-type-encoding", font_size=11))
    hx, hy = positions[_nid(hub)]
    parts.append(_card(hx - 92, hy - 42, 184, 84, _label(hub), ctx, fill=_PALETTE["amber"], stroke=_PALETTE["amber_dark"], cls="hub-emphasis network-hub", font_size=14))
    parts.append('<g class="network-layout non-tree-layout"/>')
    parts.append("</svg>")
    return parts


def _render_decision_tree(spec: dict[str, Any], *, title: str, design_spec: dict[str, Any] | None) -> list[str]:
    ctx = _ctx(spec, design_spec)
    nodes = _nodes(spec)
    edges = _edges(spec)
    by_id = {_nid(n): n for n in nodes}
    incoming = {nid: 0 for nid in by_id}
    children: dict[str, list[tuple[str, str]]] = {nid: [] for nid in by_id}
    for edge in edges:
        src = str(edge.get("source") or edge.get("from") or "")
        tgt = str(edge.get("target") or edge.get("to") or "")
        if src in by_id and tgt in by_id:
            incoming[tgt] = incoming.get(tgt, 0) + 1
            children.setdefault(src, []).append((tgt, str(edge.get("label") or "")))
    roots = [nid for nid, count in incoming.items() if count == 0] or [_nid(nodes[0])]
    levels: list[list[str]] = []
    seen: set[str] = set()
    frontier = roots[:1]
    while frontier:
        levels.append(frontier)
        next_frontier: list[str] = []
        for nid in frontier:
            seen.add(nid)
            for tgt, _ in children.get(nid, []):
                if tgt not in seen and tgt not in next_frontier:
                    next_frontier.append(tgt)
        frontier = next_frontier
    leftovers = [nid for nid in by_id if nid not in seen]
    if leftovers:
        levels.append(leftovers)
    width = max(880.0, max(len(level) for level in levels) * 210.0 + 120.0)
    height = max(560.0, len(levels) * 126.0 + 150.0)
    parts = _svg_open(width, height, ctx, GRAPH_GRAMMAR_DECISION_TREE, _title(spec, title), spec)
    positions: dict[str, tuple[float, float]] = {}
    for li, level in enumerate(levels):
        y = 96.0 + li * 122.0
        step = width / (len(level) + 1)
        for i, nid in enumerate(level):
            positions[nid] = (step * (i + 1), y)
    for edge in edges:
        src = str(edge.get("source") or edge.get("from") or "")
        tgt = str(edge.get("target") or edge.get("to") or "")
        label = str(edge.get("label") or "")
        if src in positions and tgt in positions:
            sx, sy = positions[src]
            tx, ty = positions[tgt]
            parts.append(_edge_path([(sx, sy + 40), (sx, (sy + ty) / 2), (tx, (sy + ty) / 2), (tx, ty - 38)], ctx, cls="branch-label yes-no-path decision-tree-edge", label=label or "分支", primary=True))
    for nid, (x, y) in positions.items():
        node = by_id[nid]
        is_decision = "decision" in _kind(node) or node.get("shape") == "diamond" or children.get(nid)
        if is_decision:
            parts.append(_diamond_node(x, y, 160, 78, _label(node), ctx, cls="condition-diamond decision-node"))
        else:
            parts.append(_card(x - 78, y - 32, 156, 64, _label(node), ctx, fill=_PALETTE["green"], cls="outcome-leaf-node decision-leaf", font_size=12))
    parts.append('<g class="top-down-tree no-floating-leaves"/>')
    parts.append("</svg>")
    return parts


def _edge_label(edges: list[dict[str, Any]], src: str, tgt: str) -> str:
    for edge in edges:
        es = str(edge.get("source") or edge.get("from") or "")
        et = str(edge.get("target") or edge.get("to") or "")
        if es == src and et == tgt:
            return str(edge.get("label") or "")
    return ""
