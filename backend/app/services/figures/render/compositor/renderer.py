"""通用结构图 PNG 合成器。

本模块只枚举可穷尽的基础版式，不内置领域专用模板。
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

from app.services.figures.intent.taxonomy import canonical_subtype
from app.services.figures.render.result import FigureRenderResult

W = 1365
H = 900
MARGIN = 56
TITLE_H = 36
PLACEHOLDERS = tuple("甲乙丙丁戊己庚辛壬癸")
PALETTE = (
    ("#1D4ED8", "#EFF6FF", "#BFDBFE"),
    ("#15803D", "#F0FDF4", "#BBF7D0"),
    ("#C2410C", "#FFF7ED", "#FED7AA"),
    ("#6D28D9", "#F5F3FF", "#DDD6FE"),
    ("#0E7490", "#ECFEFF", "#A5F3FC"),
    ("#BE123C", "#FFF1F2", "#FECDD3"),
)
TEXT = "#111827"
MUTED = "#475569"
LINE = "#1F2937"


def render_composited_diagram(
    spec: dict[str, Any],
    out_path: Path,
    *,
    subtype: str = "",
    title: str = "",
) -> FigureRenderResult:
    st = canonical_subtype(subtype or str(spec.get("diagram_subtype") or ""))
    img = Image.new("RGB", (W, H), "#FFFFFF")
    draw = ImageDraw.Draw(img)
    fonts = _fonts()
    _ = title

    nodes = _nodes_from_spec(spec)
    edges = _edges_from_spec(spec, nodes)
    layout = _select_layout(st, spec, nodes, edges)

    if layout == "matrix":
        _draw_matrix(draw, spec, fonts)
    elif layout == "timeline":
        _draw_timeline(draw, spec, nodes, fonts)
    elif layout == "layers":
        _draw_layers(draw, spec, fonts)
    elif layout == "tree":
        _draw_tree(draw, nodes, edges, fonts)
    elif layout == "radial":
        _draw_radial(draw, nodes, edges, fonts)
    elif layout == "grid":
        _draw_grid(draw, nodes, fonts)
    elif layout == "linear_v":
        _draw_linear_vertical(draw, nodes, fonts)
    elif layout == "branch":
        _draw_branch(draw, nodes, edges, fonts)
    elif layout == "snake":
        _draw_snake(draw, nodes, fonts)
    else:
        _draw_linear_horizontal(draw, nodes, fonts)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="PNG")
    return FigureRenderResult(
        primary_png_path=out_path,
        optional_svg_path=None,
        render_source="generic.compositor",
        diagnostics={"layout": layout, "node_count": len(nodes), "edge_count": len(edges)},
    )


def _fonts() -> dict[str, ImageFont.FreeTypeFont | ImageFont.ImageFont]:
    candidates = (
        r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
        r"C:\Windows\Fonts\arial.ttf",
    )

    def load(size: int):
        for path in candidates:
            try:
                return ImageFont.truetype(path, size=size)
            except Exception:
                continue
        return ImageFont.load_default()

    return {
        "title": load(46),
        "h1": load(31),
        "h2": load(25),
        "body": load(21),
        "small": load(18),
        "tiny": load(15),
    }


def _label(item: Any, fallback: str = "") -> str:
    if isinstance(item, str):
        return item.strip()
    if not isinstance(item, dict):
        return fallback
    for key in ("label", "title", "name", "text", "id"):
        value = str(item.get(key) or "").strip()
        if value:
            return value
    return fallback


def _nodes_from_spec(spec: dict[str, Any]) -> list[dict[str, str]]:
    raw_nodes = spec.get("nodes")
    nodes: list[dict[str, str]] = []
    if isinstance(raw_nodes, list) and raw_nodes:
        for i, item in enumerate(raw_nodes):
            label = _label(item, _placeholder(i))
            nid = str(item.get("id") or label or f"n{i}") if isinstance(item, dict) else label
            nodes.append({"id": nid, "label": label or _placeholder(i)})
    if not nodes:
        for field in ("stages", "steps", "events", "blocks", "items", "groups", "sections", "cards"):
            values = spec.get(field)
            if isinstance(values, list) and values:
                for i, item in enumerate(values):
                    label = _label(item, _placeholder(i))
                    nodes.append({"id": f"{field}-{i}", "label": label or _placeholder(i)})
                break
    if not nodes:
        layers = spec.get("layers")
        if isinstance(layers, list):
            for i, item in enumerate(layers):
                label = _label(item, _placeholder(i))
                nodes.append({"id": f"layer-{i}", "label": label or _placeholder(i)})
    if not nodes:
        nodes = [{"id": f"n{i}", "label": _placeholder(i)} for i in range(3)]
    return nodes[:16]


def _edges_from_spec(spec: dict[str, Any], nodes: list[dict[str, str]]) -> list[dict[str, str]]:
    ids = [n["id"] for n in nodes]
    edges: list[dict[str, str]] = []
    raw_edges = spec.get("edges")
    if isinstance(raw_edges, list):
        for item in raw_edges:
            if not isinstance(item, dict):
                continue
            src = str(item.get("from") or item.get("source") or item.get("src") or "").strip()
            dst = str(item.get("to") or item.get("target") or item.get("dst") or "").strip()
            label = str(item.get("label") or "").strip()
            if src and dst:
                edges.append({"from": src, "to": dst, "label": label})
    if not edges and len(ids) >= 2:
        edges = [{"from": ids[i], "to": ids[i + 1], "label": ""} for i in range(len(ids) - 1)]
    return edges[:24]


def _select_layout(st: str, spec: dict[str, Any], nodes: list[dict[str, str]], edges: list[dict[str, str]]) -> str:
    if st == "comparison_matrix" or spec.get("columns") or spec.get("dimensions"):
        return "matrix"
    if st == "timeline_roadmap" or spec.get("events"):
        return "timeline"
    if st == "system_architecture" and spec.get("layers"):
        return "layers"
    if st in {"taxonomy_map", "decision_tree"}:
        return "tree"
    if st == "concept_diagram":
        return "radial"
    if st == "infographic":
        return "grid"
    if _has_branch(edges):
        return "branch"
    if st in {"process_flow", "mechanism_diagram"}:
        if len(nodes) <= 4 and not _has_long_label(nodes):
            return "linear_h"
        if len(nodes) <= 6 and _has_long_label(nodes):
            return "linear_v"
        return "snake"
    if len(nodes) > 6:
        return "grid"
    return "linear_h"


def _has_branch(edges: list[dict[str, str]]) -> bool:
    out: dict[str, int] = {}
    inc: dict[str, int] = {}
    for e in edges:
        out[e["from"]] = out.get(e["from"], 0) + 1
        inc[e["to"]] = inc.get(e["to"], 0) + 1
    return any(v > 1 for v in out.values()) or any(v > 1 for v in inc.values())


def _has_long_label(nodes: list[dict[str, str]]) -> bool:
    return any(_visual_len(n["label"]) > 9 for n in nodes)


def _placeholder(index: int) -> str:
    if index < len(PLACEHOLDERS):
        return PLACEHOLDERS[index]
    return f"项{index + 1}"


def _visual_len(text: str) -> float:
    total = 0.0
    for ch in str(text or ""):
        total += 1.0 if "\u4e00" <= ch <= "\u9fff" else 0.55
    return total


def _short_text(text: str, max_units: int) -> str:
    out = ""
    for ch in str(text or "").strip():
        if _visual_len(out + ch) > max_units:
            break
        out += ch
    return out.strip()


def _draw_title(draw: ImageDraw.ImageDraw, title: str, font) -> None:
    box = draw.textbbox((0, 0), title, font=font)
    draw.text(((W - (box[2] - box[0])) / 2, 30), title, fill=TEXT, font=font)


def _text_lines(text: str, max_units: int, max_lines: int = 3) -> list[str]:
    text = str(text or "").strip()
    if not text:
        return []
    lines: list[str] = []
    cur = ""
    for ch in text:
        if _visual_len(cur + ch) > max_units and cur:
            lines.append(cur)
            cur = ch
        else:
            cur += ch
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = _short_text(lines[-1], max_units - 1) + "…"
    return lines


def _draw_card(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], text: str, fonts, tone_index: int = 0) -> None:
    stroke, fill, _ = PALETTE[tone_index % len(PALETTE)]
    draw.rounded_rectangle(box, radius=20, fill=fill, outline=stroke, width=3)
    x1, y1, x2, y2 = box
    lines = _text_lines(text, max(5, int((x2 - x1) / 25)), 3)
    total_h = len(lines) * 31
    y = y1 + max(18, int((y2 - y1 - total_h) / 2))
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=fonts["h2"])
        draw.text((x1 + (x2 - x1 - (bb[2] - bb[0])) / 2, y), line, fill=TEXT, font=fonts["h2"])
        y += 31


def _arrow(draw: ImageDraw.ImageDraw, start: tuple[float, float], end: tuple[float, float], *, dashed: bool = False) -> None:
    if dashed:
        _dashed_line(draw, start, end, fill=LINE, width=3)
    else:
        draw.line([start, end], fill=LINE, width=3)
    angle = math.atan2(end[1] - start[1], end[0] - start[0])
    size = 14
    p1 = (end[0] - size * math.cos(angle - 0.45), end[1] - size * math.sin(angle - 0.45))
    p2 = (end[0] - size * math.cos(angle + 0.45), end[1] - size * math.sin(angle + 0.45))
    draw.polygon([end, p1, p2], fill=LINE)


def _arrow_between_boxes(draw: ImageDraw.ImageDraw, a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> None:
    ac = ((a[0] + a[2]) / 2, (a[1] + a[3]) / 2)
    bc = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    dx = bc[0] - ac[0]
    dy = bc[1] - ac[1]
    pad = 8
    if abs(dx) >= abs(dy):
        if dx >= 0:
            start = (a[2] + pad, ac[1])
            end = (b[0] - pad, bc[1])
        else:
            start = (a[0] - pad, ac[1])
            end = (b[2] + pad, bc[1])
    else:
        if dy >= 0:
            start = (ac[0], a[3] + pad)
            end = (bc[0], b[1] - pad)
        else:
            start = (ac[0], a[1] - pad)
            end = (bc[0], b[3] + pad)
    _arrow(draw, start, end)


def _dashed_line(draw: ImageDraw.ImageDraw, start, end, *, fill: str, width: int) -> None:
    x1, y1 = start
    x2, y2 = end
    dist = math.hypot(x2 - x1, y2 - y1)
    if dist <= 0:
        return
    dx = (x2 - x1) / dist
    dy = (y2 - y1) / dist
    dash = 14
    gap = 10
    pos = 0
    while pos < dist:
        a = pos
        b = min(pos + dash, dist)
        draw.line([(x1 + dx * a, y1 + dy * a), (x1 + dx * b, y1 + dy * b)], fill=fill, width=width)
        pos += dash + gap


def _draw_linear_horizontal(draw, nodes, fonts) -> None:
    n = len(nodes)
    card_w = min(245, int((W - MARGIN * 2 - (n - 1) * 44) / max(1, n)))
    card_h = 170
    gap = (W - MARGIN * 2 - n * card_w) / max(1, n - 1) if n > 1 else 0
    y = 340
    boxes = []
    for i, node in enumerate(nodes):
        x = int(MARGIN + i * (card_w + gap))
        box = (x, y, x + card_w, y + card_h)
        boxes.append(box)
        _draw_card(draw, box, node["label"], fonts, i)
    for a, b in zip(boxes, boxes[1:]):
        _arrow_between_boxes(draw, a, b)


def _draw_linear_vertical(draw, nodes, fonts) -> None:
    card_w = 420
    card_h = max(90, min(130, int((H - TITLE_H - 80) / max(1, len(nodes))) - 22))
    x = int((W - card_w) / 2)
    y = TITLE_H + 28
    boxes = []
    for i, node in enumerate(nodes):
        box = (x, y, x + card_w, y + card_h)
        boxes.append(box)
        _draw_card(draw, box, node["label"], fonts, i)
        y += card_h + 34
    for a, b in zip(boxes, boxes[1:]):
        _arrow_between_boxes(draw, a, b)


def _draw_snake(draw, nodes, fonts) -> None:
    rows = 2 if len(nodes) <= 8 else 3
    cols = math.ceil(len(nodes) / rows)
    card_w = min(275, int((W - MARGIN * 2 - (cols - 1) * 38) / cols))
    card_h = 150
    row_gap = 92
    start_y = TITLE_H + 120
    positions: list[tuple[int, int, int, int]] = []
    for i, node in enumerate(nodes):
        r = i // cols
        c0 = i % cols
        c = c0 if r % 2 == 0 else cols - 1 - c0
        x = int(MARGIN + c * (card_w + 38))
        y = int(start_y + r * (card_h + row_gap))
        box = (x, y, x + card_w, y + card_h)
        positions.append(box)
        _draw_card(draw, box, node["label"], fonts, i)
    for a, b in zip(positions, positions[1:]):
        _arrow_between_boxes(draw, a, b)


def _draw_branch(draw, nodes, edges, fonts) -> None:
    root = nodes[0]
    root_box = (int(W / 2 - 160), TITLE_H + 40, int(W / 2 + 160), TITLE_H + 170)
    _draw_card(draw, root_box, root["label"], fonts, 0)
    children = [e["to"] for e in edges if e["from"] == root["id"]]
    if not children:
        children = [n["id"] for n in nodes[1:]]
    child_nodes = [n for n in nodes if n["id"] in children] or nodes[1:]
    y = TITLE_H + 300
    card_w = min(290, int((W - MARGIN * 2 - max(0, len(child_nodes) - 1) * 42) / max(1, len(child_nodes))))
    boxes = []
    for i, node in enumerate(child_nodes):
        x = int(MARGIN + i * (card_w + 42))
        box = (x, y, x + card_w, y + 150)
        boxes.append(box)
        _draw_card(draw, box, node["label"], fonts, i + 1)
        _arrow(draw, ((root_box[0] + root_box[2]) / 2, root_box[3] + 5), ((box[0] + box[2]) / 2, box[1] - 5))
    rest = [n for n in nodes[1:] if n not in child_nodes]
    if rest:
        _draw_grid_at(draw, rest, fonts, y + 240, tone_offset=len(child_nodes) + 1)


def _draw_tree(draw, nodes, edges, fonts) -> None:
    levels = _levels(nodes, edges)
    y = TITLE_H + 40
    boxes_by_id: dict[str, tuple[int, int, int, int]] = {}
    for depth, level in enumerate(levels[:4]):
        card_w = min(250, int((W - MARGIN * 2 - max(0, len(level) - 1) * 34) / max(1, len(level))))
        card_h = 112
        gap = (W - MARGIN * 2 - len(level) * card_w) / max(1, len(level) - 1) if len(level) > 1 else 0
        for i, node in enumerate(level):
            x = int(MARGIN + i * (card_w + gap)) if len(level) > 1 else int((W - card_w) / 2)
            box = (x, y, x + card_w, y + card_h)
            boxes_by_id[node["id"]] = box
            _draw_card(draw, box, node["label"], fonts, depth + i)
        y += card_h + 76
    for edge in edges:
        a = boxes_by_id.get(edge["from"])
        b = boxes_by_id.get(edge["to"])
        if a and b:
            _arrow(draw, ((a[0] + a[2]) / 2, a[3] + 4), ((b[0] + b[2]) / 2, b[1] - 4))


def _levels(nodes, edges) -> list[list[dict[str, str]]]:
    by_id = {n["id"]: n for n in nodes}
    children: dict[str, list[str]] = {}
    incoming: set[str] = set()
    for e in edges:
        if e["from"] in by_id and e["to"] in by_id:
            children.setdefault(e["from"], []).append(e["to"])
            incoming.add(e["to"])
    roots = [n["id"] for n in nodes if n["id"] not in incoming] or [nodes[0]["id"]]
    out: list[list[dict[str, str]]] = []
    seen: set[str] = set()
    cur = roots
    while cur and len(out) < 4:
        level = [by_id[x] for x in cur if x in by_id and x not in seen]
        if level:
            out.append(level)
        seen.update(cur)
        nxt: list[str] = []
        for nid in cur:
            nxt.extend(children.get(nid, []))
        cur = [x for x in nxt if x not in seen]
    rest = [n for n in nodes if n["id"] not in seen]
    if rest:
        out.append(rest)
    return out or [nodes]


def _draw_radial(draw, nodes, edges, fonts) -> None:
    center = nodes[0]
    cx, cy = W / 2, H / 2 + 40
    center_box = (int(cx - 170), int(cy - 80), int(cx + 170), int(cy + 80))
    _draw_card(draw, center_box, center["label"], fonts, 0)
    others = nodes[1:]
    radius_x = 440
    radius_y = 265
    boxes: list[tuple[int, int, int, int]] = []
    for i, node in enumerate(others):
        angle = -math.pi / 2 + i * (2 * math.pi / max(1, len(others)))
        x = int(cx + radius_x * math.cos(angle) - 125)
        y = int(cy + radius_y * math.sin(angle) - 58)
        box = (x, y, x + 250, y + 116)
        boxes.append(box)
        _draw_card(draw, box, node["label"], fonts, i + 1)
        _arrow(draw, (cx, cy), ((box[0] + box[2]) / 2, (box[1] + box[3]) / 2))


def _draw_grid(draw, nodes, fonts) -> None:
    _draw_grid_at(draw, nodes, fonts, TITLE_H + 80)


def _draw_grid_at(draw, nodes, fonts, y_start: int, *, tone_offset: int = 0) -> None:
    cols = 3 if len(nodes) <= 6 else 4
    card_w = int((W - MARGIN * 2 - (cols - 1) * 34) / cols)
    card_h = 155
    for i, node in enumerate(nodes):
        r, c = divmod(i, cols)
        x = int(MARGIN + c * (card_w + 34))
        y = int(y_start + r * (card_h + 42))
        _draw_card(draw, (x, y, x + card_w, y + card_h), node["label"], fonts, i + tone_offset)


def _draw_layers(draw, spec, fonts) -> None:
    layers = spec.get("layers") if isinstance(spec.get("layers"), list) else []
    if not layers:
        _draw_linear_vertical(draw, _nodes_from_spec(spec), fonts)
        return
    band_h = int((H - TITLE_H - 80) / max(1, len(layers)))
    y = TITLE_H + 24
    for i, layer in enumerate(layers[:5]):
        stroke, fill, soft = PALETTE[i % len(PALETTE)]
        band = (MARGIN, y, W - MARGIN, y + band_h - 22)
        draw.rounded_rectangle(band, radius=22, fill=fill, outline=stroke, width=3)
        title = _label(layer, _placeholder(i))
        draw.text((band[0] + 22, band[1] + 18), _short_text(title, 18), fill=TEXT, font=fonts["h2"])
        modules = []
        if isinstance(layer, dict):
            modules = [str(x).strip() for x in (layer.get("modules") or layer.get("items") or []) if str(x).strip()]
        if not modules:
            modules = [_placeholder(0), _placeholder(1)]
        inner_x = band[0] + 250
        inner_w = band[2] - inner_x - 26
        visible_modules = modules[:4]
        card_w = min(245, int((inner_w - max(0, len(visible_modules) - 1) * 24) / max(1, len(visible_modules))))
        total_w = len(visible_modules) * card_w + max(0, len(visible_modules) - 1) * 24
        start_x = inner_x + max(0, int((inner_w - total_w) / 2))
        for j, module in enumerate(visible_modules):
            x = int(start_x + j * (card_w + 24))
            _draw_card(draw, (x, band[1] + 35, x + card_w, band[3] - 32), module, fonts, i + j)
        if i > 0:
            _arrow(draw, (W / 2, y - 20), (W / 2, y - 4))
        y += band_h


def _draw_timeline(draw, spec, nodes, fonts) -> None:
    events = spec.get("events") if isinstance(spec.get("events"), list) else []
    if events:
        nodes = [{"id": f"e{i}", "label": _label(e, _placeholder(i))} for i, e in enumerate(events[:8])]
    n = max(1, len(nodes))
    y = TITLE_H + 280
    x1, x2 = MARGIN + 40, W - MARGIN - 40
    draw.line([(x1, y), (x2, y)], fill=LINE, width=4)
    _arrow(draw, (x2 - 5, y), (x2 + 18, y))
    for i, node in enumerate(nodes):
        x = x1 + (x2 - x1) * i / max(1, n - 1)
        stroke, fill, _ = PALETTE[i % len(PALETTE)]
        draw.ellipse((x - 18, y - 18, x + 18, y + 18), fill="#FFFFFF", outline=stroke, width=5)
        label_y = y - 150 if i % 2 == 0 else y + 54
        box = (int(x - 130), int(label_y), int(x + 130), int(label_y + 110))
        _draw_card(draw, box, node["label"], fonts, i)
        if i % 2 == 0:
            _dashed_line(draw, (x, y - 20), (x, box[3] + 5), fill=stroke, width=2)
        else:
            _dashed_line(draw, (x, y + 20), (x, box[1] - 5), fill=stroke, width=2)


def _draw_matrix(draw, spec, fonts) -> None:
    cols = [str(x).strip() for x in (spec.get("columns") or []) if str(x).strip()]
    dims = [str(x).strip() for x in (spec.get("dimensions") or spec.get("rows") or []) if str(x).strip()]
    if not cols:
        cols = [_placeholder(0), _placeholder(1)]
    if not dims:
        dims = [_placeholder(i) for i in range(4)]
    cols = cols[:4]
    dims = dims[:6]
    table_x = MARGIN
    table_y = TITLE_H + 80
    table_w = W - MARGIN * 2
    row_h = 88
    head_h = 80
    label_w = 210
    col_w = int((table_w - label_w) / len(cols))
    draw.rounded_rectangle((table_x, table_y, table_x + table_w, table_y + head_h + row_h * len(dims)), radius=20, fill="#F8FAFC", outline="#CBD5E1", width=2)
    draw.rectangle((table_x, table_y, table_x + table_w, table_y + head_h), fill="#E2E8F0")
    for i, col in enumerate(cols):
        x = table_x + label_w + i * col_w
        draw.line([(x, table_y), (x, table_y + head_h + row_h * len(dims))], fill="#CBD5E1", width=2)
        _draw_cell_text(draw, (x, table_y, x + col_w, table_y + head_h), col, fonts["h2"], TEXT, max_lines=2)
    for r, dim in enumerate(dims):
        y = table_y + head_h + r * row_h
        fill = "#FFFFFF" if r % 2 == 0 else "#F8FAFC"
        draw.rectangle((table_x, y, table_x + table_w, y + row_h), fill=fill)
        draw.line([(table_x, y), (table_x + table_w, y)], fill="#CBD5E1", width=2)
        _draw_cell_text(draw, (table_x, y, table_x + label_w, y + row_h), dim, fonts["body"], TEXT, max_lines=2)
        for c in range(len(cols)):
            x = table_x + label_w + c * col_w
            text = _matrix_value(spec, r, c)
            _draw_cell_text(draw, (x, y, x + col_w, y + row_h), text, fonts["small"], MUTED, max_lines=2)


def _matrix_value(spec: dict[str, Any], row: int, col: int) -> str:
    values = spec.get("cells") or spec.get("matrix")
    if isinstance(values, list) and row < len(values):
        item = values[row]
        if isinstance(item, list) and col < len(item):
            return str(item[col] or "")
        if isinstance(item, dict):
            raw = item.get("values") or item.get("cells")
            if isinstance(raw, list) and col < len(raw):
                return str(raw[col] or "")
    return ""


def _draw_cell_text(draw, box, text, font, fill, *, max_lines: int) -> None:
    x1, y1, x2, y2 = box
    lines = _text_lines(text, max(5, int((x2 - x1 - 24) / 20)), max_lines)
    if not lines:
        lines = ["—"]
    total_h = len(lines) * 25
    y = y1 + max(8, int((y2 - y1 - total_h) / 2))
    for line in lines:
        bb = draw.textbbox((0, 0), line, font=font)
        draw.text((x1 + (x2 - x1 - (bb[2] - bb[0])) / 2, y), line, fill=fill, font=font)
        y += 25
