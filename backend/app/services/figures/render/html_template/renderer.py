"""Template SVG renderer for DiagramSpec."""

from __future__ import annotations

import html
import math
from pathlib import Path
from typing import Any

from app.services.figures.render.html_template.validator import validate_and_normalize
from app.services.figures.design.typography import wrap_label
from app.services.figures.render.result import FigureRenderResult
from app.services.figures.render.svg.export_png import export_png_from_svg

W = 1365
H = 900

TONES = [
    ("#2563EB", "#EFF6FF", "#BFDBFE"),
    ("#16803A", "#F0FDF4", "#BBF7D0"),
    ("#EA580C", "#FFF7ED", "#FED7AA"),
    ("#6D28D9", "#F5F3FF", "#DDD6FE"),
    ("#0E7490", "#ECFEFF", "#A5F3FC"),
    ("#BE123C", "#FFF1F2", "#FECDD3"),
]


def render_infographic_spec(spec: dict[str, Any], out_path: Path, *, subtype: str = "") -> FigureRenderResult:
    validation = validate_and_normalize(spec, subtype=subtype)
    if not validation["ok"]:
        raise ValueError("; ".join(str(x) for x in validation.get("messages") or ["DiagramSpec 无法渲染"]))
    normalized = validation["spec"]
    svg = render_svg(normalized)
    png_path = out_path.with_suffix(".png")
    svg_path = out_path.with_name(out_path.stem + ".infographic.svg")
    svg_path.parent.mkdir(parents=True, exist_ok=True)
    svg_path.write_text(svg, encoding="utf-8")
    try:
        if not export_png_from_svg(svg_path, png_path):
            raise ValueError("模板 SVG 未能导出 PNG")
    finally:
        if svg_path.is_file():
            svg_path.unlink()
    return FigureRenderResult(
        primary_png_path=png_path if png_path.is_file() else None,
        optional_svg_path=None,
        render_source="infographic.template",
        diagnostics={
            "template_id": normalized.get("template_id"),
            "chart_type": normalized.get("chart_type"),
            "validation": validation,
        },
    )


def render_svg(spec: dict[str, Any]) -> str:
    template = str(spec.get("template_id") or "grouped_infographic")
    body = {
        "horizontal_stage_cards": _render_horizontal_stage_cards,
        "snake_cards": _render_snake_cards,
        "grouped_infographic": _render_grouped_infographic,
        "vertical_layers": _render_vertical_layers,
        "shared_resource_three_column": _render_shared_resource_three_column,
        "comparison_matrix": _render_comparison_matrix,
        "comparison_matrix_multi": _render_comparison_matrix_multi,
        "decision_cards": _render_decision_cards,
        "decision_branch_tree": _render_decision_branch_tree,
        "service_topology": _render_service_topology,
        "mechanism_sequence": _render_mechanism_sequence,
        "parallel_stack_architecture": _render_parallel_stack_architecture,
        "horizontal_timeline": _render_horizontal_timeline,
        "taxonomy_tree": _render_taxonomy_tree,
        "hub_spoke_concept": _render_hub_spoke_concept,
        "mechanism_mapping": _render_mechanism_mapping,
    }.get(template, _render_grouped_infographic)(spec)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">
<defs>
{_defs()}
</defs>
<style>{_style()}</style>
<rect width="{W}" height="{H}" fill="#F8FAFC"/>
<circle cx="1160" cy="104" r="190" fill="#EFF6FF" opacity="0.34"/>
<circle cx="160" cy="790" r="150" fill="#ECFEFF" opacity="0.28"/>
{_title(spec)}
{body}
</svg>"""


def _defs() -> str:
    return """<filter id="softShadow" x="-20%" y="-20%" width="140%" height="140%">
  <feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#0F172A" flood-opacity="0.09"/>
</filter>
<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
  <path d="M0,0 L10,5 L0,10 z" fill="#1F2937"/>
</marker>
<marker id="arrowBlue" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="8" markerHeight="8" orient="auto-start-reverse">
  <path d="M0,0 L10,5 L0,10 z" fill="#1D4ED8"/>
</marker>"""


def _style() -> str:
    return """
text { font-family: "Noto Sans CJK SC", "Source Han Sans SC", "Microsoft YaHei", "PingFang SC", Arial, sans-serif; }
.title { fill:#0F172A; font-size:48px; font-weight:800; letter-spacing:0; }
.subtitle { fill:#475569; font-size:24px; font-weight:500; }
.card { filter:url(#softShadow); }
.muted { fill:#475569; }
.small { font-size:17px; }
.label { fill:#0F172A; font-size:26px; font-weight:700; }
.body { fill:#1F2937; font-size:18px; }
.note { fill:#334155; font-size:17px; }
.badgeText { fill:#FFFFFF; font-size:24px; font-weight:800; }
.connector { stroke:#1F2937; stroke-width:3; stroke-linecap:round; stroke-linejoin:round; fill:none; marker-end:url(#arrow); }
.connectorLight { stroke:#2563EB; stroke-width:2.4; stroke-linecap:round; stroke-linejoin:round; fill:none; marker-end:url(#arrowBlue); }
.connectorDashed { stroke-dasharray:8 8; }
"""


def _esc(value: Any) -> str:
    return html.escape(str(value or ""), quote=True)


def _tone(index: int) -> tuple[str, str, str]:
    return TONES[index % len(TONES)]


def _title(spec: dict[str, Any]) -> str:
    _ = spec
    return ""


def _rect(x: float, y: float, w: float, h: float, fill: str, stroke: str, *, rx: float = 18, width: float = 2, cls: str = "card") -> str:
    return f'<rect class="{cls}" x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{rx:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{width:.1f}"/>'


def _line(x1: float, y1: float, x2: float, y2: float, *, cls: str = "connector", label: str = "") -> str:
    mid = ""
    if label:
        mid_x = (x1 + x2) / 2
        mid_y = (y1 + y2) / 2 - 16
        mid = _pill_label(mid_x, mid_y, label)
    return f'<line class="{cls}" x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}"/>{mid}'


def _path(d: str, *, cls: str = "connector", label: tuple[float, float, str] | None = None) -> str:
    lab = _pill_label(label[0], label[1], label[2]) if label else ""
    return f'<path class="{cls}" d="{d}"/>{lab}'


def _pill_label(cx: float, cy: float, text: str) -> str:
    if not text:
        return ""
    safe = _esc(text).replace("\\n", " ")
    width = min(150, max(54, len(safe) * 13))
    return (
        f'<rect x="{cx-width/2:.1f}" y="{cy-16:.1f}" width="{width:.1f}" height="28" rx="14" fill="#FFFFFF" stroke="#CBD5E1" stroke-width="1"/>'
        f'<text x="{cx:.1f}" y="{cy+1:.1f}" text-anchor="middle" dominant-baseline="middle" fill="#334155" font-size="15" font-weight="700">{safe}</text>'
    )


def _text_center(x: float, y: float, text: str, size: int, fill: str, *, weight: int = 400, max_width: float = 260, max_lines: int = 3) -> str:
    lines = wrap_label(text.replace("\\n", "\n"), max_width, font_size=size, max_lines=max_lines)
    line_h = size * 1.26
    start = y - (len(lines) - 1) * line_h / 2
    return "\n".join(
        f'<text x="{x:.1f}" y="{start+i*line_h:.1f}" text-anchor="middle" dominant-baseline="middle" fill="{fill}" font-size="{size}" font-weight="{weight}">{_esc(line)}</text>'
        for i, line in enumerate(lines)
    )


def _text_left(x: float, y: float, text: str, size: int, fill: str, *, weight: int = 400, max_width: float = 260, max_lines: int = 3, line_h: float | None = None) -> str:
    lines = wrap_label(str(text or ""), max_width, font_size=size, max_lines=max_lines)
    lh = line_h or size * 1.45
    return "\n".join(
        f'<text x="{x:.1f}" y="{y+i*lh:.1f}" fill="{fill}" font-size="{size}" font-weight="{weight}">{_esc(line)}</text>'
        for i, line in enumerate(lines)
    )


def _bullets(x: float, y: float, items: list[Any], *, size: int = 18, max_width: float = 260, max_items: int = 3) -> str:
    parts: list[str] = []
    yy = y
    for raw in items[:max_items]:
        lines = wrap_label(str(raw), max_width - 22, font_size=size, max_lines=2)
        parts.append(f'<circle cx="{x:.1f}" cy="{yy-5:.1f}" r="3.2" fill="#334155"/>')
        for i, line in enumerate(lines):
            parts.append(f'<text x="{x+18:.1f}" y="{yy+i*size*1.35:.1f}" fill="#1F2937" font-size="{size}">{_esc(line)}</text>')
        yy += max(1, len(lines)) * size * 1.35 + 8
    return "\n".join(parts)


def _number_badge(cx: float, cy: float, number: int, color: str) -> str:
    return (
        f'<rect x="{cx-24:.1f}" y="{cy-24:.1f}" width="48" height="48" rx="14" fill="{color}"/>'
        f'<text class="badgeText" x="{cx:.1f}" y="{cy+1:.1f}" text-anchor="middle" dominant-baseline="middle">{number}</text>'
    )


def _simple_icon(cx: float, cy: float, color: str, kind: str = "card") -> str:
    """Small line icon set used by the HTML-template route.

    Keep it intentionally simple and deterministic. Unknown names fall back to a
    generic card icon instead of drawing an empty placeholder.
    """
    k = str(kind or "card").lower()
    if k in {"database", "db", "vector_db"}:
        return (
            f'<ellipse cx="{cx:.1f}" cy="{cy-16:.1f}" rx="31" ry="11" fill="#FFFFFF" stroke="{color}" stroke-width="3"/>'
            f'<path d="M {cx-31:.1f} {cy-16:.1f} V {cy+22:.1f} C {cx-31:.1f} {cy+36:.1f}, {cx+31:.1f} {cy+36:.1f}, {cx+31:.1f} {cy+22:.1f} V {cy-16:.1f}" fill="none" stroke="{color}" stroke-width="3"/>'
            f'<ellipse cx="{cx:.1f}" cy="{cy+22:.1f}" rx="31" ry="11" fill="#FFFFFF" stroke="{color}" stroke-width="3"/>'
        )
    if k in {"question", "help"}:
        return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="34" fill="#FFFFFF" stroke="{color}" stroke-width="3"/><text x="{cx:.1f}" y="{cy+10:.1f}" text-anchor="middle" font-size="44" font-weight="800" fill="{color}">?</text>'
    if k in {"search", "retrieval", "检索"}:
        return f'<circle cx="{cx-8:.1f}" cy="{cy-8:.1f}" r="20" fill="#FFFFFF" stroke="{color}" stroke-width="3"/><line x1="{cx+8:.1f}" y1="{cy+8:.1f}" x2="{cx+28:.1f}" y2="{cy+28:.1f}" stroke="{color}" stroke-width="4" stroke-linecap="round"/>'
    if k in {"gear", "config", "train", "training"}:
        return f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="17" fill="#FFFFFF" stroke="{color}" stroke-width="3"/><circle cx="{cx:.1f}" cy="{cy:.1f}" r="5" fill="{color}"/><path d="M {cx:.1f} {cy-32:.1f} V {cy-22:.1f} M {cx:.1f} {cy+22:.1f} V {cy+32:.1f} M {cx-32:.1f} {cy:.1f} H {cx-22:.1f} M {cx+22:.1f} {cy:.1f} H {cx+32:.1f}" stroke="{color}" stroke-width="3" stroke-linecap="round"/>'
    if k in {"chip", "model", "llm", "brain"}:
        return f'<rect x="{cx-25:.1f}" y="{cy-25:.1f}" width="50" height="50" rx="8" fill="#FFFFFF" stroke="{color}" stroke-width="3"/><rect x="{cx-10:.1f}" y="{cy-10:.1f}" width="20" height="20" rx="3" fill="none" stroke="{color}" stroke-width="2"/><path d="M {cx-34:.1f} {cy-14:.1f} H {cx-25:.1f} M {cx-34:.1f} {cy:.1f} H {cx-25:.1f} M {cx-34:.1f} {cy+14:.1f} H {cx-25:.1f} M {cx+25:.1f} {cy-14:.1f} H {cx+34:.1f} M {cx+25:.1f} {cy:.1f} H {cx+34:.1f} M {cx+25:.1f} {cy+14:.1f} H {cx+34:.1f}" stroke="{color}" stroke-width="2.5" stroke-linecap="round"/>'
    if k in {"api", "gateway", "cloud"}:
        return f'<path d="M {cx-31:.1f} {cy+8:.1f} C {cx-34:.1f} {cy-8:.1f}, {cx-18:.1f} {cy-20:.1f}, {cx-4:.1f} {cy-16:.1f} C {cx+4:.1f} {cy-32:.1f}, {cx+27:.1f} {cy-22:.1f}, {cx+25:.1f} {cy-5:.1f} C {cx+39:.1f} {cy-2:.1f}, {cx+36:.1f} {cy+22:.1f}, {cx+20:.1f} {cy+22:.1f} H {cx-20:.1f} C {cx-30:.1f} {cy+22:.1f}, {cx-36:.1f} {cy+16:.1f}, {cx-31:.1f} {cy+8:.1f} Z" fill="#FFFFFF" stroke="{color}" stroke-width="3"/>'
    if k in {"user", "people"}:
        return f'<circle cx="{cx:.1f}" cy="{cy-14:.1f}" r="14" fill="#FFFFFF" stroke="{color}" stroke-width="3"/><path d="M {cx-26:.1f} {cy+28:.1f} C {cx-20:.1f} {cy+4:.1f}, {cx+20:.1f} {cy+4:.1f}, {cx+26:.1f} {cy+28:.1f}" fill="none" stroke="{color}" stroke-width="3" stroke-linecap="round"/>'
    if k in {"trophy", "eval", "evaluation"}:
        return f'<path d="M {cx-18:.1f} {cy-24:.1f} H {cx+18:.1f} V {cy-4:.1f} C {cx+18:.1f} {cy+12:.1f}, {cx+8:.1f} {cy+20:.1f}, {cx:.1f} {cy+20:.1f} C {cx-8:.1f} {cy+20:.1f}, {cx-18:.1f} {cy+12:.1f}, {cx-18:.1f} {cy-4:.1f} Z" fill="#FFFFFF" stroke="{color}" stroke-width="3"/><path d="M {cx-18:.1f} {cy-16:.1f} H {cx-32:.1f} C {cx-32:.1f} {cy:.1f}, {cx-24:.1f} {cy+8:.1f}, {cx-14:.1f} {cy+10:.1f} M {cx+18:.1f} {cy-16:.1f} H {cx+32:.1f} C {cx+32:.1f} {cy:.1f}, {cx+24:.1f} {cy+8:.1f}, {cx+14:.1f} {cy+10:.1f}" fill="none" stroke="{color}" stroke-width="3"/><line x1="{cx:.1f}" y1="{cy+20:.1f}" x2="{cx:.1f}" y2="{cy+34:.1f}" stroke="{color}" stroke-width="3"/><line x1="{cx-18:.1f}" y1="{cy+34:.1f}" x2="{cx+18:.1f}" y2="{cy+34:.1f}" stroke="{color}" stroke-width="3"/>'
    return (
        f'<rect x="{cx-30:.1f}" y="{cy-30:.1f}" width="60" height="60" rx="14" fill="#FFFFFF" stroke="{color}" stroke-width="3"/>'
        f'<line x1="{cx-16:.1f}" y1="{cy-8:.1f}" x2="{cx+16:.1f}" y2="{cy-8:.1f}" stroke="{color}" stroke-width="3"/>'
        f'<line x1="{cx-16:.1f}" y1="{cy+8:.1f}" x2="{cx+10:.1f}" y2="{cy+8:.1f}" stroke="{color}" stroke-width="3"/>'
    )


def _render_horizontal_stage_cards(spec: dict[str, Any]) -> str:
    stages = spec.get("stages") or []
    n = max(1, len(stages))
    gap = 38
    x0 = 62
    y = 190
    w = (W - 2 * x0 - gap * (n - 1)) / n
    h = 520
    parts: list[str] = []
    for i, stage in enumerate(stages):
        color, fill, stroke = _tone(i)
        x = x0 + i * (w + gap)
        parts.append(_rect(x, y, w, h, fill, color, rx=24))
        parts.append(_number_badge(x + 42, y + 46, i + 1, color))
        parts.append(_simple_icon(x + w - 55, y + 55, color, str(stage.get("icon") or "card")))
        parts.append(_text_left(x + 36, y + 118, str(stage.get("title") or ""), 28, "#0F172A", weight=800, max_width=w - 72, max_lines=2))
        parts.append(f'<line x1="{x+34:.1f}" y1="{y+180:.1f}" x2="{x+w-34:.1f}" y2="{y+180:.1f}" stroke="{stroke}" stroke-width="2"/>')
        parts.append(_bullets(x + 42, y + 226, list(stage.get("bullets") or stage.get("items") or []), max_width=w - 72))
        io = list(stage.get("io") or [])
        if io:
            parts.append(_rect(x + 30, y + h - 112, w - 60, 72, "#FFFFFFB8", stroke, rx=14, width=1.4, cls=""))
            parts.append(_text_left(x + 48, y + h - 72, " / ".join(str(v) for v in io[:2]), 16, "#334155", max_width=w - 96, max_lines=2))
        if i < n - 1:
            parts.append(_line(x + w + 8, y + h / 2, x + w + gap - 9, y + h / 2, label=str(stage.get("connector") or "")))
    if spec.get("note"):
        parts.append(_legend(str(spec["note"])))
    return "\n".join(parts)


def _render_snake_cards(spec: dict[str, Any]) -> str:
    steps = spec.get("steps") or []
    n = len(steps)
    cols = max(3, math.ceil(n / 2))
    gap = 42
    x0 = 58
    card_w = (W - 2 * x0 - gap * (cols - 1)) / cols
    card_h = 246
    top_y = 184
    bottom_y = 552
    positions: dict[int, tuple[float, float]] = {}
    parts: list[str] = []
    for i, step in enumerate(steps):
        row = 0 if i < cols else 1
        col = i if row == 0 else (cols - 1 - (i - cols))
        x = x0 + col * (card_w + gap)
        y = top_y if row == 0 else bottom_y
        positions[i] = (x, y)
        color, fill, stroke = _tone(i)
        parts.append(_rect(x, y, card_w, card_h, fill, color, rx=22))
        parts.append(_number_badge(x + 42, y + 44, i + 1, color))
        parts.append(_text_left(x + 82, y + 54, str(step.get("title") or ""), 27, "#0F172A", weight=800, max_width=card_w - 112, max_lines=2))
        parts.append(_simple_icon(x + 58, y + 126, color, str(step.get("icon") or "card")))
        parts.append(_bullets(x + 126, y + 120, list(step.get("items") or step.get("bullets") or []), size=17, max_width=card_w - 155))
    for i in range(n - 1):
        x1, y1 = positions[i]
        x2, y2 = positions[i + 1]
        if i == cols - 1:
            sx, sy = x1 + card_w / 2, y1 + card_h + 10
            tx, ty = x2 + card_w / 2, y2 - 10
            parts.append(_path(f"M {sx:.1f} {sy:.1f} C {sx:.1f} {sy+96:.1f}, {tx:.1f} {ty-96:.1f}, {tx:.1f} {ty:.1f}", cls="connectorLight"))
        elif y1 == y2:
            if x2 > x1:
                parts.append(_line(x1 + card_w + 8, y1 + card_h / 2, x2 - 8, y2 + card_h / 2, cls="connectorLight"))
            else:
                parts.append(_line(x1 - 8, y1 + card_h / 2, x2 + card_w + 8, y2 + card_h / 2, cls="connectorLight"))
    if spec.get("note"):
        parts.append(_legend(str(spec["note"])))
    return "\n".join(parts)


def _render_grouped_infographic(spec: dict[str, Any]) -> str:
    cards = spec.get("cards") or []
    n = len(cards)
    cols = min(4, max(3, n if n <= 4 else 4))
    rows = math.ceil(max(1, n) / cols)
    gap = 34
    x0 = 72
    y0 = 184
    card_w = (W - 2 * x0 - gap * (cols - 1)) / cols
    card_h = min(250, (H - y0 - 94 - gap * (rows - 1)) / rows)
    parts: list[str] = []
    for i, card in enumerate(cards):
        row = i // cols
        col = i % cols
        x = x0 + col * (card_w + gap)
        y = y0 + row * (card_h + gap)
        color, fill, stroke = _tone(i)
        parts.append(_rect(x, y, card_w, card_h, fill, color, rx=22))
        parts.append(_number_badge(x + 42, y + 44, i + 1, color))
        parts.append(_text_left(x + 82, y + 52, str(card.get("title") or ""), 25, "#0F172A", weight=800, max_width=card_w - 116, max_lines=2))
        parts.append(f'<line x1="{x+32:.1f}" y1="{y+100:.1f}" x2="{x+card_w-32:.1f}" y2="{y+100:.1f}" stroke="{stroke}" stroke-width="2" stroke-dasharray="7 7"/>')
        if card.get("summary"):
            parts.append(_text_left(x + 34, y + 140, str(card.get("summary")), 18, "#1F2937", weight=600, max_width=card_w - 68, max_lines=2))
        parts.append(_bullets(x + 38, y + 186, list(card.get("items") or []), size=16, max_width=card_w - 72, max_items=2))
    if spec.get("note"):
        parts.append(_legend(str(spec["note"])))
    return "\n".join(parts)


def _render_vertical_layers(spec: dict[str, Any]) -> str:
    layers = spec.get("layers") or []
    n = max(1, len(layers))
    x = 225
    w = 915
    gap = 28
    y0 = 178
    h = min(170, (H - y0 - 96 - gap * (n - 1)) / n)
    parts: list[str] = []
    labels = list(spec.get("connections") or [])
    for i, layer in enumerate(layers):
        color, fill, stroke = _tone(i)
        y = y0 + i * (h + gap)
        parts.append(_rect(x, y, w, h, fill, color, rx=22))
        parts.append(_rect(x - 2, y - 18, 152, 42, fill, color, rx=14, width=1.5, cls=""))
        parts.append(_text_center(x + 74, y + 3, str(layer.get("label") or f"第 {i+1} 层"), 20, color, weight=800, max_width=130, max_lines=1))
        parts.append(_simple_icon(x + 130, y + h / 2 + 6, color, "database" if "数据" in str(layer.get("title")) else "card"))
        parts.append(_text_left(x + 250, y + 58, str(layer.get("title") or ""), 34, "#0F172A", weight=800, max_width=430, max_lines=1))
        parts.append(_text_left(x + 250, y + 104, str(layer.get("desc") or ""), 21, "#1F2937", max_width=560, max_lines=2))
        if i < n - 1:
            label = labels[i] if i < len(labels) else ""
            parts.append(_line(x + w / 2, y + h + 8, x + w / 2, y + h + gap - 8, cls="connectorLight", label=str(label)))
            parts.append(_line(x + w / 2 + 110, y + h + gap - 8, x + w / 2 + 110, y + h + 8, cls="connectorLight connectorDashed", label="返回" if i == 0 else "结果"))
    parts.append(_legend("实线表示主动请求方向；虚线表示响应或结果返回。", x=66, y=760, width=320))
    return "\n".join(parts)


def _render_shared_resource_three_column(spec: dict[str, Any]) -> str:
    left = spec.get("left") or {}
    center = spec.get("center") or {}
    right = spec.get("right") or {}
    col_y = 190
    col_h = 585
    col_w = 350
    left_x = 58
    center_x = 500
    right_x = 957
    parts: list[str] = []
    parts.append(_group_column(left_x, col_y, col_w, col_h, left, 1, "left"))
    parts.append(_db_center(center_x + 120, 382, 225, 250, center))
    parts.append(_group_column(right_x, col_y, col_w, col_h, right, 0, "right"))
    parts.append(_line(left_x + col_w + 20, 445, center_x + 4, 445, cls="connectorLight", label="写入"))
    parts.append(_line(center_x + 240 + 10, 445, right_x - 22, 445, cls="connectorLight", label="查询"))
    parts.append(_path(f"M {right_x-24:.1f} 520 C 850 520, 830 560, {center_x+244:.1f} 560", cls="connectorLight connectorDashed", label=(806, 544, "返回结果")))
    if spec.get("note"):
        parts.append(_legend(str(spec["note"]), x=470, y=182, width=420))
    return "\n".join(parts)


def _group_column(x: float, y: float, w: float, h: float, data: dict[str, Any], tone_index: int, name: str) -> str:
    color, fill, stroke = _tone(tone_index)
    parts = [_rect(x, y, w, h, fill, color, rx=26)]
    parts.append(_text_center(x + w / 2, y + 48, str(data.get("title") or ""), 29, "#0F172A", weight=800, max_width=w - 52, max_lines=1))
    if data.get("subtitle"):
        parts.append(_text_center(x + w / 2, y + 86, str(data.get("subtitle")), 21, color, weight=700, max_width=w - 52, max_lines=1))
    modules = data.get("modules") or []
    card_y = y + 125
    for i, mod in enumerate(modules[:4]):
        parts.append(_rect(x + 36, card_y + i * 128, w - 72, 96, "#FFFFFF", stroke, rx=18, width=1.6, cls=""))
        parts.append(_simple_icon(x + 82, card_y + i * 128 + 48, color, str(mod.get("icon") or "card")))
        parts.append(_text_left(x + 138, card_y + i * 128 + 38, str(mod.get("title") or ""), 24, "#0F172A", weight=800, max_width=w - 180, max_lines=1))
        parts.append(_text_left(x + 138, card_y + i * 128 + 70, str(mod.get("desc") or ""), 17, "#475569", max_width=w - 180, max_lines=1))
    return "\n".join(parts)


def _db_center(cx: float, cy: float, w: float, h: float, data: dict[str, Any]) -> str:
    color = "#6D28D9"
    return (
        f'<ellipse cx="{cx:.1f}" cy="{cy-h/2:.1f}" rx="{w/2:.1f}" ry="38" fill="#F5F3FF" stroke="{color}" stroke-width="3"/>'
        f'<rect x="{cx-w/2:.1f}" y="{cy-h/2:.1f}" width="{w:.1f}" height="{h:.1f}" fill="#F5F3FF" stroke="none"/>'
        f'<line x1="{cx-w/2:.1f}" y1="{cy-h/2:.1f}" x2="{cx-w/2:.1f}" y2="{cy+h/2:.1f}" stroke="{color}" stroke-width="3"/>'
        f'<line x1="{cx+w/2:.1f}" y1="{cy-h/2:.1f}" x2="{cx+w/2:.1f}" y2="{cy+h/2:.1f}" stroke="{color}" stroke-width="3"/>'
        f'<ellipse cx="{cx:.1f}" cy="{cy+h/2:.1f}" rx="{w/2:.1f}" ry="38" fill="#F5F3FF" stroke="{color}" stroke-width="3"/>'
        + _simple_icon(cx, cy - 28, color, "database")
        + _text_center(cx, cy + 54, str(data.get("title") or ""), 29, "#0F172A", weight=800, max_width=w - 28, max_lines=2)
        + _text_center(cx, cy + 112, str(data.get("desc") or ""), 18, "#475569", weight=500, max_width=w - 28, max_lines=2)
    )


def _render_comparison_matrix(spec: dict[str, Any]) -> str:
    dims = spec.get("dimensions") or []
    cols = list(spec.get("columns") or ["对象 A", "对象 B"])
    x0 = 62
    y0 = 176
    dim_w = 260
    col_w = 480
    row_h = min(130, (H - y0 - 110) / (len(dims) + 1))
    parts: list[str] = []
    parts.append(_rect(x0, y0, dim_w, row_h, "#E2E8F0", "#CBD5E1", rx=18, cls=""))
    parts.append(_text_center(x0 + dim_w / 2, y0 + row_h / 2, "对比维度", 25, "#0F172A", weight=800))
    for j, col in enumerate(cols[:2]):
        color, fill, _ = _tone(j)
        x = x0 + dim_w + j * col_w
        parts.append(_rect(x, y0, col_w - 8, row_h, fill, color, rx=18, cls=""))
        parts.append(_text_center(x + (col_w - 8) / 2, y0 + row_h / 2, str(col), 28, "#0F172A", weight=800, max_width=col_w - 80))
    for i, dim in enumerate(dims):
        y = y0 + (i + 1) * row_h
        parts.append(_rect(x0, y, dim_w, row_h - 8, "#FFFFFF", "#CBD5E1", rx=14, cls=""))
        parts.append(_text_left(x0 + 28, y + 44, str(dim.get("title") or ""), 22, "#0F172A", weight=800, max_width=dim_w - 50, max_lines=1))
        parts.append(_text_left(x0 + 28, y + 76, str(dim.get("desc") or ""), 16, "#64748B", max_width=dim_w - 50, max_lines=1))
        for j, side in enumerate(("left", "right")):
            color, fill, stroke = _tone(j)
            x = x0 + dim_w + j * col_w
            val = dim.get(side) or {}
            parts.append(_rect(x, y, col_w - 8, row_h - 8, fill, stroke, rx=14, width=1.4, cls=""))
            parts.append(_text_left(x + 28, y + 36, str(val.get("tag") or ""), 20, color, weight=800, max_width=120, max_lines=1))
            parts.append(_score_bars(x + 160, y + 29, int(val.get("score") or 0), color))
            parts.append(_bullets(x + 30, y + 72, list(val.get("bullets") or []), size=15, max_width=col_w - 60, max_items=2))
    return "\n".join(parts)


def _score_bars(x: float, y: float, score: int, color: str) -> str:
    parts = []
    for i in range(5):
        fill = color if i < score else "#CBD5E1"
        parts.append(f'<rect x="{x+i*18:.1f}" y="{y:.1f}" width="12" height="30" rx="5" fill="{fill}" opacity="{1 if i < score else 0.55}"/>')
    return "\n".join(parts)


def _render_decision_cards(spec: dict[str, Any]) -> str:
    root = spec.get("root") or {}
    branches = spec.get("branches") or []
    parts: list[str] = []
    root_w = 560
    root_x = (W - root_w) / 2
    root_y = 178
    parts.append(_rect(root_x, root_y, root_w, 112, "#EEF2FF", "#4F46E5", rx=28))
    parts.append(_simple_icon(root_x + 70, root_y + 56, "#4F46E5", "question"))
    parts.append(_text_left(root_x + 132, root_y + 66, str(root.get("title") or "你的主要需求是什么？"), 30, "#0F172A", weight=800, max_width=root_w - 164, max_lines=1))
    n = max(1, len(branches))
    gap = 46
    x0 = 74
    card_w = (W - 2 * x0 - gap * (n - 1)) / n
    card_h = 360
    card_y = 430
    for i, branch in enumerate(branches):
        color, fill, stroke = _tone(i + 1)
        x = x0 + i * (card_w + gap)
        parts.append(_path(f"M {W/2:.1f} {root_y+112:.1f} L {x+card_w/2:.1f} {card_y-22:.1f}", cls="connectorLight"))
        parts.append(_rect(x, card_y, card_w, card_h, fill, color, rx=24))
        parts.append(_text_center(x + card_w / 2, card_y + 54, str(branch.get("condition") or ""), 24, color, weight=800, max_width=card_w - 54, max_lines=2))
        parts.append(f'<line x1="{x+36:.1f}" y1="{card_y+106:.1f}" x2="{x+card_w-36:.1f}" y2="{card_y+106:.1f}" stroke="{stroke}" stroke-width="2" stroke-dasharray="7 7"/>')
        parts.append(_text_center(x + card_w / 2, card_y + 160, str(branch.get("title") or ""), 30, "#0F172A", weight=800, max_width=card_w - 48, max_lines=2))
        parts.append(_bullets(x + 50, card_y + 230, list(branch.get("bullets") or []), size=18, max_width=card_w - 90))
    return "\n".join(parts)


def _render_horizontal_timeline(spec: dict[str, Any]) -> str:
    events = spec.get("events") or []
    n = max(1, len(events))
    rail_y = 265
    left = 90
    right = W - 90
    parts = [f'<line x1="{left:.1f}" y1="{rail_y:.1f}" x2="{right:.1f}" y2="{rail_y:.1f}" stroke="#1F2937" stroke-width="4" marker-end="url(#arrow)"/>']
    item_w = min(198, (right - left) / n - 16)
    for i, event in enumerate(events):
        x = left + (right - left - 70) * i / max(1, n - 1)
        color, fill, stroke = _tone(i)
        parts.append(f'<circle cx="{x:.1f}" cy="{rail_y:.1f}" r="18" fill="#FFFFFF" stroke="{color}" stroke-width="6"/>')
        parts.append(_text_center(x, rail_y - 74, str(event.get("year") or ""), 29, color, weight=800, max_width=160, max_lines=1))
        card_x = min(max(32, x - item_w / 2), W - item_w - 32)
        card_y = 352
        parts.append(_rect(card_x, card_y, item_w, 365, "#FFFFFF", stroke, rx=18, width=1.5, cls=""))
        parts.append(_text_center(card_x + item_w / 2, card_y + 54, str(event.get("title") or ""), 25, color, weight=800, max_width=item_w - 26, max_lines=3))
        parts.append(f'<line x1="{card_x+20:.1f}" y1="{card_y+116:.1f}" x2="{card_x+item_w-20:.1f}" y2="{card_y+116:.1f}" stroke="{stroke}" stroke-width="2"/>')
        parts.append(_bullets(card_x + 22, card_y + 158, list(event.get("bullets") or []), size=15, max_width=item_w - 38, max_items=4))
        parts.append(f'<line x1="{x:.1f}" y1="{rail_y+24:.1f}" x2="{x:.1f}" y2="{card_y-8:.1f}" stroke="{color}" stroke-width="2" stroke-dasharray="7 8"/>')
    return "\n".join(parts)


def _render_taxonomy_tree(spec: dict[str, Any]) -> str:
    root = str(spec.get("root") or spec.get("title") or "分类")
    groups = spec.get("groups") or []
    root_w = 430
    root_x = (W - root_w) / 2
    root_y = 174
    parts = [_rect(root_x, root_y, root_w, 92, "#EEF2FF", "#4F46E5", rx=24)]
    parts.append(_text_center(W / 2, root_y + 46, root, 34, "#0F172A", weight=800, max_width=root_w - 40, max_lines=1))
    n = max(1, len(groups))
    gap = 44
    x0 = 78
    group_w = (W - 2 * x0 - gap * (n - 1)) / n
    group_y = 370
    for i, group in enumerate(groups):
        color, fill, stroke = _tone(i)
        x = x0 + i * (group_w + gap)
        parts.append(_line(W / 2, root_y + 92, x + group_w / 2, group_y - 28, cls="connectorLight"))
        parts.append(_rect(x, group_y, group_w, 92, fill, color, rx=20))
        parts.append(_text_center(x + group_w / 2, group_y + 46, str(group.get("title") or ""), 28, "#0F172A", weight=800, max_width=group_w - 34, max_lines=1))
        items = list(group.get("items") or [])
        item_y = group_y + 150
        for j, item in enumerate(items[:5]):
            iy = item_y + j * 76
            parts.append(_line(x + group_w / 2, group_y + 92, x + group_w / 2, iy - 8, cls="connectorLight"))
            parts.append(_rect(x + 32, iy, group_w - 64, 54, "#FFFFFF", stroke, rx=14, width=1.4, cls=""))
            parts.append(_text_center(x + group_w / 2, iy + 28, str(item), 23, "#0F172A", weight=700, max_width=group_w - 96, max_lines=1))
    return "\n".join(parts)


def _render_hub_spoke_concept(spec: dict[str, Any]) -> str:
    center = spec.get("center") or {"title": spec.get("title") or "核心概念"}
    items = spec.get("items") or []
    cx, cy = W / 2, 440
    parts = [_rect(cx - 170, cy - 92, 340, 184, "#EEF2FF", "#4F46E5", rx=34)]
    parts.append(_text_center(cx, cy - 20, str(center.get("title") or ""), 34, "#0F172A", weight=800, max_width=280, max_lines=2))
    if center.get("desc"):
        parts.append(_text_center(cx, cy + 52, str(center.get("desc")), 18, "#475569", max_width=260, max_lines=2))
    n = max(1, len(items))
    radius_x = 500
    radius_y = 270
    card_w, card_h = 255, 118
    for i, item in enumerate(items[:8]):
        angle = -math.pi / 2 + i * 2 * math.pi / n
        x = cx + math.cos(angle) * radius_x - card_w / 2
        y = cy + math.sin(angle) * radius_y - card_h / 2
        x = min(max(38, x), W - card_w - 38)
        y = min(max(168, y), H - card_h - 52)
        color, fill, stroke = _tone(i)
        parts.append(_line(cx, cy, x + card_w / 2, y + card_h / 2, cls="connectorLight"))
        parts.append(_rect(x, y, card_w, card_h, fill, color, rx=18))
        parts.append(_text_center(x + card_w / 2, y + 42, str(item.get("title") or ""), 23, "#0F172A", weight=800, max_width=card_w - 34, max_lines=1))
        parts.append(_text_center(x + card_w / 2, y + 78, str(item.get("desc") or ""), 16, "#475569", max_width=card_w - 34, max_lines=2))
    return "\n".join(parts)


def _render_mechanism_mapping(spec: dict[str, Any]) -> str:
    sections = spec.get("sections") or []
    n = max(3, len(sections))
    gap = 34
    x0 = 66
    y = 255
    card_w = (W - 2 * x0 - gap * (n - 1)) / n
    card_h = 310
    parts: list[str] = []
    for i, sec in enumerate(sections[:6]):
        color, fill, stroke = _tone(i)
        x = x0 + i * (card_w + gap)
        parts.append(_rect(x, y, card_w, card_h, fill, color, rx=22))
        parts.append(_number_badge(x + 42, y + 44, i + 1, color))
        parts.append(_text_left(x + 80, y + 54, str(sec.get("title") or ""), 26, "#0F172A", weight=800, max_width=card_w - 98, max_lines=2))
        parts.append(f'<line x1="{x+30:.1f}" y1="{y+108:.1f}" x2="{x+card_w-30:.1f}" y2="{y+108:.1f}" stroke="{stroke}" stroke-width="2"/>')
        parts.append(_text_left(x + 32, y + 158, str(sec.get("desc") or ""), 18, "#1F2937", max_width=card_w - 64, max_lines=4))
        if i < len(sections[:6]) - 1:
            parts.append(_line(x + card_w + 8, y + card_h / 2, x + card_w + gap - 8, y + card_h / 2, cls="connectorLight"))
    if spec.get("formula"):
        parts.append(_rect(330, 665, 705, 88, "#FFFFFF", "#A78BFA", rx=18, width=1.6, cls=""))
        parts.append(_text_center(W / 2, 710, str(spec.get("formula")), 24, "#0F172A", weight=700, max_width=660, max_lines=2))
    return "\n".join(parts)



def _render_comparison_matrix_multi(spec: dict[str, Any]) -> str:
    dims = spec.get("dimensions") or []
    cols = list(spec.get("columns") or ["对象 A", "对象 B", "对象 C"])
    cols = cols[:4]
    x0 = 62
    y0 = 176
    dim_w = 230
    col_w = (W - 2 * x0 - dim_w) / max(1, len(cols))
    row_h = min(118, (H - y0 - 108) / (len(dims) + 1))
    parts: list[str] = []
    parts.append(_rect(x0, y0, dim_w, row_h, "#E2E8F0", "#CBD5E1", rx=18, cls=""))
    parts.append(_text_center(x0 + dim_w / 2, y0 + row_h / 2, "对比维度", 24, "#0F172A", weight=800))
    for j, col in enumerate(cols):
        color, fill, _ = _tone(j)
        x = x0 + dim_w + j * col_w
        parts.append(_rect(x, y0, col_w - 8, row_h, fill, color, rx=18, cls=""))
        parts.append(_text_center(x + (col_w - 8) / 2, y0 + row_h / 2, str(col), 26, "#0F172A", weight=800, max_width=col_w - 24, max_lines=1))
    for i, dim in enumerate(dims[:5]):
        y = y0 + (i + 1) * row_h
        parts.append(_rect(x0, y, dim_w, row_h - 8, "#FFFFFF", "#CBD5E1", rx=14, cls=""))
        parts.append(_text_left(x0 + 24, y + 42, str(dim.get("title") or ""), 21, "#0F172A", weight=800, max_width=dim_w - 48, max_lines=1))
        parts.append(_text_left(x0 + 24, y + 72, str(dim.get("desc") or ""), 15, "#64748B", max_width=dim_w - 48, max_lines=1))
        scores = dim.get("scores") or {}
        bullets = dim.get("bullets") or {}
        for j, col in enumerate(cols):
            color, fill, stroke = _tone(j)
            x = x0 + dim_w + j * col_w
            parts.append(_rect(x, y, col_w - 8, row_h - 8, fill, stroke, rx=14, width=1.3, cls=""))
            score = int(scores.get(col) or 3)
            parts.append(_score_bars(x + 28, y + 26, score, color))
            b = bullets.get(col) if isinstance(bullets, dict) else []
            if b:
                parts.append(_bullets(x + 28, y + 72, list(b), size=14, max_width=col_w - 50, max_items=1))
    return "\n".join(parts)


def _render_decision_branch_tree(spec: dict[str, Any]) -> str:
    root = spec.get("root") or {"title": "你的主要条件是否成立？"}
    branches = spec.get("branches") or []
    parts: list[str] = []
    root_w = 560
    root_x = (W - root_w) / 2
    root_y = 178
    parts.append(_rect(root_x, root_y, root_w, 112, "#EEF2FF", "#4F46E5", rx=28))
    parts.append(_simple_icon(root_x + 70, root_y + 56, "#4F46E5", "question"))
    parts.append(_text_left(root_x + 132, root_y + 66, str(root.get("title") or ""), 30, "#0F172A", weight=800, max_width=root_w - 164, max_lines=1))
    gap = 46
    x0 = 74
    n = max(2, min(4, len(branches)))
    card_w = (W - 2 * x0 - gap * (n - 1)) / n
    card_y = 430
    card_h = 360
    for i, branch in enumerate(branches[:n]):
        color, fill, stroke = _tone(i + 1)
        x = x0 + i * (card_w + gap)
        label = str(branch.get("label") or branch.get("condition") or ("是" if i == 0 else "否"))
        parts.append(_path(f"M {W/2:.1f} {root_y+112:.1f} C {W/2:.1f} 345, {x+card_w/2:.1f} 345, {x+card_w/2:.1f} {card_y-20:.1f}", cls="connectorLight", label=(x + card_w / 2, 350, label)))
        parts.append(_rect(x, card_y, card_w, card_h, fill, color, rx=24))
        parts.append(_text_center(x + card_w / 2, card_y + 54, label, 24, color, weight=800, max_width=card_w - 54, max_lines=1))
        parts.append(f'<line x1="{x+36:.1f}" y1="{card_y+106:.1f}" x2="{x+card_w-36:.1f}" y2="{card_y+106:.1f}" stroke="{stroke}" stroke-width="2" stroke-dasharray="7 7"/>')
        parts.append(_text_center(x + card_w / 2, card_y + 162, str(branch.get("title") or ""), 29, "#0F172A", weight=800, max_width=card_w - 48, max_lines=2))
        parts.append(_bullets(x + 50, card_y + 230, list(branch.get("bullets") or []), size=18, max_width=card_w - 90))
    return "\n".join(parts)


def _render_service_topology(spec: dict[str, Any]) -> str:
    gateway = spec.get("gateway") or {"title": "API 网关", "desc": "统一入口 / 路由转发"}
    services = spec.get("services") or []
    queue = spec.get("queue") or {"title": "消息队列", "desc": "异步解耦 / 事件传递"}
    parts: list[str] = []
    gw_w, gw_h = 430, 104
    gw_x, gw_y = (W - gw_w) / 2, 178
    parts.append(_rect(gw_x, gw_y, gw_w, gw_h, "#EFF6FF", "#2563EB", rx=18))
    parts.append(_text_center(W / 2, gw_y + 42, str(gateway.get("title") or "API 网关"), 32, "#0F172A", weight=800, max_width=gw_w-40, max_lines=1))
    parts.append(_text_center(W / 2, gw_y + 76, str(gateway.get("desc") or ""), 19, "#475569", max_width=gw_w-40, max_lines=1))
    n = max(1, len(services))
    gap = 46
    x0 = 150
    service_w = (W - 2 * x0 - gap * (n - 1)) / n
    service_y, service_h = 370, 138
    for i, svc in enumerate(services):
        color, fill, stroke = _tone(i + 1)
        x = x0 + i * (service_w + gap)
        parts.append(_line(W/2, gw_y+gw_h, x+service_w/2, service_y-18, cls="connector"))
        parts.append(_rect(x, service_y, service_w, service_h, fill, color, rx=18))
        parts.append(_text_center(x+service_w/2, service_y+48, str(svc.get("title") or ""), 27, "#0F172A", weight=800, max_width=service_w-30, max_lines=1))
        parts.append(_text_center(x+service_w/2, service_y+88, str(svc.get("desc") or ""), 18, "#475569", max_width=service_w-30, max_lines=2))
    q_w, q_h = 360, 118
    q_x, q_y = (W - q_w) / 2, 640
    parts.append(_rect(q_x, q_y, q_w, q_h, "#ECFEFF", "#0E7490", rx=18))
    parts.append(_text_center(W/2, q_y+44, str(queue.get("title") or "消息队列"), 30, "#0F172A", weight=800, max_width=q_w-40))
    parts.append(_text_center(W/2, q_y+80, str(queue.get("desc") or ""), 18, "#475569", max_width=q_w-40))
    if services:
        # Orders service (middle if exists) publishes event; queue notifies last service.
        mid_idx = min(1, len(services)-1)
        mid_x = x0 + mid_idx*(service_w+gap) + service_w/2
        parts.append(_path(f"M {mid_x:.1f} {service_y+service_h:.1f} L {mid_x:.1f} {q_y-20:.1f} L {W/2:.1f} {q_y-20:.1f} L {W/2:.1f} {q_y:.1f}", cls="connectorLight connectorDashed", label=(mid_x, q_y-48, "发布事件")))
    if spec.get("note"):
        parts.append(_legend(str(spec["note"])))
    return "\n".join(parts)


def _render_mechanism_sequence(spec: dict[str, Any]) -> str:
    sections = spec.get("sections") or []
    n = max(3, len(sections))
    gap = 34
    x0 = 66
    y = 255
    card_w = (W - 2 * x0 - gap * (n - 1)) / n
    card_h = 300
    parts: list[str] = []
    for i, sec in enumerate(sections[:6]):
        color, fill, stroke = _tone(i)
        x = x0 + i * (card_w + gap)
        parts.append(_rect(x, y, card_w, card_h, fill, color, rx=22))
        parts.append(_number_badge(x + 42, y + 44, i + 1, color))
        parts.append(_simple_icon(x + card_w - 52, y + 52, color, "chip" if i in (1, 2) else "card"))
        parts.append(_text_left(x + 32, y + 105, str(sec.get("title") or ""), 26, "#0F172A", weight=800, max_width=card_w - 64, max_lines=2))
        parts.append(f'<line x1="{x+30:.1f}" y1="{y+160:.1f}" x2="{x+card_w-30:.1f}" y2="{y+160:.1f}" stroke="{stroke}" stroke-width="2"/>')
        parts.append(_text_left(x + 32, y + 205, str(sec.get("desc") or ""), 18, "#1F2937", max_width=card_w - 64, max_lines=3))
        if i < len(sections[:6]) - 1:
            parts.append(_line(x + card_w + 8, y + card_h / 2, x + card_w + gap - 8, y + card_h / 2, cls="connectorLight"))
    if spec.get("formula"):
        parts.append(_rect(300, 650, 765, 82, "#FFFFFF", "#A78BFA", rx=18, width=1.6, cls=""))
        parts.append(_text_center(W / 2, 692, str(spec.get("formula")), 25, "#0F172A", weight=700, max_width=720, max_lines=2))
    return "\n".join(parts)


def _render_parallel_stack_architecture(spec: dict[str, Any]) -> str:
    enc = list(spec.get("encoder_layers") or [])
    dec = list(spec.get("decoder_layers") or [])
    parts: list[str] = []
    box_w, box_h = 430, 470
    enc_x, dec_x = 170, 765
    y = 205
    parts.append(_rect(enc_x, y, box_w, box_h, "#F0FDF4", "#16803A", rx=22))
    parts.append(_text_center(enc_x + box_w/2, y + 42, "编码器（Encoder）", 26, "#166534", weight=800, max_width=box_w-40))
    parts.append(_rect(dec_x, y, box_w, box_h, "#EFF6FF", "#2563EB", rx=22))
    parts.append(_text_center(dec_x + box_w/2, y + 42, "解码器（Decoder）", 26, "#1D4ED8", weight=800, max_width=box_w-40))
    def stack(items, x, color):
        row_h = min(58, (box_h - 110) / max(1, len(items)))
        out=[]
        for i, item in enumerate(items):
            yy = y + 92 + i * (row_h + 10)
            out.append(_rect(x + 50, yy, box_w - 100, row_h, "#FFFFFF", color, rx=12, width=1.4, cls=""))
            out.append(_text_center(x + box_w/2, yy + row_h/2, str(item), 18, "#0F172A", weight=700, max_width=box_w-130, max_lines=2))
        return out
    parts.extend(stack(enc, enc_x, "#86EFAC"))
    parts.extend(stack(dec, dec_x, "#93C5FD"))
    parts.append(_line(enc_x + box_w + 18, y + box_h/2, dec_x - 18, y + box_h/2, cls="connector", label="交叉注意力"))
    if spec.get("note"):
        parts.append(_legend(str(spec["note"]), x=250, y=760, width=865))
    return "\n".join(parts)

def _legend(text: str, *, x: float = 125, y: float = 792, width: float = 1115) -> str:
    return (
        _rect(x, y, width, 54, "#FFFFFFCC", "#CBD5E1", rx=18, width=1.2, cls="")
        + _text_center(x + width / 2, y + 28, text, 17, "#334155", weight=600, max_width=width - 40, max_lines=2)
    )
